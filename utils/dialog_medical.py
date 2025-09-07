# utils/dialog_medical.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import re
from datetime import datetime, timedelta

# Парсинг дат/времени
try:
    import dateparser  # требует: dateparser==1.2.0
except Exception:
    dateparser = None

# Валидация телефонов (США)
try:
    import phonenumbers  # требует: phonenumbers==8.13.43
    from phonenumbers.phonenumberutil import NumberParseException
except Exception:
    phonenumbers = None
    NumberParseException = Exception

from .twilio_response import ssml_digits  # для озвучки цифр


# --------------------------- вспомогательные функции ---------------------------

def normalize_name(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    # простая нормализация регистра
    parts = [p.capitalize() for p in t.split(" ") if p]
    return " ".join(parts)


def parse_reason(text: str) -> str:
    t = (text or "").lower()
    # простейшие ключевые слова
    if any(w in t for w in ["чистк", "гигиен", "clean"]):
        return "Профгигиена"
    if any(w in t for w in ["консульт", "consult"]):
        return "Консультация"
    if any(w in t for w in ["боль", "болит", "экстрен", "urgent"]):
        return "Экстренный осмотр"
    return t.strip().capitalize() or "Приём"


def parse_dob(text: str) -> Optional[datetime]:
    # Ожидаем что-то вроде "15 мая 1980", "15.05.1980", "1980-05-15"
    if not text:
        return None
    if dateparser:
        dt = dateparser.parse(text, languages=["ru"], settings={"PREFER_DAY_OF_MONTH": "first"})
        if dt and dt.year and dt.year > 1900 and dt.year < datetime.now().year + 1:
            return dt
    # fallback: dd.mm.yyyy
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", text)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mth, d)
        except Exception:
            return None
    return None


def parse_phone(text: str, default_region: str = "US") -> Tuple[Optional[str], Optional[str]]:
    """
    Возвращает (E164, для_озвучки_цифрами).
    Пример: ("+17188441007", "<say-as interpret-as='digits'>7188441007</say-as>")
    """
    if not text:
        return None, None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None, None

    if phonenumbers:
        try:
            num = phonenumbers.parse(digits, default_region)
            if phonenumbers.is_valid_number(num):
                e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
                # для озвучки берём только цифры без плюса
                only_digits = re.sub(r"\D", "", e164)
                return e164, ssml_digits(only_digits)
        except NumberParseException:
            pass

    # Fallback: США без проверки
    if len(digits) == 10:
        e164 = "+1" + digits
        return e164, ssml_digits(digits)
    if len(digits) == 11 and digits.startswith("1"):
        e164 = "+" + digits
        return e164, ssml_digits(digits[1:])
    return None, None


def parse_when(text: str) -> Optional[datetime]:
    """
    Парсит дату/время визита. Если указано только время — считает ближайший день.
    """
    if not text:
        return None
    if dateparser:
        dp = dateparser.parse(text, languages=["ru"], settings={"PREFER_DATES_FROM": "future"})
        if dp:
            # если времени не было — зададим 10:00 по умолчанию
            if dp.hour == 0 and dp.minute == 0 and not any(x in text for x in [":", "час", "мин"]):
                dp = dp.replace(hour=10, minute=0)
            # округление к ближайшей минуте
            return dp.replace(second=0, microsecond=0)
    # Fallback: "10 сентября в 15:00" уже покрывается dateparser; тут можно расширять по мере необходимости
    return None


# ------------------------------- состояние диалога -------------------------------

@dataclass
class PatientData:
    full_name: Optional[str] = None
    reason: Optional[str] = None
    when_dt: Optional[datetime] = None
    dob: Optional[datetime] = None
    phone_e164: Optional[str] = None
    phone_ssml: Optional[str] = None

    attempts: Dict[str, int] = field(default_factory=dict)

    def inc(self, key: str) -> int:
        self.attempts[key] = self.attempts.get(key, 0) + 1
        return self.attempts[key]


class MedDialog:
    """
    Простая FSM:
    intro -> name -> reason -> when -> dob -> phone -> confirm -> create
    """

    def __init__(self):
        self._sessions: Dict[str, PatientData] = {}

    def get(self, call_sid: str) -> PatientData:
        if call_sid not in self._sessions:
            self._sessions[call_sid] = PatientData()
        return self._sessions[call_sid]

    def reset(self, call_sid: str):
        if call_sid in self._sessions:
            del self._sessions[call_sid]

    # --------------------- основной обработчик ---------------------

    def handle(self, call_sid: str, user_text: str, from_number: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        txt = (user_text or "").strip()

        # 1) NAME
        if not s.full_name:
            # если пользователь сказал «записаться ...» — ловим имя после
            if len(txt.split()) <= 2 or any(w in txt.lower() for w in ["меня", "зовут"]):
                # попытаемся выцепить имя-последовательность
                m = re.search(r"(?:меня зовут|моё имя|я)\s+([А-ЯЁA-Z][\w\- ]+)$", txt, re.IGNORECASE)
                if m:
                    s.full_name = normalize_name(m.group(1))
                else:
                    s.inc("name")
                    return "Назовите, пожалуйста, ваше имя и фамилию.", False, False
            else:
                # возможно, первое, что сказали — это цель, а не имя
                # попробуем принять это как имя, если там 2+ слова и нет явной причины
                if any(k in txt.lower() for k in ["чистк", "консульт", "боль", "осмотр"]):
                    pass
                else:
                    s.full_name = normalize_name(txt)

            if not s.full_name:
                s.inc("name")
                return "Повторите, пожалуйста, ваше полное имя.", False, False

            # не возвращаемся — продолжаем собирать дальше
            txt = ""  # потребуем следующий ответ

        # 2) REASON
        if not s.reason:
            if not txt:
                s.inc("reason")
                return ("Коротко: цель визита — консультация, чистка, экстренный осмотр? "
                        "Скажите одним словом.", False, False)
            s.reason = parse_reason(txt)
            txt = ""

        # 3) WHEN (дата+время)
        if not s.when_dt:
            if not txt:
                s.inc("when")
                return ("Когда удобно прийти? Например: «завтра в 15:30» или «10 сентября в 10 утра».", False, False)
            when = parse_when(txt)
            if not when:
                if s.inc("when") < 3:
                    return ("Не расслышал дату и время. Повторите, пожалуйста, например: "
                            "«послезавтра в 11:00».", False, False)
                else:
                    return ("Пока не понял дату и время. Давайте так: назовите дату и точное время в формате "
                            "«10 сентября в 10:00».", False, False)
            s.when_dt = when
            txt = ""

        # 4) DOB (дата рождения)
        if not s.dob:
            if not txt:
                s.inc("dob")
                return ("Назовите дату рождения, например: «15 мая 1980» или «15.05.1980».", False, False)
            dob = parse_dob(txt)
            if not dob:
                if s.inc("dob") < 3:
                    return "Не расслышал дату рождения. Повторите, пожалуйста.", False, False)
                else:
                    return "Скажите дату рождения полностью: число, месяц, год.", False, False)
            s.dob = dob
            txt = ""

        # 5) PHONE
        if not s.phone_e164:
            if not txt:
                s.inc("phone")
                return ("Назовите контактный номер телефона. Говорите по цифрам или блоками.", False, False)
            e164, ssml = parse_phone(txt, default_region="US")
            if not e164:
                if s.inc("phone") < 3:
                    return ("Не расслышал номер. Повторите, пожалуйста, медленно по цифрам.", False, False)
                else:
                    return ("Скажите номер ещё раз, например: «семь один восемь, восемь четыре четыре, "
                            "десять, ноль семь».", False, False)
            s.phone_e164 = e164
            s.phone_ssml = ssml
            txt = ""

        # 6) CONFIRM
        if txt:
            # если пользователю есть что добавить после заполнения — пропустим в подтверждение
            pass

        # Формируем подтверждение с чтением телефона по цифрам
        dob_str = s.dob.strftime("%d.%m.%Y") if s.dob else "-"
        dt_str = s.when_dt.strftime("%d.%m.%Y в %H:%M") if s.when_dt else "-"

        confirm_text = (f"Проверим. {s.full_name}. Причина визита: {s.reason}. "
                        f"Дата и время: {dt_str}. Дата рождения: {dob_str}. "
                        f"{s.phone_ssml if s.phone_ssml else ''} Если всё верно, скажите «подтверждаю». "
                        f"Если нужно исправить — скажите, что именно.")

        return confirm_text, False, False

        # Пользователь должен сказать «подтверждаю». Это ловим уже в следующем заходе.
        # Ниже — второй проход, когда ждём подтверждение и создаём событие.

    # ВТОРОЙ ВЫЗОВ ПОСЛЕ ПОДТВЕРЖДЕНИЯ
    def handle_confirm(self, call_sid: str, user_text: str) -> Tuple[str, bool, bool]:
        s = self.get(call_sid)
        t = (user_text or "").lower().strip()
        if any(w in t for w in ["подтверждаю", "да", "верно", "всё верно", "подтверждаю запись"]):
            # сигнал на создание события
            return "Создаю запись…", True, True
        # Если сказали, что-то надо исправить — сбросим поле и спросим заново
        if "имя" in t or "фамил" in t:
            s.full_name = None
            return "Повторите, пожалуйста, имя и фамилию.", False, False
        if "причин" in t or "цель" in t or "визит" in t:
            s.reason = None
            return "Скажите причину визита одним словом.", False, False
        if "дат" in t or "врем" in t:
            s.when_dt = None
            return "Назовите дату и время визита, например: «10 сентября в 10:00».", False, False
        if "рожд" in t:
            s.dob = None
            return "Назовите дату рождения полностью: день, месяц, год.", False, False
        if "тел" in t or "номер" in t:
            s.phone_e164 = None
            s.phone_ssml = None
            return "Назовите контактный номер по цифрам.", False, False

        # Иначе мягкое повторение
        return "Если всё верно, скажите «подтверждаю». Или скажите, что исправить.", False, False

    # Унифицированный интерфейс, вызывается из app.py
    def handle(self, call_sid: str, user_text: str, from_number: str) -> Tuple[str, bool, bool]:
        """
        Возвращает: (reply_text, done, create_event_flag)
        done нам не критичен, оставлен для совместимости.
        """
        s = self.get(call_sid)

        # Если уже все поля заполнены — ждём подтверждения
        if s.full_name and s.reason and s.when_dt and s.dob and s.phone_e164:
            return self.handle_confirm(call_sid, user_text)

        # Иначе продолжаем сбор
        return self._handle_collect(call_sid, user_text)

    # Внутренний метод (чтоб не ломать сигнатуру)
    def _handle_collect(self, call_sid: str, user_text: str) -> Tuple[str, bool, bool]:
        # Это та самая логика из handle() — но вынесена, чтобы не путаться.
        # Для простоты просто вызовем исходный handle тела:
        return MedDialog.handle.__wrapped__(self, call_sid, user_text, "")
