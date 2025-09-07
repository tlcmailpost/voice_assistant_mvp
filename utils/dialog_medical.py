# utils/dialog_medical.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional
from utils.validators import parse_dob, normalize_phone, parse_datetime_ru

PROMPTS = {
    "greeting": "Здравствуйте! Вы позвонили в клинику. Давайте запишем вас на приём.",
    "full_name": "Назовите, пожалуйста, ваше имя и фамилию.",
    "dob": "Назовите дату рождения в формате день-месяц-год.",
    "phone": "Продиктуйте номер телефона для подтверждения записи.",
    "reason": "Кратко опишите причину визита: консультация, чистка или лечение?",
    "datetime": "Когда вам удобно прийти? Назовите день и время, например: завтра в 10 утра.",
    "confirm": "Подтвердите запись: {summary}. Сказать «да» или «нет»?",
    "bad_dob": "Не расслышал дату рождения. Повторите, пожалуйста: день-месяц-год.",
    "bad_phone": "Не распознал номер. Повторите номер телефона, пожалуйста.",
    "bad_dt": "Не распознал дату и время. Скажите, например: завтра в 10 утра.",
    "ok_booked": "Готово! Запись создана. Отправлю SMS-подтверждение.",
    "cancel": "Хорошо, отменяю. Скажите другую дату и время, пожалуйста.",
}

STEPS = ["full_name", "dob", "phone", "reason", "datetime", "confirm"]

@dataclass
class MedSession:
    stage: str = "full_name"
    data: Dict[str, str] = field(default_factory=dict)

    def next_prompt(self) -> str:
        return PROMPTS[self.stage]

    def summary(self) -> str:
        n = self.data.get("full_name", "без имени")
        dob = self.data.get("dob_str", "дата рождения не указана")
        ph = self.data.get("phone", "без телефона")
        reason = self.data.get("reason", "без причины")
        when = self.data.get("datetime_str", "время не указано")
        return f"{n}, {dob}, телефон {ph}, причина: {reason}, время: {when}"

class MedDialog:
    """Простая машина состояний. Возвращает (reply_text, done_flag, need_create_event_flag)."""

    def __init__(self):
        self.sessions: Dict[str, MedSession] = {}

    def get(self, call_sid: str) -> MedSession:
        if call_sid not in self.sessions:
            self.sessions[call_sid] = MedSession()
        return self.sessions[call_sid]

    def reset(self, call_sid: str):
        self.sessions[call_sid] = MedSession()

    def handle(self, call_sid: str, speech: str, from_number: Optional[str] = None):
        s = self.get(call_sid)
        text = (speech or "").strip()

        if s.stage == "full_name":
            if text:
                s.data["full_name"] = text
                s.stage = "dob"
                return PROMPTS["dob"], False, False
            return PROMPTS["full_name"], False, False

        if s.stage == "dob":
            dob = parse_dob(text)
            if dob:
                s.data["dob"] = dob.isoformat()
                s.data["dob_str"] = dob.strftime("%d.%m.%Y")
                s.stage = "phone"
                return PROMPTS["phone"], False, False
            return PROMPTS["bad_dob"], False, False

        if s.stage == "phone":
            phone = normalize_phone(text) or normalize_phone(from_number or "")
            if phone:
                s.data["phone"] = phone
                s.stage = "reason"
                return PROMPTS["reason"], False, False
            return PROMPTS["bad_phone"], False, False

        if s.stage == "reason":
            if text:
                s.data["reason"] = text
                s.stage = "datetime"
                return PROMPTS["datetime"], False, False
            return PROMPTS["reason"], False, False

        if s.stage == "datetime":
            dt = parse_datetime_ru(text)
            if dt:
                s.data["datetime_iso"] = dt.isoformat()
                s.data["datetime_str"] = dt.strftime("%d %B %H:%M")
                s.stage = "confirm"
                return PROMPTS["confirm"].format(summary=s.summary()), False, False
            return PROMPTS["bad_dt"], False, False

        if s.stage == "confirm":
            low = text.lower()
            if any(x in low for x in ["да", "подтверж", "ок", "хорошо", "ага"]):
                # подтверждаем → выходим, сигналим создать событие
                return PROMPTS["ok_booked"], True, True
            if any(x in low for x in ["нет", "отмена", "не", "поменяй"]):
                # отменяем только время → вернемся на выбор времени
                s.stage = "datetime"
                return PROMPTS["cancel"], False, False
            # если не понял — повторим просьбу подтвердить
            return PROMPTS["confirm"].format(summary=s.summary()), False, False

        # на всякий случай
        self.reset(call_sid)
        return PROMPTS["greeting"] + " " + PROMPTS["full_name"], False, False
