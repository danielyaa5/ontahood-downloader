# dfr/auth.py
# OAuth and Drive service helpers

import os
from pathlib import Path
from typing import Dict, Tuple

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import drive_fetch_resilient as dfr


def _resolve_credentials_path(p: str) -> str:
    pth = Path(p)
    if pth.is_file():
        return str(pth)
    pth2 = dfr.SUPPORT_DIR / Path(p).name
    if pth2.is_file():
        return str(pth2)
    try:
        base = Path(getattr(dfr.sys, "_MEIPASS", Path(__file__).resolve().parent))
    except Exception:
        base = Path(__file__).resolve().parent
    pth3 = base / Path(p).name
    if pth3.is_file():
        return str(pth3)
    raise FileNotFoundError(
        f"Could not find {p!r}. Looked in: {Path(p).resolve()}, {pth2}, {pth3}"
    )


def get_service_and_creds(token_path: str, credentials_path: str):
    from google.auth.transport.requests import Request
    token_path = str(Path(token_path))
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, dfr.SCOPES)
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                dfr.logging.info(dfr.L("Refreshing stored credentials...", "Menyegarkan kredensial tersimpan..."))
                creds.refresh(Request())
            else:
                raise Exception("Need fresh auth")
        except Exception:
            dfr.logging.info(dfr.L("Launching browser for Google OAuth...", "Membuka browser untuk OAuth Google..."))
            cred_path_resolved = _resolve_credentials_path(credentials_path)
            flow = InstalledAppFlow.from_client_secrets_file(cred_path_resolved, dfr.SCOPES)
            creds = flow.run_local_server(port=0)
        Path(token_path).parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
            dfr.logging.info(dfr.L(f"Wrote token file: {token_path}", f"Menulis token file: {token_path}"))
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service, creds


def get_service_if_token_valid(token_path: str, credentials_path: str):
    try:
        from google.auth.transport.requests import Request
        token_path = str(Path(token_path))
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, dfr.SCOPES)
        if not creds:
            return None, None
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    return None, None
            else:
                return None, None
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return service, creds
    except Exception:
        return None, None


def try_get_account_info(token_path: str, credentials_path: str) -> Dict:
    svc, _ = get_service_if_token_valid(token_path, credentials_path)
    if svc is None:
        return {}
    return get_account_info(svc)


def get_account_info(service) -> Dict:
    try:
        about = service.about().get(fields="user(emailAddress,displayName)").execute()
        u = about.get("user") or {}
        return {"email": u.get("emailAddress"), "name": u.get("displayName")}
    except Exception:
        return {}
