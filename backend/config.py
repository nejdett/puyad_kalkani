# Puyad Kalkanı
# Konfigürasyon yönetimi
import json
import os
import shutil
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

DEFAULTS = {
    "RUN_MODE": "standalone",
    "AGENT_SHARED_SECRET": "puyad-secure-key-degistirin",
    "TELEGRAM_ENABLED": False,
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
}


def _ensure_config_file() -> None:
    """config.json dosyasinin dosya oldugundan emin olur."""
    try:
        if CONFIG_FILE.is_dir():
            # Docker bind mount dizin olarak olusturmus olabilir
            shutil.rmtree(str(CONFIG_FILE))
    except Exception:
        pass
    if not CONFIG_FILE.exists():
        save_config(DEFAULTS.copy())


def save_config(cfg: dict) -> None:
    """Konfigürasyonu config.json dosyasına yazar."""
    _ensure_config_file()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except PermissionError:
        # Yazma izni yoksa env degiskeninden okumaya don
        pass
    except Exception:
        pass


def load_config() -> dict:
    """Mevcut konfigürasyonu yükler. Dosya yoksa varsayılanları döndürür."""
    _ensure_config_file()
    if CONFIG_FILE.exists() and CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for k, v in DEFAULTS.items():
                    cfg.setdefault(k, v)
                return cfg
        except (json.JSONDecodeError, Exception):
            # Hatali JSON ise sifirla
            pass
    # Ortam degiskenlerinden de oku
    env_cfg = DEFAULTS.copy()
    for key in DEFAULTS:
        env_val = os.environ.get(f"PUYAD_{key}")
        if env_val is not None:
            if isinstance(DEFAULTS[key], bool):
                env_cfg[key] = env_val.lower() in ("true", "1", "yes")
            else:
                env_cfg[key] = env_val
    return env_cfg


def update_config(updates: dict) -> dict:
    """Mevcut konfigürasyonu günceller ve kaydeder."""
    cfg = load_config()
    cfg.update({k: v for k, v in updates.items() if v is not None})
    save_config(cfg)
    return cfg
