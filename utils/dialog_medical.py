# utils/dialog_medical.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import re
from datetime import datetime, timedelta

# Парсинг дат/времени
try:
    import dateparser
except Exception:
    dateparser = None

# Валидация телефонов
try:
    import phonenumbers
    from phonenumbers.phonenumberutil import NumberParseException
except Exception:
    phonenumbers = None
    NumberParseException = Exception

from .twilio_response import ssml_digits


# --------------------------- вспомогательные функции ---------------------------

def normalize_name(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    parts = [p.capitalize() for p in t.split(" ") if p]
    return " ".join(parts)


def parse_reason(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ["clean", "hygiene"]):
        return "Cleaning"
    if any(w in t for w in ["consult", "check"]):
        return "Consultation"
    if any(w in t for w in ["pain", "hurt", "urgent"]):
        return "Urgent visit"
    return t.strip().capitalize() or "Appointment"


def parse_dob(text: str) -> Optional[datetime]:
    if not text:
        return None
    if dateparser:
        dt = dateparser.parse(text, languages=["en"], settings={"PREFER_DAY_OF_MONTH": "first"})
        if dt and 1900 < dt.year < datetime.now().year + 1:
            return dt
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", text)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mth, d)
        except Exception:
            return None
    return None


def parse_phone(text: str, default_region: str = "US") -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None, None

    if phonenumbers:
        try:
            num = phonenumbers.parse(digits, default_region)
            if phonenumbers.is_valid_number(num):
                e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
                only_digits = re.sub(r"\D", "", e164)
                return e164, ssml_digits(only_digits)
        except NumberParseException:
            pass

    if len(digits) == 10:
        e164 = "+1" + digits
        return e164, ssml_digits(digits)
    if len(digits) == 11 and digits.startswith("1"):
        e164 = "+" + digits
        return e164, ssml_digits(digits[1:])
    return None, None


def parse_when(text: str) -> Optional[datetime]:
    if not text:
        return None
    if dateparser:
        dp = dateparser.parse(text, languages=["en"], settings={"PREFER_DATES_FROM": "future"})
        if dp:
            if dp.hour == 0 and dp.minute == 0 and not any(x in text for x in [":", "am", "pm"]):
                dp = dp.replace(hour=10, minute=0)
            return dp.replace(second=0, microsecond=0)
    return None


# ------------------------------- состояние диалога -------------------------------

@dataclass
class PatientData:
    full_name: Optional[str] = None
    reason: Optional[str] = None
    when_dt: Optional[datetime] = None
    dob: Optional[datetime] = None
    phone_e164: Optional[str] = None
    phone_ssml: Optional[str] = None
    attempts: Dict[str, int] = field(default_factory=dict)


class MedDialog:
    """
    FSM:
    intro -> name -> reason -> when -> dob -> phone -> confirm -> create
    """

    def __init__(self):
        self._sessions: Dict[str, PatientData] = {}

    def get(self, call_sid: str) -> PatientData:
        if call_sid not in self._sessions:
            self._sessions[call_sid] = PatientData()
        return self._sessions[call_sid]

    def reset(self, call_sid: str):
        if call_sid in self._sessions:
            del self._sessions[call_sid]

    # --------------------- основной обработчик ---------------------

    def handle(self, call_sid: str, user_text: str, from_number: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        txt = (user_text or "").strip()

        # === NAME with confirmation ===
        if not s.full_name:
            # если ждем подтверждения имени
            if "candidate_name" in s.attempts:
                candidate = s.attempts["candidate_name"]
                t = txt.lower()
                if any(w in t for w in ["yes", "correct", "confirm", "yeah", "right", "ok", "okay", "sure"]):
                    s.full_name = candidate
                    s.attempts.pop("candidate_name")
                    return f"Great, {s.full_name}. What is the reason for your visit?", False, False
                elif any(w in t for w in ["no", "wrong", "not"]):
                    s.attempts.pop("candidate_name")
                    return "Okay, let's try again. Please tell me your full name.", False, False
                else:
                    return f"I heard your name as {candidate}. Please say yes if this is correct, or no if you want to repeat.", False, False

            if not txt:
                return "Please tell me your full name.", False, False
            candidate = normalize_name(txt)
            s.attempts["candidate_name"] = candidate
            return f"I heard your name as {candidate}. Is that correct?", False, False

        # === REASON ===
        if not s.reason:
            if not txt:
                return "What is the reason for your visit? For example: consultation, cleaning, urgent.", False, False
            s.reason = parse_reason(txt)
            return f"Reason noted: {s.reason}. What date and time do you prefer?", False, False

        # === WHEN ===
        if not s.when_dt:
            if not txt:
                return "Please tell me the date and time for your appointment, for example: tomorrow at 3 pm.", False, False
            when = parse_when(txt)
            if not when:
                return "I didn’t understand the date and time. Please repeat, for example: September 10th at 10 am.", False, False
            s.when_dt = when
            return f"Okay, appointment on {s.when_dt.strftime('%B %d at %H:%M')}. What is your date of birth?", False, False

        # === DOB with confirmation ===
        if not s.dob:
            if "candidate_dob" in s.attempts:
                candidate_dob = s.attempts["candidate_dob"]
                t = txt.lower()
                if any(w in t for w in ["yes", "correct", "confirm", "yeah", "right", "ok", "okay", "sure"]):
                    s.dob = candidate_dob
                    s.attempts.pop("candidate_dob")
                    return f"Date of birth {s.dob.strftime('%d %B %Y')} confirmed. Please provide your phone number.", False, False
                elif any(w in t for w in ["no", "wrong", "not"]):
                    s.attempts.pop("candidate_dob")
                    return "Okay, please repeat your date of birth, for example: May 15 1980.", False, False
                else:
                    return f"I heard your date of birth as {candidate_dob.strftime('%d %B %Y')}. Please say yes if this is correct, or no if you want to repeat.", False, False

            if not txt:
                return "Please tell me your date of birth, for example: May 15 1980.", False, False
            dob = parse_dob(txt)
            if not dob:
                return "I didn’t catch the date of birth. Please repeat, for example: May 15 1980.", False, False
            s.attempts["candidate_dob"] = dob
            return f"I heard your date of birth as {dob.strftime('%d %B %Y')}. Is that correct?", False, False

        # === PHONE with confirmation ===
        if not s.phone_e164:
            if "candidate_phone" in s.attempts:
                candidate_e164, candidate_ssml = s.attempts["candidate_phone"]
                t = txt.lower()
                if any(w in t for w in ["yes", "correct", "confirm", "yeah", "right", "ok", "okay", "sure"]):
                    s.phone_e164 = candidate_e164
                    s.phone_ssml = candidate_ssml
                    s.attempts.pop("candidate_phone")
                    return f"Phone number confirmed. Let me summarize all details.", False, False
                elif any(w in t for w in ["no", "wrong", "not"]):
                    s.attempts.pop("candidate_phone")
                    return "Okay, please repeat your phone number digit by digit.", False, False
                else:
                    return f"I heard your phone number as {candidate_ssml}. Please say yes if this is correct, or no if you want to repeat.", False, False

            if not txt:
                return "Please tell me your phone number, digit by digit.", False, False
            e164, ssml = parse_phone(txt, default_region="US")
            if not e164:
                return "I didn’t catch the phone number. Please repeat slowly, digit by digit.", False, False
            s.attempts["candidate_phone"] = (e164, ssml)
            return f"I heard your phone number as {ssml}. Is that correct?", False, False

        # === CONFIRMATION ===
        dob_str = s.dob.strftime("%d.%m.%Y") if s.dob else "-"
        dt_str = s.when_dt.strftime("%d.%m.%Y at %H:%M") if s.when_dt else "-"
        confirm_text = (
            f"Please confirm. Name: {s.full_name}. "
            f"Reason: {s.reason}. "
            f"Date and time: {dt_str}. "
            f"Date of birth: {dob_str}. "
            f"Phone: {s.phone_e164}. "
            "If everything is correct, please say confirm. "
            "If something is wrong, please say what to correct."
        )
        return confirm_text, False, False
