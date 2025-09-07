import os
from flask import Flask, request, Response, redirect
from utils.openai_gpt import get_gpt_response
from utils.twilio_response import create_twiml_response
from utils.dialog_medical import MedDialog
from utils.calendar import create_event  # из предыдущей интеграции Google
from utils.google_oauth import build_flow, save_creds, load_creds

app = Flask(__name__)

ECHO_MODE = os.environ.get("ECHO_MODE", "0") == "1"
APP_BASE = os.environ.get("APP_BASE_URL", "https://voice-assistant-mvp-9.onrender.com")
CLINIC_NAME = os.environ.get("CLINIC_NAME", "Клиника")

dialog = MedDialog()  # простое хранилище сессий по CallSid

@app.route("/", methods=["GET"])
def home():
    return "✅ Voice Assistant is running!"

@app.route("/twilio-voice", methods=["GET", "POST"])
def twilio_voice():
    if request.method == "GET":
        twiml_xml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="ru-RU" voice="alice">Webhook готов. Используйте POST для распознавания речи.</Say></Response>'
        return Response(twiml_xml, mimetype="text/xml")

    call_sid = (request.form.get("CallSid") or "").strip()
    from_number = (request.form.get("From") or "").strip()
    speech_text = (request.form.get("SpeechResult") or request.values.get("SpeechResult") or "").strip()

    print(f"[Twilio] CallSid={call_sid} From={from_number} Speech='{speech_text}'")

    # Если нет текста — первичный Gather
    if not speech_text:
        twiml_xml = create_twiml_response(None)
        return Response(twiml_xml, mimetype="text/xml")

    # --- Ветка медицинской записи (state machine) ---
    # Если пользователь начал явно сценарий записи (или просто идём по шагам)
    # Пробуем применить диалог
    reply, done, create_flag = dialog.handle(call_sid, speech_text, from_number)

    if create_flag:
        # Создаём событие в календаре, если Google подключен
        if not load_creds("admin"):
            reply = f"Чтобы завершить запись, подключите Google: {APP_BASE}/oauth/google/start"
        else:
            s = dialog.get(call_sid).data
            from datetime import datetime
            from dateutil import parser as dtparser  # если нет dateutil — можно через datetime.fromisoformat
            start_dt = dtparser.parse(s["datetime_iso"])
            ok, info = create_event(
                summary=f"{CLINIC_NAME}: {s.get('full_name','Пациент')} / {s.get('reason','приём')}",
                start_dt=start_dt,
                description=f"DOB: {s.get('dob_str','-')}, Phone: {s.get('phone','-')}"
            )
            if ok:
                reply = "Запись создана. Ссылка отправлена в SMS."
                # Отправим SMS пациенту
                from utils.sms import send_sms
                sms_body = f"{CLINIC_NAME}: запись {s.get('datetime_str')} — {s.get('reason','приём')}."
                send_sms(s.get("phone",""), sms_body)
            else:
                reply = f"Не удалось создать событие: {info}"

        # Сессию можно сбросить
        dialog.reset(call_sid)
        twiml_xml = create_twiml_response(reply)
        return Response(twiml_xml, mimetype="text/xml")

    # Если диалог ещё идёт — просто задаём следующий вопрос/уточняем
    if reply:
        twiml_xml = create_twiml_response(reply)
        return Response(twiml_xml, mimetype="text/xml")

    # --- Обычный Q&A (если не попали в сценарий) ---
    if ECHO_MODE:
        out = f"Вы сказали: {speech_text}"
    else:
        out = get_gpt_response(speech_text)

    twiml_xml = create_twiml_response(out)
    return Response(twiml_xml, mimetype="text/xml")

# ---- Google OAuth ----
@app.route("/oauth/google/start")
def oauth_google_start():
    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return redirect(auth_url)

@app.route("/oauth/google/callback")
def oauth_google_callback():
    flow = build_flow()
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    save_creds(creds, "admin")
    return "✅ Google подключён! Можете вернуться к звонку и сказать: «Запиши меня завтра в 10 утра на чистку зубов»."



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

