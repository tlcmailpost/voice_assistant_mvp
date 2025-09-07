import os
from flask import Flask, request, Response

from utils.openai_gpt import get_gpt_response  # как у тебя было раньше
from utils.twilio_response import create_twiml_response

app = Flask(__name__)

# ВРЕМЕННО для отладки: эхо-режим (повторяем распознанное)
# Включается через переменную окружения ECHO_MODE=1
ECHO_MODE = os.environ.get("ECHO_MODE", "0") == "1"

@app.route("/", methods=["GET"])
def home():
    return "✅ Voice Assistant is running!"

# Разрешаем и GET, и POST — чтобы консоль Twilio не показывала "Not Valid"
@app.route("/twilio-voice", methods=["GET", "POST"])
def twilio_voice():
    if request.method == "GET":
        # Короткий валидный TwiML на GET — консоль будет довольна
        twiml_xml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="ru-RU" voice="alice">Webhook готов. Используйте POST для распознавания речи.</Say></Response>'
        return Response(twiml_xml, mimetype="text/xml")

    # ------ POST ------
    # (Опционально) Посмотрим весь приходящий набор полей в логах Render
    try:
        print(f"[Twilio] form={dict(request.form)} values={dict(request.values)}")
    except Exception:
        pass

    # Twilio присылает SpeechResult после Gather. В первый заход его нет.
    speech_text = (
        request.form.get("SpeechResult")
        or request.values.get("SpeechResult")
        or ""
    ).strip()
    print(f"[Twilio] SpeechResult: {speech_text!r}")

    if not speech_text:
        # Первый вызов / тишина — вернём Gather
        twiml_xml = create_twiml_response(None)
        return Response(twiml_xml, mimetype="text/xml")

    # ЭХО-ОТВЕТ для отладки: сразу услышишь, что распозналось.
    if ECHO_MODE:
        reply = f"Вы сказали: {speech_text}"
    else:
        # Боевой режим: спрашиваем GPT (оставь utils/openai_gpt.py как раньше)
        reply = get_gpt_response(speech_text)

    print(f"[Reply] {reply}")
    twiml_xml = create_twiml_response(reply)
    return Response(twiml_xml, mimetype="text/xml")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

