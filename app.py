from flask import Flask, request, Response
from utils.openai_gpt import get_gpt_response
from utils.twilio_response import create_twiml_response
import os

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "✅ Voice assistant is running!"

@app.route("/twilio-voice", methods=["POST"])
def voice():
    speech_text = request.form.get("SpeechResult", "")
    print(f"User said: {speech_text}")

    reply = get_gpt_response(speech_text)
    print(f"Assistant reply: {reply}")

    twiml = create_twiml_response(reply)
    return Response(twiml, mimetype="text/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)