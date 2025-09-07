# utils/sms.py
import os
from twilio.rest import Client

_TW_SID = os.environ.get("TWILIO_ACCOUNT_SID")
_TW_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
_TW_FROM = os.environ.get("TWILIO_PHONE_NUMBER")

_client = Client(_TW_SID, _TW_TOKEN) if all([_TW_SID, _TW_TOKEN]) else None

def send_sms(to_number: str, body: str) -> bool:
    if not _client or not _TW_FROM or not to_number:
        return False
    try:
        _client.messages.create(from_=_TW_FROM, to=to_number, body=body[:1000])
        return True
    except Exception as e:
        print(f"[twilio-sms] error: {e}")
        return False
