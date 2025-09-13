# app.py — GPT-first with per-call history
import os
from collections import defaultdict, deque
from flask import Flask, request, Response, redirect, session
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"

HARD_SECRET = "vK7!qD9#sYp$3Lx@0ZnF4hGt8Rb^2MwUjE1oCk&Va5Tr*NpXgHdWlQfZy!BmRs"
env_secret = (os.environ.get("FLASK_SECRET_KEY") or "").strip()
final_secret = env_secret or HARD_SECRET
app.secret_key = final_secret
app.config["SECRET_KEY"] = final_secret
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE="Lax")
print(f"[flask] SECRET from env? {'yes' if env_secret else 'no (using hard)'}")

from utils.openai_gpt import get_gpt_response
from utils.twilio_response import create_twiml_response

# --- Load external system prompt ---
PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts/system_prompt_en.txt")
SYSTEM_PROMPT = ""
if os.path.exists(PROMPT_FILE):
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
    print("[app] system prompt loaded ✅")
else:
    print("[app] system prompt not found ❌")

# ---- Per-call chat history (in-memory) ----
# CallSid -> deque of {'role': 'user'|'assistant', 'content': '...'}
SESSIONS = defaultdict(lambda: deque(maxlen=12))

@app.route("/", methods=["GET"])
def home():
    return "✅ Voice Assistant is running!"

@app.route("/twilio-voice", methods=["GET", "POST"])
def twilio_voice():
    if request.method == "GET":
        twiml_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Say language="en-US" voice="Polly.Joanna">'
            'Webhook is ready. Use POST for speech recognition.'
            '</Say></Response>'
        )
        return Response(twiml_xml, mimetype="text/xml")

    call_sid = (request.form.get("CallSid") or "").strip()
    from_number = (request.form.get("From") or "").strip()
    speech_text = (request.form.get("SpeechResult") or request.values.get("SpeechResult") or "").strip()
    print(f"[Twilio] CallSid={call_sid} From={from_number} Speech='{speech_text}'")

    # ПЕРВОЕ обращение в звонке → приветствие
    if not speech_text:
        # Очистим историю на старте звонка (подстраховка)
        if call_sid:
            SESSIONS.pop(call_sid, None)
        twiml_xml = create_twiml_response(None, first=True)
        return Response(twiml_xml, mimetype="text/xml")

    # История для этого звонка
    hist = list(SESSIONS.get(call_sid, deque()))
    # Добавляем текущую реплику пользователя
    if call_sid:
        SESSIONS[call_sid].append({"role": "user", "content": speech_text})

    # Получаем ответ GPT с учётом истории
    out = get_gpt_response(speech_text, system_prompt=SYSTEM_PROMPT, history=hist)

    # Кладём ответ ассистента в историю
    if call_sid and out:
        SESSIONS[call_sid].append({"role": "assistant", "content": out})

    # Отдаём TwiML
    twiml_xml = create_twiml_response(out)
    return Response(twiml_xml, mimetype="text/xml")

# --- Optional: endpoint to clear a call session (если подключишь статус-хуки Twilio)
@app.route("/debug/clear/<sid>")
def debug_clear(sid: str):
    SESSIONS.pop(sid, None)
    return f"Cleared session for {sid}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
