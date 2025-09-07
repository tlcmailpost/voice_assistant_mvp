from flask import Flask, request, jsonify
from openai_gpt import get_gpt_response
from twilio_response import respond_to_call
import os

app = Flask(__name__)
@app.route("/", methods=["GET"])
def home():
    return "Voice Assistant is running!"

@app.route("/", methods=["GET"])
def index():
    return "Voice Assistant is running!"

@app.route("/voice", methods=["POST"])
def voice():
    response = respond_to_call(request.form)
    return str(response)

# Главная правка здесь:
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
