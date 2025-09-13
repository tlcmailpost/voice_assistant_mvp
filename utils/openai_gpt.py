# utils/openai_gpt.py
import os
import sys
import traceback
from typing import Optional, List

try:
    from openai import OpenAI
except Exception:
    raise RuntimeError("Библиотека 'openai' не установлена. Проверь requirements.txt и деплой.")

# --------- Настройки моделей ---------
PREFERRED_MODELS: List[str] = [
    "gpt-4o-mini",  # быстрый и дешёвый
    "gpt-4o",       # запасной вариант, мощнее
]

# --------- Загружаем системный промпт ---------
PROMPT_FILE = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt_en.txt")
SYSTEM_PROMPT = "You are a polite English-speaking medical voice assistant."
if os.path.exists(PROMPT_FILE):
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            SYSTEM_PROMPT = f.read().strip()
        print("[openai_gpt] system prompt loaded from file")
    except Exception as e:
        print(f"[openai_gpt] error loading prompt file: {e}", file=sys.stderr)
else:
    print("[openai_gpt] system_prompt_en.txt not found, using default")

# --------- Настройки генерации ---------
MAX_TOKENS = 220
TEMPERATURE = 0.3

# --------- Клиент OpenAI ---------
_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
if not _api_key:
    print("[openai] OPENAI_API_KEY is missing in environment!", file=sys.stderr)

_client = OpenAI(api_key=_api_key) if _api_key else None


def _call_model(model: str, prompt: str) -> Optional[str]:
    """Вызывает конкретную модель OpenAI и возвращает ответ."""
    if not _client:
        return None
    try:
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
        print(f"[openai] model '{model}' error: {e}", file=sys.stderr)
        try:
            traceback.print_exc()
        except Exception:
            pass
        return None


def get_gpt_response(prompt: str) -> str:
    """Основная функция ассистента. Пытается несколько моделей подряд."""
    if not prompt or not prompt.strip():
        return "Sorry, I didn’t catch that. Could you repeat please?"

    if not _client:
        return "OpenAI API key is missing. Please check your configuration."

    for model in PREFERRED_MODELS:
        result = _call_model(model, prompt)
        if result:
            return result

    return "Sorry, I’m having trouble connecting right now. Please try again in a minute."
