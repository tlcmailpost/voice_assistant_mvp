# utils/dialog_medical.py
import re
from datetime import datetime

class PatientData:
    def __init__(self):
        self.full_name = None
        self.reason = None
        self.dob_str = None
        self.datetime_str = None
        self.datetime_iso = None
        self.phone = None
        self.step = "name"
        self.attempts = {}

    def reset(self):
        self.__init__()

class MedDialog:
    def __init__(self):
        self.sessions = {}

    def get(self, call_sid):
        if call_sid not in self.sessions:
            self.sessions[call_sid] = PatientData()
        return self.sessions[call_sid]

    def reset(self, call_sid):
        if call_sid in self.sessions:
            self.sessions[call_sid].reset()

    def handle(self, call_sid, text, from_number=None):
        s = self.get(call_sid)
        txt = (text or "").strip()

        # === STEP: NAME ===
        if s.step == "name":
            if not txt:
                return "Please tell me your full name.", False, False

            # Candidate name
            candidate = txt
            if "candidate_name" not in s.attempts:
                s.attempts["candidate_name"] = candidate
                return f"I heard your name is {candidate}. Is that correct?", False, False

            # Confirm candidate name
            if txt.lower() in ["yes", "yeah", "correct", "right", "confirm"]:
                s.full_name = s.attempts.pop("candidate_name")
                s.step = "reason"
                return f"Great, {s.full_name}. What is the reason for your visit?", False, False
            elif txt.lower() in ["no", "wrong", "incorrect"]:
                s.attempts.pop("candidate_name", None)
                return "Okay, please repeat your full name.", False, False
            else:
                return "Please say yes if this is correct, or no if you want to repeat.", False, False

        # === STEP: REASON ===
        if s.step == "reason":
            if not s.reason:
                s.reason = txt
                s.step = "dob"
                return f"Thank you. Reason noted: {s.reason}. What is your date of birth?", False, False

        # === STEP: DOB ===
        if s.step == "dob":
            if not s.dob_str:
                # Simple validation: must contain digits
                if not re.search(r"\d", txt):
                    return "Please tell me your date of birth in month, day, and year format.", False, False
                s.dob_str = txt
                s.step = "datetime"
                return f"Got it. Your date of birth is {s.dob_str}. What date and time do you prefer for the appointment?", False, False

        # === STEP: DATETIME ===
        if s.step == "datetime":
            if not s.datetime_str:
                s.datetime_str = txt
                try:
                    s.datetime_iso = str(datetime.fromisoformat(txt))
                except Exception:
                    s.datetime_iso = None
                s.step = "phone"
                return f"Okay, appointment requested for {s.datetime_str}. Could you give me your phone number?", False, False

        # === STEP: PHONE ===
        if s.step == "phone":
            if not s.phone:
                digits = "".join(ch for ch in txt if ch.isdigit())
                if not digits:
                    return "Please say the phone number clearly, digit by digit.", False, False
                s.phone = digits
                s.step = "done"
                return f"Thank you. I recorded your phone number as {', '.join(s.phone)}. Should I confirm the appointment now?", False, True

        # === STEP: DONE ===
        if s.step == "done":
            return "All details are already collected.", True, True

        return "Sorry, I didn’t understand. Could you repeat?", False, False
