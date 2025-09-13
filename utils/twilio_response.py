# utils/twilio_response.py
from twilio.twiml.voice_response import VoiceResponse, Gather

# --- Settings: English voice ---
VOICE = "Polly.Joanna"  # Natural English voice
LANG = "en-US"


def _clip(text: str, limit: int = 450) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    for p in ".?!…":
        k = cut.rfind(p)
        if k >= int(limit * 0.6):
            return cut[:k + 1].strip()
    return cut.strip() + "…"


def ssml_digits(s: str) -> str:
    """
    Return SSML string to pronounce digits one by one.
    Example: 'Our phone: <say-as interpret-as="digits">7188441007</say-as>'
    Works in Twilio/Polly.
    """
    digits_only = "".join(ch for ch in s if ch.isdigit())
    if not digits_only:
        return s
    return f'Contact number: <say-as interpret-as="digits">{digits_only}</say-as>.'


def create_twiml_response(text: str | None = None, *, hints: str | None = None, first: bool = False) -> str:
    """
    If text is empty → ask user with Gather.
    If text is given → speak response and wait for next input.
    Supports SSML tags (<say-as interpret-as="digits">...).
    """
    vr = VoiceResponse()

    if not text or not str(text).strip():
        # First greeting
        gather = Gather(
            input="speech",
            language=LANG,
            action="/twilio-voice",
            method="POST",
            timeout=7,
            speech_timeout="auto",
        )
        greet = "Welcome to MedVoice Clinic. Please tell me your full name." if first else "Please say your answer."
        gather.say(greet, voice=VOICE, language=LANG)
        vr.append(gather)
        return str(vr)

    # If we already have text, just answer once and open Gather again
    speak_text = _clip(str(text))
    vr.say(speak_text, voice=VOICE, language=LANG)

    gather = Gather(
        input="speech",
        language=LANG,
        action="/twilio-voice",
        method="POST",
        timeout=7,
        speech_timeout="auto",
    )
    gather.say("Please continue.", voice=VOICE, language=LANG)
    vr.append(gather)

    return str(vr)
