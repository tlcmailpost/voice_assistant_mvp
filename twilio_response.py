from twilio.twiml.voice_response import VoiceResponse

def create_twiml_response(text):
    response = VoiceResponse()
    response.say(text, voice='alice', language='ru-RU')
    return str(response)
