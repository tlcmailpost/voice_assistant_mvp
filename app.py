# app.py — CLEAN SAFE BOOT
import os
from flask import Flask, request, Response, redirect, session
from werkzeug.middleware.proxy_fix import ProxyFix

# -------------------- Flask app + proxy & session config --------------------
app = Flask(__name__)

# Доверяем прокси Render (чтобы request.url был https) и явно задаём https
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"

# СЕКРЕТ ДЛЯ СЕССИЙ — ОБЯЗАТЕЛЬНО ДО ЛЮБЫХ @app.route
env_secret = os.environ.get("FLASK_SECRET_KEY")
if env_secret and env_secret.strip():
    app.secret_key = env_secret.strip()
    app.config["SECRET_KEY"] = app.secret_key
else:
    # Подстраховка: сгенерируем временный ключ, чтобы сервер не падал.
    # (Но рекомендуем задать FLASK_SECRET_KEY в Render → Environment.)
    gen = os.urandom(32)
    app.secret_key = gen
    app.config["SECRET_KEY"] = app.secret_key
    print("[flask] WARNING: FLASK_SECRET_KEY отсутствует; использую временный ключ")

app.config.update(
    SESSION_COOKIE_SECURE=True,   # cookie только по https
    SESSION_COOKIE_SAMESITE="Lax"
)
# ---------------------------------------------------------------------------

# ----------------------------- Optional imports ----------------------------
from utils.openai_gpt import get_gpt_response
from utils.twilio_response import create_twiml_response

# Диалог (медицинский) — по возможности
try:
    from utils.dialog_medical import MedDialog
    HAVE_MED = True
except Exception as e:
    print(f"[boot] dialog_medical not available: {e}")
    MedDialog = None
    HAVE_MED = False

# Google OAuth/Calendar — по возможности
try:
    from utils.google_oauth import build_flow, save_creds, load_creds
    from utils.calendar import create_event
    HAVE_GOOGLE = True
except Exception as e:
    print(f"[boot] google calendar not available: {e}")
    build_flow = save_creds = load_creds = create_event = None
    HAVE_GOOGLE = False

# SMS — по возможности
try:
    from utils.sms import send_sms
    HAVE_SMS = True
except Exception as e:
    print(f"[boot] sms not available: {e}")
    def send_sms(*args, **kwargs): return False
    HAVE_SMS = False
# ---------------------------------------------------------------------------

# ------------------------------- App settings ------------------------------
ECHO_MODE = os.environ.get("ECHO_MODE", "0") == "1"
APP_BASE = os.environ.get("APP_BASE_URL", "https://voice-assistant-mvp-9.onrender.com")
CLINIC_NAME = os.environ.get("CLINIC_NAME", "Клиника")

dialog = MedDialog() if HAVE_MED and MedDialog else None
# ---------------------------------------------------------------------------

# ------------------------------- Diagnostics -------------------------------
@app.route("/debug/secret")
def debug_secret():
    sk = app.config.get("SECRET_KEY")
    return ("SECRET_SET=True" if sk else "SECRET_SET=False"), 200, {
        "Content-Type": "text/plain; charset=utf-8"
    }

@app.route("/debug/google")
def debug_google():
    cid  = os.environ.get("GOOGLE_CLIENT_ID", "")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    redir = os.environ.get("GOOGLE_REDIRECT_URI", "")
    def mask(s: str) -> str:
        return (s[:8] + "…" + s[-8:]) if len(s) > 20 else (s or "(empty)")
    body = [
        "GOOGLE_CLIENT_ID: " + mask(cid),
        "GOOGLE_CLIENT_SECRET: " + mask(csec),
        "GOOGLE_REDIRECT_URI: " + (redir or "(empty)"),
    ]
    return "\n".join(body), 200, {"Content-Type": "text/plain; charset=utf-8"}
# ---------------------------------------------------------------------------

