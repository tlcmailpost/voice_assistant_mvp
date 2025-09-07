from twilio.twiml.voice_response import VoiceResponse

def create_twiml_response(text: str) -> str:
    """
    Возвращает корректный TwiML (XML), который Twilio прочитает голосом Alice.
    """
    resp = VoiceResponse()
    resp.say(text, voice="alice", language="en-US")
    return str(resp)

