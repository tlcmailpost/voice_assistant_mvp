from twilio.twiml.voice_response import VoiceResponse, Gather

def create_twiml_response(text: str | None = None) -> str:
    """
    Если text пустой -> даём Gather для распознавания речи.
    Если text есть -> произносим ответ и снова предлагаем задать вопрос.
    """
    vr = VoiceResponse()

    if not text or not str(text).strip():
        # Первый заход (или тишина): просим сказать вопрос
        gather = Gather(
            input="speech",
            language="ru-RU",
            action="/twilio-voice",   # Twilio вернётся сюда же со SpeechResult
            method="POST",
            timeout=6,                # пауза молчания перед фолбэком
            speech_timeout="auto"     # завершать по естественной паузе
        )
        gather.say(
            "Скажите ваш вопрос после сигнала. Например: «Создай встречу завтра в 10 утра».",
            voice="alice",
            language="ru-RU"
        )
        vr.append(gather)

        # На случай, если пользователь промолчал:
        vr.say("Я не услышал речь. Попробуйте ещё раз.", voice="alice", language="ru-RU")
        vr.redirect("/twilio-voice", method="POST")
        return str(vr)

    # Есть распознанный текст -> отвечаем и предлагаем следующий вопрос
    vr.say(str(text).strip(), voice="alice", language="ru-RU")
    vr.pause(length=1)
    vr.say("Можете задать следующий вопрос.", voice="alice", language="ru-RU")
    vr.redirect("/twilio-voice", method="POST")
    return str(vr)

