# Puyad Kalkanı
# APScheduler tabanlı periyodik tarama
import json
import threading
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import engine
import remediation_engine
import database

CONFIG_FILE = Path(__file__).parent / "scheduler_config.json"
ALERT_FILE  = Path(__file__).parent / "scheduler_alerts.json"


CRITICAL_SCORE_THRESHOLD = 60

_scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
_lock = threading.Lock()


def _default_config() -> dict:
    return {
        "enabled": False,
        "interval": "weekly",   # "daily" | "weekly" | "monthly"
        "day_of_week": "mon",
        "hour": 3,
        "minute": 0,
        "last_run": None,
        "next_run": None,
    }


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                defaults = _default_config()
                for k, v in defaults.items():
                    cfg.setdefault(k, v)
                return cfg
        except Exception:
            pass
    return _default_config()


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_alerts() -> list[dict]:
    """Return unread alerts."""
    if not ALERT_FILE.exists():
        return []
    try:
        with open(ALERT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def add_alert(message: str, score: int) -> None:
    alerts = get_alerts()
    alerts.insert(0, {
        "message": message,
        "score": score,
        "created_at": datetime.now().isoformat(),
        "read": False
    })
    alerts = alerts[:20]  # keep only the last 20 alerts
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, indent=2, ensure_ascii=False)


def mark_alerts_read() -> None:
    alerts = get_alerts()
    for a in alerts:
        a["read"] = True
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, indent=2, ensure_ascii=False)


def get_unread_count() -> int:
    return sum(1 for a in get_alerts() if not a.get("read", True))


def _run_scheduled_scan() -> None:
    """Scheduled scan task — runs in a background thread."""
    with _lock:
        try:
            print(f"[Scheduler] Scheduled scan started: {datetime.now().isoformat()}")
            results = engine.scan_all()
            scan_id = remediation_engine.save_scan_to_history(results)

            total    = len(results)
            ok_count = sum(1 for r in results if r["status"] == "ok")
            score    = int((ok_count / total * 100)) if total > 0 else 0

            cfg = load_config()
            cfg["last_run"] = datetime.now().isoformat()
            save_config(cfg)

            if score < CRITICAL_SCORE_THRESHOLD:
                warnings = total - ok_count
                add_alert(
                    f"Tarama tamamlandı. Güvenlik skoru kritik: {score}/100. "
                    f"{warnings} uyari tespit edildi.",
                    score
                )
                print(f"[Scheduler] CRITICAL: Score {score}/100")
            else:
                print(f"[Scheduler] Scan complete. Score: {score}/100")

        except Exception as e:
            print(f"[Scheduler] Error: {str(e)}")
            add_alert(f"Tarama başarısız: {str(e)}", 0)


def _build_trigger(cfg: dict) -> CronTrigger:
    interval = cfg.get("interval", "weekly")
    hour = cfg.get("hour", 3)
    minute = cfg.get("minute", 0)

    if interval == "daily":
        return CronTrigger(hour=hour, minute=minute)
    elif interval == "monthly":
        return CronTrigger(day=1, hour=hour, minute=minute)
    else:  # weekly
        return CronTrigger(
            day_of_week=cfg.get("day_of_week", "mon"),
            hour=hour,
            minute=minute
        )


def start_scheduler() -> None:
    """Start the APScheduler instance and apply any saved schedule."""
    if not _scheduler.running:
        _scheduler.start()

    cfg = load_config()
    if cfg.get("enabled"):
        _apply_schedule(cfg)


def _apply_schedule(cfg: dict) -> None:
    """Replace the existing job with a new one based on current config."""
    try:
        _scheduler.remove_job("auto_scan")
    except Exception:
        pass

    if cfg.get("enabled"):
        trigger = _build_trigger(cfg)
        job = _scheduler.add_job(
            _run_scheduled_scan,
            trigger=trigger,
            id="auto_scan",
            replace_existing=True
        )
        cfg["next_run"] = job.next_run_time.isoformat() if job.next_run_time else None
        save_config(cfg)


def update_schedule(enabled: bool, interval: str = "weekly",
                    day_of_week: str = "mon", hour: int = 3, minute: int = 0) -> dict:
    """Update schedule settings and return the updated config."""
    cfg = load_config()
    cfg["enabled"] = enabled
    cfg["interval"] = interval
    cfg["day_of_week"] = day_of_week
    cfg["hour"] = hour
    cfg["minute"] = minute

    _apply_schedule(cfg)
    save_config(cfg)
    return cfg


def run_now() -> dict:
    """Trigger a scheduled scan immediately in a background thread."""
    t = threading.Thread(target=_run_scheduled_scan, daemon=True)
    t.start()
    return {"success": True, "message": "Tarama arka planda başlatıldı."}


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
