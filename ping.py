# ping.py
import os
import requests

BASE = os.environ.get("BASE_URL", "https://voice-assistant-mvp-9.onrender.com").rstrip("/")

def ping(path: str) -> None:
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, timeout=8)
        print(f"[PING] {url} -> {r.status_code}")
    except Exception as e:
        print(f"[PING] {url} -> ERROR: {e}")

if __name__ == "__main__":
    ping("/")              # будим главную
    ping("/twilio-voice")  # будим вебхук (GET отдаёт TwiML)
