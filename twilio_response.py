from twilio.twiml.voice_response import VoiceResponse

def create_twiml_response(text):
    response = VoiceResponse()
    response.say(text, voice='alice', language='en-US')
    return str(response)