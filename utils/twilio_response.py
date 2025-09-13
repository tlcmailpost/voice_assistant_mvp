from twilio.twiml.voice_response import VoiceResponse, Gather

VOICE = "alice"   # English voice
LANG = "en-US"    # English language


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
    Returns SSML string for digit-by-digit pronunciation.
    Example: 'Our phone number is <say-as interpret-as="digits">7188441007</say-as>'
    """
    digits_only = "".join(ch for ch in s if ch.isdigit())
    if not digits_only:
        return s
    return f'Our contact number is: <say-as interpret-as="digits">{digits_only}</say-as>.'


def create_twiml_response(text: str | None = None, *, hints: str | None = None) -> str:
    """
    If text is empty → give Gather for speech recognition.
    If text exists → say response and then continue asking.
    Supports SSML tags (<say-as interpret-as="digits">...).
    """
    vr = VoiceResponse()

    if not text or not str(text).strip():
        gather = Gather(
            input="speech",
            language=LANG,
            action="/twilio-voice",
            method="POST",
            timeout=7,
            speech_timeout="auto",
        )
        gather.say(
            "Please speak after the beep. If I didn’t catch it, I will repeat the question.",
            voice=VOICE, language=LANG
        )
        vr.append(gather)
        return str(vr)

    # If text has SSML tags <say-as ...>, Twilio will handle them correctly.
    speak_text = _clip(str(text))
    vr.say(speak_text, voice=VOICE, language=LANG)
    vr.pause(length=1)
    vr.say("You may continue.", voice=VOICE, language=LANG)
    vr.redirect("/twilio-voice", method="POST")
    return str(vr)
