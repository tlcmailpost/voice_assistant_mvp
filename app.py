# app.py — clean GPT-first mode with optional FSM toggle
import os
from flask import Flask, request, Response, redirect, session
from werkzeug.middleware.proxy_fix import ProxyFix

# -------------------- Flask app + proxy & session config --------------------
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"

# Hard secret fallback (keeps app booting even if env missing)
HARD_SECRET = "vK7!qD9#sYp$3Lx@0ZnF4hGt8Rb^2MwUjE1oCk&Va5Tr*NpXgHdWlQfZy!BmRs"
env_secret = (os.environ.get("FLASK_SECRET_KEY") or "").strip()
final_secret = env_secret or HARD_SECRET
app.secret_key = final_secret
app.config["SECRET_KEY"] = final_secret
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE="Lax")
print(f"[flask] SECRET from env? {'yes' if env_secret else 'no (using hard)'}")

# ----------------------------- Imports ----------------------------
from utils.openai_gpt import get_gpt_response
from utils.twilio_response import create_twiml_response

# Optional: FSM (dialog_medical)
try:
    from utils.dialog_medical import MedDialog
    HAVE_MED = True
except Exception as e:
    print(f"[boot] dialog_medical not available: {e}")
    MedDialog = None
    HAVE_MED = False

# Optional: Google Calendar
try:
    from utils.google_oauth import build_flow, save_creds, load_creds
    from utils.calendar import create_event
    HAVE_GOOGLE = True
except Exception as e:
    print(f"[boot] google calendar not available: {e}")
    build_flow = save_creds = load_creds = create_event = None
    HAVE_GOOGLE = False

# Optional: SMS
try:
    from utils.sms import send_sms
    HAVE_SMS = True
except Exception as e:
    print(f"[boot] sms not available: {e}")
    def send_sms(*args, **kwargs): return False
    HAVE_SMS = False

# ------------------------------- App settings ------------------------------
ECHO_MODE = os.environ.get("ECHO_MODE", "0") == "1"
APP_BASE = os.environ.get("APP_BASE_URL", "https://voice-assistant-mvp-9.onrender.com")
CLINIC_NAME = os.environ.get("CLINIC_NAME", "MedVoice Clinic")

# ✅ Тумблер: использовать FSM или чистый GPT
USE_FSM = os.environ.get("USE_FSM", "0") == "1"
dialog = (MedDialog() if (HAVE_MED and MedDialog and USE_FSM) else None)
print(f"[mode] USE_FSM={USE_FSM}")

# ------------------------------- Diagnostics -------------------------------
@app.route("/debug/secret")
def debug_secret():
    sk = app.config.get("SECRET_KEY")
    src = "env" if (os.environ.get("FLASK_SECRET_KEY") or "").strip() else "hard"
    return (f"SECRET_SET={'True' if sk else 'False'} via={src}"), 200, {"Content-Type":"text/plain; charset=utf-8"}

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

# --------------------------------- Routes ----------------------------------
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

    # Если пусто — вернём Gather (приветствие/вопрос делает twilio_response)
    if not speech_text:
        twiml_xml = create_twiml_response(None)
        return Response(twiml_xml, mimetype="text/xml")

    # ===== РЕЖИМ FSM (если включён) =====
    if dialog:
        try:
            reply, done, create_flag = dialog.handle(call_sid, speech_text, from_number)
        except Exception as e:
            print(f"[dialog] ERROR: {e}")
            reply, done, create_flag = "Sorry, something went wrong. Let’s try again.", False, False

        if create_flag:
            if not HAVE_GOOGLE or not load_creds or not load_creds("admin"):
                reply = f"To finish booking, connect Google Calendar: {APP_BASE}/oauth/google/start"
            else:
                try:
                    # ⚠️ Здесь зависит от реализации твоего MedDialog; оставляем как есть.
                    s = dialog.get(call_sid)  # получаем объект состояния
                    # Ожидается, что у тебя есть поля s.full_name / s.reason / s.when_dt / s.dob / s.phone_e164
                    start_dt = getattr(s, "when_dt", None)
                    if not start_dt:
                        raise RuntimeError("start_dt is missing")
                    dob_str = s.dob.strftime("%Y-%m-%d") if getattr(s, "dob", None) else "-"
                    phone_txt = getattr(s, "phone_e164", "-")
                    ok, info = create_event(
                        summary=f"{CLINIC_NAME}: {getattr(s,'full_name','Patient')} / {getattr(s,'reason','appointment')}",
                        start_dt=start_dt,
                        description=f"DOB: {dob_str}, Phone: {phone_txt}"
                    )
                    if ok:
                        reply = "Your appointment is created. I’ve sent you an SMS confirmation."
                        if HAVE_SMS and phone_txt and phone_txt.startswith("+"):
                            sms_body = f"{CLINIC_NAME}: {getattr(s,'reason','appointment')} on {start_dt}."
                            send_sms(phone_txt, sms_body)
                    else:
                        reply = f"Couldn’t create the calendar event: {info}"
                except Exception as e:
                    print(f"[calendar] error: {e}")
                    reply = "I can’t create the appointment right now. Please try again later."
            dialog.reset(call_sid)
            twiml_xml = create_twiml_response(reply)
            return Response(twiml_xml, mimetype="text/xml")

        if reply:
            twiml_xml = create_twiml_response(reply)
            return Response(twiml_xml, mimetype="text/xml")

        # fallback
        out = get_gpt_response(speech_text)
        twiml_xml = create_twiml_response(out)
        return Response(twiml_xml, mimetype="text/xml")

    # ===== РЕЖИМ GPT (FSM выключен) =====
    out = (f"You said: {speech_text}" if ECHO_MODE else get_gpt_response(speech_text))
    twiml_xml = create_twiml_response(out)
    return Response(twiml_xml, mimetype="text/xml")

# ---- Google OAuth ----
@app.route("/oauth/google/start")
def oauth_google_start():
    if not HAVE_GOOGLE or not build_flow:
        return "Google OAuth is not configured on the server yet.", 200
    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent",
    )
    session["google_oauth_state"] = state
    return redirect(auth_url)

@app.route("/oauth/google/callback")
def oauth_google_callback():
    if not HAVE_GOOGLE or not build_flow or not save_creds:
        return "Google OAuth is not configured on the server yet.", 200
    state = session.pop("google_oauth_state", None)
    flow = build_flow(state=state)
    auth_resp_url = request.url.replace("http://", "https://", 1)
    flow.fetch_token(authorization_response=auth_resp_url)
    save_creds(flow.credentials, "admin")
    return "✅ Google connected! You can return to the call."

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
