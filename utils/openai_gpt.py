# utils/openai_gpt.py
import os
import sys
import traceback
from typing import Optional, List

try:
    from openai import OpenAI
except Exception:
    # Если зависимость не подтянулась ещё
    raise RuntimeError("Библиотека 'openai' не установлена. Проверь requirements.txt и деплой.")

# --------- Настройки ---------
# Актуальные быстрые и дешёвые модели; сначала mini, затем полноразмерная.
# Если какая-то недоступна в аккаунте, код попробует следующую.
PREFERRED_MODELS: List[str] = [
    "gpt-4o-mini",  # быстрый и экономичный
    "gpt-4o",       # более мощный, чуть дороже/дольше
]

SYSTEM_PROMPT = (
    "Ты — вежливый русскоязычный голосовой ассистент. "
    "Отвечай кратко, по делу, 1–3 предложения. "
    "Избегай длинных списков, говори естественно."
)

# Ограничим длину, чтобы Twilio не ждал слишком долго
MAX_TOKENS = 220
TEMPERATURE = 0.3

# --------- Клиент ---------
_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
if not _api_key:
    # Сообщим в stdout — это попадёт в Render Logs
    print("[openai] OPENAI_API_KEY is missing in environment!", file=sys.stderr)

_client = OpenAI(api_key=_api_key) if _api_key else None


def _call_model(model: str, prompt: str) -> Optional[str]:
    """
    Пробует один вызов модели. Возвращает текст или None при ошибке.
    """
    if not _client:
        return None
    try:
        # Современный вызов Chat Completions (поддерживается в openai>=1.x)
        resp = _client.chat.completions.create(
            model=model,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt.strip()},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or None
    except Exception as e:
        # Логируем, но не прерываем — пусть попробует следующую модель
        print(f"[openai] model '{model}' error: {e}", file=sys.stderr)
        try:
            traceback.print_exc()
        except Exception:
            pass
        return None


def get_gpt_response(prompt: str) -> str:
    """
    Главная функция для ассистента.
    Делаем валидацию входа, пытаемся несколько моделей по очереди,
    выдаём понятный ответ при фатальной ошибке.
    """
    if not prompt or not prompt.strip():
        return "Я не расслышал. Повторите, пожалуйста."

    # Если нет API-ключа — вернём понятное сообщение
    if not _client:
        return "Ключ OpenAI не найден в конфигурации. Попросите администратора проверить настройки."

    # Пробуем модели по очереди
    for model in PREFERRED_MODELS:
        result = _call_model(model, prompt)
        if result:
            return result

    # Если все попытки неудачны:
    return "Извините, сейчас не получается получить ответ от модели. Попробуйте ещё раз через минуту."



