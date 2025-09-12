from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import re
from datetime import datetime, timedelta

try:
    import dateparser  # requires: dateparser==1.2.0
except Exception:
    dateparser = None

try:
    import phonenumbers  # requires: phonenumbers==8.13.43
    from phonenumbers.phonenumberutil import NumberParseException
except Exception:
    phonenumbers = None
    NumberParseException = Exception

from .twilio_response import ssml_digits


# --------------------------- helpers ---------------------------

def normalize_name(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    parts = [p.capitalize() for p in t.split(" ") if p]
    return " ".join(parts)


def parse_reason(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ["clean", "hygiene"]):
        return "Cleaning"
    if "consult" in t:
        return "Consultation"
    if any(w in t for w in ["pain", "hurt", "urgent"]):
        return "Urgent check"
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
            if dp.hour == 0 and dp.minute == 0 and not any(x in text for x in [":", "am", "pm", "hour"]):
                dp = dp.replace(hour=10, minute=0)
            return dp.replace(second=0, microsecond=0)
    return None


# ------------------------------- state -------------------------------

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

    def handle(self, call_sid: str, user_text: str, from_number: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)

        # if all filled, wait for confirm
        if s.full_name and s.reason and s.when_dt and s.dob and s.phone_e164:
            return self.handle_confirm(call_sid, user_text)

        return self._handle_collect(call_sid, user_text)

    def _handle_collect(self, call_sid: str, user_text: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        txt = (user_text or "").strip()

        # 0) INTRO
        if not s.attempts.get("intro"):
            s.attempts["intro"] = 1
            return (
                "👋 Welcome to MedVoice AI Clinic! "
                "I will help you schedule your appointment. "
                "First, please tell me your full name."
            ), False, False

        # 1) NAME
        if not s.full_name:
            if not txt:
                return "Please tell me your full name.", False, False
            s.full_name = normalize_name(txt)
            txt = ""

        # 2) REASON
        if not s.reason:
            if not txt:
                return "What is the reason for your visit? For example: consultation, cleaning, or urgent check.", False, False
            s.reason = parse_reason(txt)
            txt = ""

        # 3) WHEN
        if not s.when_dt:
            if not txt:
                return "When would you like to come? For example: tomorrow at 3:30 PM, or September 10th at 10 AM.", False, False
            when = parse_when(txt)
            if not when:
                return "I didn’t catch the date and time. Please repeat, for example: tomorrow at 11:00 AM.", False, False
            s.when_dt = when
            txt = ""

        # 4) DOB
        if not s.dob:
            if not txt:
                return "Please provide your date of birth. For example: May 15, 1980.", False, False
            dob = parse_dob(txt)
            if not dob:
                return "I didn’t catch your date of birth. Please repeat.", False, False
            s.dob = dob
            txt = ""

        # 5) PHONE
        if not s.phone_e164:
            if not txt:
                return "Please say your contact phone number, slowly, digit by digit.", False, False
            e164, ssml = parse_phone(txt, default_region="US")
            if not e164:
                return "I didn’t catch your phone number. Please repeat slowly.", False, False
            s.phone_e164 = e164
            s.phone_ssml = ssml
            txt = ""

        # 6) CONFIRM
        dob_str = s.dob.strftime("%d.%m.%Y") if s.dob else "-"
        dt_str = s.when_dt.strftime("%d.%m.%Y at %H:%M") if s.when_dt else "-"

        confirm_text = (
            f"Let’s confirm. {s.full_name}. "
            f"Reason: {s.reason}. "
            f"Date and time: {dt_str}. "
            f"Date of birth: {dob_str}. "
            f"Phone: {s.phone_ssml if s.phone_ssml else ''} "
            "If this is correct, please say 'confirm'. "
            "If you need to change something, just say what to fix."
        )

        return confirm_text, False, False

    def handle_confirm(self, call_sid: str, user_text: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        t = (user_text or "").lower().strip()
        if any(w in t for w in ["confirm", "yes", "correct"]):
            return "Creating your appointment…", True, True
        if "name" in t:
            s.full_name = None
            return "Please repeat your full name.", False, False
        if "reason" in t:
            s.reason = None
            return "Please tell me the reason for your visit.", False, False
        if "date" in t or "time" in t:
            s.when_dt = None
            return "Please tell me the exact date and time, for example: September 10th at 10:00 AM.", False, False
        if "birth" in t:
            s.dob = None
            return "Please say your full date of birth: day, month, year.", False, False
        if "phone" in t or "number" in t:
            s.phone_e164 = None
            s.phone_ssml = None
            return "Please repeat your phone number.", False, False

        return "If everything is correct, please say 'confirm'. Or tell me what to change.", False, False
