# utils/twilio_response.py
from twilio.twiml.voice_response import VoiceResponse, Gather

VOICE = "Polly.Tatyana"  # более естественная русская озвучка, чем 'alice'
LANG = "ru-RU"


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
    Возвращает строку с SSML для показа цифр по одной:
    Пример: 'Наш телефон: <say-as interpret-as="digits">7188441007</say-as>'
    Работает в Twilio/Polly.
    """
    digits_only = "".join(ch for ch in s if ch.isdigit())
    if not digits_only:
        return s
    return f'Наш контактный номер: <say-as interpret-as="digits">{digits_only}</say-as>.'


def create_twiml_response(text: str | None = None, *, hints: str | None = None) -> str:
    """
    Если text пуст → даём Gather для распознавания речи.
    Если text есть → произносим ответ и предлагаем следующий вопрос.
    Поддерживает в тексте SSML-теги (<say-as interpret-as="digits">...).
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
            "После сигнала скажите один ответ. Если не услышал — повторю вопрос.",
            voice=VOICE, language=LANG
        )
        vr.append(gather)
        # ВАЖНО: не говорим сразу «я не услышал» — это убирает ощущение зацикливания
        return str(vr)

    # Если в тексте есть SSML-теги <say-as ...>, Twilio проглотит их корректно.
    speak_text = _clip(str(text))
    vr.say(speak_text, voice=VOICE, language=LANG)
    vr.pause(length=1)
    vr.say("Можете продолжать.", voice=VOICE, language=LANG)
    vr.redirect("/twilio-voice", method="POST")
    return str(vr)
