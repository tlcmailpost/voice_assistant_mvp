import os
from flask import Flask, request, Response
from utils.openai_gpt import get_gpt_response
from utils.twilio_response import create_twiml_response

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "✅ Voice Assistant is running!"

@app.route("/twilio-voice", methods=["POST"])
def twilio_voice():
    speech_text = request.form.get("SpeechResult", "") or request.values.get("SpeechResult", "")
    print(f"[Twilio] User said: {speech_text}")

    reply = get_gpt_response(speech_text)
    print(f"[GPT] Assistant reply: {reply}")

    twiml_xml = create_twiml_response(reply)
    return Response(twiml_xml, mimetype="text/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
