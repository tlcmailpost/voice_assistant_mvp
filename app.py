from flask import Flask, request
from twilio_response import twilio_voice_response
from openai_gpt import get_gpt_response

app = Flask(__name__)

# Route for health check / homepage
@app.route("/", methods=["GET"])
def home():
    return "Voice Assistant is running!"

# Route for handling Twilio voice webhook
@app.route("/twilio-voice", methods=["POST"])
def voice():
    incoming_message = request.form.get("SpeechResult", "")
    print(f"User said: {incoming_message}")

    # Get response from OpenAI
    gpt_response = get_gpt_response(incoming_message)
    print(f"GPT responded: {gpt_response}")

    # Create TwiML voice response
    response = twilio_voice_response(gpt_response)
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
