# app.py — GPT with external system prompt
import os
from flask import Flask, request, Response, redirect, session
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"

# --- Secret config ---
HARD_SECRET = "vK7!qD9#sYp$3Lx@0ZnF4hGt8Rb^2MwUjE1oCk&Va5Tr*NpXgHdWlQfZy!BmRs"
env_secret = (os.environ.get("FLASK_SECRET_KEY") or "").strip()
final_secret = env_secret or HARD_SECRET
app.secret_key = final_secret
app.config["SECRET_KEY"] = final_secret
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE="Lax")

print(f"[flask] SECRET from env? {'yes' if env_secret else 'no (using hard)'}")

# ---------------- Imports ----------------
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

# --- Optional FSM (dialog_medical) ---
try:
    from utils.dialog_medical import MedDialog
    HAVE_MED = True
except Exception as e:
    print(f"[boot] dialog_medical not available: {e}")
    MedDialog = None
    HAVE_MED = False

# --- Optional Google Calendar ---
try:
    from utils.google_oauth import build_flow, save_creds, load_creds
    from utils.calendar import create_event
    HAVE_GOOGLE = True
except Exception as e:
    print(f"[boot] google calendar not available: {e}")
    build_flow = save_creds = load_creds = create_event = None
    HAVE_GOOGLE = False

# --- Optional SMS ---
try:
    from utils.sms import send_sms
    HAVE_SMS = True
except Exception as e:
    print(f"[boot] sms not available: {e}")
    def send_sms(*args, **kwargs): return False
    HAVE_SMS = False

# ---------------- Settings ----------------
ECHO_MODE = os.environ.get("ECHO_MODE", "0") == "1"
APP_BASE = os.environ.get("APP_BASE_URL", "https://voice-assistant-mvp-9.onrender.com")
CLINIC_NAME = os.environ.get("CLINIC_NAME", "MedVoice Clinic")

# ---------------- Routes ----------------
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

    # === No speech → trigger first greeting ===
    if not speech_text:
        twiml_xml = create_twiml_response(None, first=True)
        return Response(twiml_xml, mimetype="text/xml")

    # === GPT mode ===
    out = (
        f"You said: {speech_text}"
        if ECHO_MODE
        else get_gpt_response(speech_text, system_prompt=SYSTEM_PROMPT)
    )
    twiml_xml = create_twiml_response(out)
    return Response(twiml_xml, mimetype="text/xml")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