# --------------------------------- Routes ----------------------------------
@app.route("/", methods=["GET"])
def home():
    return "✅ Voice Assistant is running!"

@app.route("/twilio-voice", methods=["GET", "POST"])
def twilio_voice():
    if request.method == "GET":
        twiml_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Say language="ru-RU" voice="alice">'
            'Webhook готов. Используйте POST для распознавания речи.'
            '</Say></Response>'
        )
        return Response(twiml_xml, mimetype="text/xml")

    call_sid = (request.form.get("CallSid") or "").strip()
    from_number = (request.form.get("From") or "").strip()
    speech_text = (request.form.get("SpeechResult") or request.values.get("SpeechResult") or "").strip()
    print(f"[Twilio] CallSid={call_sid} From={from_number} Speech='{speech_text}'")

    # Первичный вызов — просим речь
    if not speech_text:
        twiml_xml = create_twiml_response(None)
        return Response(twiml_xml, mimetype="text/xml")

    # --- Медицинский диалог (если доступен) ---
    if dialog:
        reply, done, create_flag = dialog.handle(call_sid, speech_text, from_number)
        if create_flag:
            # Требуется Google OAuth
            if not HAVE_GOOGLE or not load_creds or not load_creds("admin"):
                reply = f"Чтобы завершить запись, подключите Google: {APP_BASE}/oauth/google/start"
            else:
                try:
                    s = dialog.get(call_sid).data
                    # Без внешних зависимостей парсим ISO стандартными средствами
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(s["datetime_iso"])
                    ok, info = create_event(
                        summary=f"{CLINIC_NAME}: {s.get('full_name','Пациент')} / {s.get('reason','приём')}",
                        start_dt=start_dt,
                        description=f"DOB: {s.get('dob_str','-')}, Phone: {s.get('phone','-')}"
                    )
                    if ok:
                        reply = "Запись создана. Ссылка отправлена в SMS."
                        if HAVE_SMS:
                            sms_body = f"{CLINIC_NAME}: запись {s.get('datetime_str')} — {s.get('reason','приём')}."
                            send_sms(s.get('phone',''), sms_body)
                    else:
                        reply = f"Не удалось создать событие: {info}"
                except Exception as e:
                    print(f"[calendar] error: {e}")
                    reply = "Не удалось создать событие сейчас. Попробуйте позднее."
            dialog.reset(call_sid)
            twiml_xml = create_twiml_response(reply)
            return Response(twiml_xml, mimetype="text/xml")

        if reply:
            twiml_xml = create_twiml_response(reply)
            return Response(twiml_xml, mimetype="text/xml")

    # --- Обычный Q&A ---
    out = f"Вы сказали: {speech_text}" if ECHO_MODE else get_gpt_response(speech_text)
    twiml_xml = create_twiml_response(out)
    return Response(twiml_xml, mimetype="text/xml")

# ---- Google OAuth (если модули есть) ----
@app.route("/oauth/google/start")
def oauth_google_start():
    if not HAVE_GOOGLE or not build_flow:
        return "Google OAuth пока не настроен на сервере.", 200

    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    # Сохраняем state в сессии — критично для защиты от CSRF и для колбэка
    session["google_oauth_state"] = state
    return redirect(auth_url)

@app.route("/oauth/google/callback")
def oauth_google_callback():
    if not HAVE_GOOGLE or not build_flow or not save_creds:
        return "Google OAuth пока не настроен на сервере.", 200

    # Достаём state из сессии и пересоздаём Flow с тем же state
    state = session.pop("google_oauth_state", None)
    flow = build_flow(state=state)

    # Подстраховка: если прокси подставил внутренний http, заменим на https
    auth_resp_url = request.url.replace("http://", "https://", 1)

    # Обмен кода на токены
    flow.fetch_token(authorization_response=auth_resp_url)
    save_creds(flow.credentials, "admin")
    return "✅ Google подключён! Можно возвращаться к звонку."
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
