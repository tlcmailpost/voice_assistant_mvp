# utils/dialog_medical.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import re
from datetime import datetime

try:
    import dateparser
except Exception:
    dateparser = None

try:
    import phonenumbers
    from phonenumbers.phonenumberutil import NumberParseException
except Exception:
    phonenumbers = None
    NumberParseException = Exception

from .twilio_response import ssml_digits


def normalize_name(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    parts = [p.capitalize() for p in t.split(" ") if p]
    return " ".join(parts)


def parse_reason(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ["clean", "hygiene"]):
        return "Cleaning"
    if any(w in t for w in ["consult", "checkup"]):
        return "Consultation"
    if any(w in t for w in ["pain", "hurt", "urgent"]):
        return "Emergency visit"
    return t.strip().capitalize() or "Appointment"


def parse_dob(text: str) -> Optional[datetime]:
    if not text:
        return None
    if dateparser:
        dt = dateparser.parse(text, languages=["en"], settings={"PREFER_DAY_OF_MONTH": "first"})
        if dt and dt.year and 1900 < dt.year < datetime.now().year + 1:
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


@dataclass
class PatientData:
    full_name: Optional[str] = None
    reason: Optional[str] = None
    when_dt: Optional[datetime] = None
    dob: Optional[datetime] = None
    phone_e164: Optional[str] = None
    phone_ssml: Optional[str] = None
    attempts: Dict[str, int] = field(default_factory=dict)

    def inc(self, key: str) -> int:
        self.attempts[key] = self.attempts.get(key, 0) + 1
        return self.attempts[key]


class MedDialog:
    """
    FSM: intro -> name -> reason -> when -> dob -> phone -> confirm -> create
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

    def _handle_collect(self, call_sid: str, user_text: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        txt = (user_text or "").strip()

        # 1) NAME
        if not s.full_name:
            if not txt:
                s.inc("name")
                return "Please tell me your full name.", False, False
            s.full_name = normalize_name(txt)
            return f"Thank you, I got your name: {s.full_name}. What is the reason for your visit?", False, False

        # 2) REASON
        if not s.reason:
            if not txt:
                s.inc("reason")
                return "What is the reason for your visit? For example: consultation, cleaning, or emergency.", False, False
            s.reason = parse_reason(txt)
            return f"Reason noted: {s.reason}. When would you like to come?", False, False

        # 3) WHEN
        if not s.when_dt:
            if not txt:
                s.inc("when")
                return "When would you like to come? For example: tomorrow at 3:30 PM or September 10 at 10 AM.", False, False
            when = parse_when(txt)
            if not when:
                if s.inc("when") < 3:
                    return "Sorry, I didn’t catch the date and time. Please repeat, for example: 'day after tomorrow at 11 AM'.", False, False
                else:
                    return "Please say the date and exact time, like 'September 10 at 10:00 AM'.", False, False
            s.when_dt = when
            dt_str = s.when_dt.strftime("%B %d, %Y at %I:%M %p")
            return f"Got it, appointment on {dt_str}. Please tell me your date of birth.", False, False

        # 4) DOB
        if not s.dob:
            if not txt:
                s.inc("dob")
                return "Please tell me your date of birth, for example: May 15, 1980.", False, False
            dob = parse_dob(txt)
            if not dob:
                if s.inc("dob") < 3:
                    return "Sorry, I didn’t catch the date of birth. Please repeat.", False, False
                else:
                    return "Please say your full date of birth: day, month, year.", False, False
            s.dob = dob
            dob_str = s.dob.strftime("%B %d, %Y")
            return f"Thank you, I recorded your date of birth: {dob_str}. Finally, please tell me your contact phone number.", False, False

        # 5) PHONE
        if not s.phone_e164:
            if not txt:
                s.inc("phone")
                return "Please tell me your contact phone number. Say it digit by digit or in small groups.", False, False
            e164, ssml = parse_phone(txt, default_region="US")
            if not e164:
                if s.inc("phone") < 3:
                    return "Sorry, I didn’t catch the phone number. Please repeat slowly digit by digit.", False, False
                else:
                    return "Say the number again, for example: seven one eight, eight four four, one zero zero seven.", False, False
            s.phone_e164 = e164
            s.phone_ssml = ssml
            return f"Perfect, I got your phone number. Let’s confirm your appointment details.", False, False

        # 6) CONFIRM
        dob_str = s.dob.strftime("%B %d, %Y") if s.dob else "-"
        dt_str = s.when_dt.strftime("%B %d, %Y at %I:%M %p") if s.when_dt else "-"
        confirm_text = (
            f"Let’s confirm. Name: {s.full_name}. "
            f"Reason: {s.reason}. "
            f"Date and time: {dt_str}. "
            f"Date of birth: {dob_str}. "
            f"{s.phone_ssml if s.phone_ssml else ''} "
            f"If this is correct, please say 'confirm'. "
            f"If something needs to be changed, please say what exactly."
        )
        return confirm_text, False, False

    def handle_confirm(self, call_sid: str, user_text: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        t = (user_text or "").lower().strip()
        if any(w in t for w in ["confirm", "yes", "correct"]):
            return "Creating the appointment now…", True, True
        if "name" in t:
            s.full_name = None
            return "Please repeat your full name.", False, False
        if "reason" in t or "visit" in t:
            s.reason = None
            return "Please tell me the reason for your visit.", False, False
        if "date" in t or "time" in t:
            s.when_dt = None
            return "Please tell me the date and time of the visit, for example: September 10 at 10 AM.", False, False
        if "birth" in t:
            s.dob = None
            return "Please tell me your date of birth: day, month, year.", False, False
        if "phone" in t or "number" in t:
            s.phone_e164 = None
            s.phone_ssml = None
            return "Please repeat your contact phone number digit by digit.", False, False
        return "If everything is correct, please say 'confirm'. Or tell me what needs to be changed.", False, False

    def handle(self, call_sid: str, user_text: str, from_number: str = "") -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        if s.full_name and s.reason and s.when_dt and s.dob and s.phone_e164:
            return self.handle_confirm(call_sid, user_text)
        return self._handle_collect(call_sid, user_text)
