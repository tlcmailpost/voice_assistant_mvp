# utils/openai_gpt.py
import os, sys, traceback
from typing import Optional, List, Dict, Any

try:
    from openai import OpenAI
except Exception:
    raise RuntimeError("Library 'openai' is not installed. Check requirements.txt and deploy.")

PREFERRED_MODELS: List[str] = [
    "gpt-4o-mini",  # fast & cheaper
    "gpt-4o",
]

DEFAULT_SYSTEM_PROMPT = (
    "You are a polite, professional voice receptionist for a medical clinic. "
    "Speak naturally, keep answers short (1–3 sentences). "
    "Never use profanity or technical phrases."
)

MAX_TOKENS = 220
TEMPERATURE = 0.3

_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
if not _api_key:
    print("[openai] OPENAI_API_KEY is missing in environment!", file=sys.stderr)
_client = OpenAI(api_key=_api_key) if _api_key else None


def _call_model(model: str, messages: List[Dict[str, Any]]) -> Optional[str]:
    if not _client:
        return None
    try:
        resp = _client.chat.completions.create(
            model=model,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=messages,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or None
    except Exception as e:
        print(f"[openai] model '{model}' error: {e}", file=sys.stderr)
        try: traceback.print_exc()
        except Exception: pass
        return None


def get_gpt_response(
    user_text: str,
    system_prompt: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    history — список [{role: 'user'|'assistant', content: '...'}] из прошлых ходов.
    Мы сами добавим system и текущий user.
    """
    if not user_text or not user_text.strip():
        return "I didn’t catch that. Could you repeat, please?"
    if not _client:
        return "OpenAI API key not found. Please check configuration."

    sys_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT

    # Формируем сообщения: system → history → текущий user
    messages: List[Dict[str, str]] = [{"role": "system", "content": sys_prompt}]
    if history:
        # подрезаем историю, чтобы не распухала
        tail = history[-12:]  # последние 12 сообщений (6 пар)
        for m in tail:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_text.strip()})

    for model in PREFERRED_MODELS:
        result = _call_model(model, messages)
        if result:
            return result

    return "Sorry, I’m having trouble right now. Please try again in a minute."
