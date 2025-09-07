from flask import Flask, request, Response
from utils.openai_gpt import get_gpt_response
from utils.twilio_response import create_twiml_response

app = Flask(__name__)

@app.route("/")
def index():
    return "<h1>👋 Привет, Влад!</h1><p>Твой виртуальный ассистент работает! 🚀</p><p>Теперь можно подключать Twilio и GPT для голосового общения.</p>"

@app.route("/twilio-voice", methods=["POST"])
def voice():
    speech_text = request.form.get("SpeechResult", "")
    print(f"User said: {speech_text}")

    reply = get_gpt_response(speech_text)
    print(f"Assistant reply: {reply}")

    twiml = create_twiml_response(reply)
    return Response(twiml, mimetype="text/xml")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
