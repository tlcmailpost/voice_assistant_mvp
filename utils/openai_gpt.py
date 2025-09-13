import os
import sys
import traceback
from typing import Optional, List

try:
    from openai import OpenAI
except Exception:
    raise RuntimeError("Library 'openai' is not installed. Check requirements.txt and deploy.")

# --------- Default Settings ---------
PREFERRED_MODELS: List[str] = [
    "gpt-4o-mini",  # fast & cheaper
    "gpt-4o",       # more powerful
]

DEFAULT_SYSTEM_PROMPT = (
    "You are a polite, professional voice assistant for a medical clinic. "
    "Speak naturally, keep answers short (1–3 sentences). "
    "Never joke, never use inappropriate words."
)

MAX_TOKENS = 220
TEMPERATURE = 0.3

# --------- OpenAI Client ---------
_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
if not _api_key:
    print("[openai] OPENAI_API_KEY is missing in environment!", file=sys.stderr)

_client = OpenAI(api_key=_api_key) if _api_key else None


def _call_model(model: str, prompt: str, system_prompt: str) -> Optional[str]:
    """
    Try one model call. Return response text or None if error.
    """
    if not _client:
        return None
    try:
        resp = _client.chat.completions.create(
            model=model,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
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


def get_gpt_response(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Main function for assistant.
    If system_prompt is given → use it.
    Else → fallback to DEFAULT_SYSTEM_PROMPT.
    """
    if not prompt or not prompt.strip():
        return "I did not hear you. Please repeat."

    if not _client:
        return "OpenAI API key not found. Please check configuration."

    sys_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT

    # Try models in order
    for model in PREFERRED_MODELS:
        result = _call_model(model, prompt, sys_prompt)
        if result:
            return result

    return "Sorry, I cannot get a response right now. Please try again later."
