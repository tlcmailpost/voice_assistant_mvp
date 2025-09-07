from flask import request
from utils.openai_gpt import get_gpt_response
from twilio.twiml.voice_response import VoiceResponse

def handle_call():
    """Обработка входящего звонка от Twilio"""
    prompt = request.values.get("SpeechResult", "")
    print(f"User said: {prompt}")

    response_text = get_gpt_response(prompt)
    print(f"GPT response: {response_text}")

    resp = VoiceResponse()
    resp.say(response_text, voice='alice', language='en-US')
    return str(resp)

