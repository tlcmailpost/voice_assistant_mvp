import os
from flask import Flask, request, Response

from utils.openai_gpt import get_gpt_response  # оставить как в прошлой версии
from utils.twilio_response import create_twiml_response

app = Flask(__name__)

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

    # ----- POST -----
    # Twilio присылает SpeechResult после Gather. В первый заход его нет.
    speech_text = (
        request.form.get("SpeechResult")
        or request.values.get("SpeechResult")
        or ""
    ).strip()
    print(f"[Twilio] SpeechResult: {speech_text!r}")

    if not speech_text:
        # Первый вызов / тишина — отвечаем Gather'ом
        twiml_xml = create_twiml_response(None)
        return Response(twiml_xml, mimetype="text/xml")

    # Есть распознанный текст → спрашиваем GPT и озвучиваем
    reply = get_gpt_response(speech_text)
    print(f"[GPT] Reply: {reply}")
    twiml_xml = create_twiml_response(reply)
    return Response(twiml_xml, mimetype="text/xml")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


