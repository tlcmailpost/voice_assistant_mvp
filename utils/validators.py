# utils/validators.py
import os
from datetime import datetime
import dateparser
import phonenumbers
import pytz

TZ = os.environ.get("TIMEZONE", "America/New_York")

def parse_datetime_ru(text: str):
    if not text: 
        return None
    return dateparser.parse(
        text,
        languages=["ru"],
        settings={
            "TIMEZONE": TZ,
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DATES_FROM": "future",
        },
    )

def parse_dob(text: str):
    """Парсим дату рождения (день-месяц-год). Вернём date или None."""
    if not text:
        return None
    dt = dateparser.parse(
        text,
        languages=["ru", "en"],
        settings={
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DAY_OF_MONTH": "first",
        },
    )
    return dt.date() if dt else None

def normalize_phone(text: str, default_region: str = "US"):
    """Приводим номер к E.164 (+1...). Вернём строку или None."""
    if not text:
        return None
    try:
        num = phonenumbers.parse(text, default_region)
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    return None
