from twilio.twiml.voice_response import VoiceResponse

def create_twiml_response(text: str) -> str:
    """
    Создаёт TwiML-ответ для звонка в Twilio.
    :param text: Текст, который будет произнесён голосом Alice.
    :return: XML-строка (TwiML).
    """
    response = VoiceResponse()
    response.say(text, voice="alice", language="en-US")
    return str(response)
