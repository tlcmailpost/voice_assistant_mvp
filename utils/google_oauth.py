# utils/google_oauth.py
import os, json, pathlib, secrets
from typing import Optional
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDS_DIR = pathlib.Path("creds")
CREDS_DIR.mkdir(exist_ok=True)

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "")

def _client_config():
    return {
        "web": {
            "client_id": CLIENT_ID,
            "project_id": "voice-assistant",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
        }
    }

def build_flow(state: Optional[str] = None) -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state or secrets.token_urlsafe(16),
    )

def save_creds(creds: Credentials, key: str = "admin") -> None:
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    (CREDS_DIR / f"{key}.json").write_text(json.dumps(data))

def load_creds(key: str = "admin") -> Optional[Credentials]:
    p = CREDS_DIR / f"{key}.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return Credentials(**data)
