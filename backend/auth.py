# Puyad Kalkanı
# Kimlik doğrulama modülü
import json
import hashlib
import secrets
import bcrypt
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

CREDS_FILE         = Path(__file__).parent / "credentials.json"
TOKEN_EXPIRY_HOURS = 12
SECRET_KEY         = None  # ilk kullanımda üretilir

_bearer = HTTPBearer(auto_error=False)


def _get_secret() -> str:
    global SECRET_KEY
    if SECRET_KEY:
        return SECRET_KEY

    env_key = os.environ.get("PUYAD_SECRET_KEY")
    if env_key:
        SECRET_KEY = env_key
        return SECRET_KEY

    secret_file = Path(__file__).parent / ".secret_key"
    if secret_file.exists():
        SECRET_KEY = secret_file.read_text().strip()
    else:
        SECRET_KEY = secrets.token_hex(32)
        secret_file.write_text(SECRET_KEY)
        secret_file.chmod(0o600)
    return SECRET_KEY


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _load_credentials() -> dict:
    if CREDS_FILE.exists():
        try:
            with open(CREDS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    default = {
        "username":      "admin",
        "password_hash": _hash_password("puyad2026"),
        "created_at":    datetime.now().isoformat(),
    }
    _save_credentials(default)
    return default


def _save_credentials(creds: dict) -> None:
    with open(CREDS_FILE, "w") as f:
        json.dump(creds, f, indent=2)
    CREDS_FILE.chmod(0o600)


def create_token(username: str) -> str:
    import hmac, base64
    expiry      = (datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)).isoformat()
    payload     = f"{username}:{expiry}"
    payload_b64 = base64.b64encode(payload.encode()).decode()
    sig         = hmac.new(_get_secret().encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> Optional[str]:
    import hmac, base64
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected = hmac.new(_get_secret().encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload  = base64.b64decode(payload_b64).decode()
        username, expiry_str = payload.rsplit(":", 1)
        if datetime.fromisoformat(expiry_str) < datetime.now():
            return None
        return username
    except Exception:
        return None


def login(username: str, password: str) -> dict:
    creds = _load_credentials()
    stored_hash = creds["password_hash"]
    password_ok = False

    if stored_hash.startswith("$2"):
        password_ok = bcrypt.checkpw(password.encode(), stored_hash.encode())
    else:
        if hashlib.sha256(password.encode()).hexdigest() == stored_hash:
            password_ok = True
            creds["password_hash"] = _hash_password(password)
            _save_credentials(creds)

    if username != creds["username"] or not password_ok:
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı.")
    return {
        "access_token": create_token(username),
        "token_type":   "bearer",
        "expires_in":   TOKEN_EXPIRY_HOURS * 3600,
        "username":     username,
    }


def change_password(username: str, old_password: str, new_password: str) -> dict:
    creds = _load_credentials()
    stored_hash = creds["password_hash"]
    password_ok = False

    if stored_hash.startswith("$2"):
        password_ok = bcrypt.checkpw(old_password.encode(), stored_hash.encode())
    else:
        password_ok = hashlib.sha256(old_password.encode()).hexdigest() == stored_hash

    if username != creds["username"] or not password_ok:
        raise HTTPException(status_code=401, detail="Mevcut şifre hatalı.")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 8 karakter olmalıdır.")
    creds["password_hash"] = _hash_password(new_password)
    _save_credentials(creds)
    return {"success": True, "message": "Şifre başarıyla değiştirildi."}


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Kimlik doğrulama gerekli.")
    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş token.")
    return username
