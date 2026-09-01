# Puyad Kalkanı v2.1.0
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


import engine
import backup_manager
import remediation_engine
import log_monitor
import pdf_reporter
import scheduler
import honeypot
import auth
import config
import agent_client
import database
import forensic_manager
import network_mapper
import telegram_manager
import cve_analyzer

app = FastAPI(
    title="Puyad Kalkani API",
    version="2.1.0",
    docs_url="/docs",
    redoc_url=None,
)

import socket


def _get_local_ips() -> list[str]:
    """Kullanilan makinenin yerel IP adreslerini tespit eder."""
    extras = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        extras.append(f"http://{s.getsockname()[0]}:3000")
        extras.append(f"http://{s.getsockname()[0]}:5173")
        s.close()
    except Exception:
        pass
    return extras


CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
] + _get_local_ips()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    scheduler.start_scheduler()
    honeypot.restore_from_config()
    # telegram polling baslat
    telegram_manager.PuyadTelegramManager.start_polling()
    # migrate eski veritabanlarını
    from migrate import migrate
    migrate()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown_scheduler()


# ── Modeller ─────────────────────────────────────────────────────────────────

class RuleModel(BaseModel):
    id: str
    name: str
    category: str
    severity: str
    check_command: str
    fix_command: str
    description: str

class SnapshotCreateModel(BaseModel):
    label: Optional[str] = ""

class FixModel(BaseModel):
    auto_snapshot: Optional[bool] = True
    server_id: Optional[int] = 1

class SchedulerConfigModel(BaseModel):
    enabled: bool
    interval: Optional[str] = "weekly"
    day_of_week: Optional[str] = "mon"
    hour: Optional[int] = 3
    minute: Optional[int] = 0

class LoginModel(BaseModel):
    username: str
    password: str

class ChangePasswordModel(BaseModel):
    username: str
    old_password: str
    new_password: str

class HoneypotModel(BaseModel):
    port: int
    service: Optional[str] = "custom"
    label: Optional[str] = ""

class ServerModel(BaseModel):
    name: str
    ip_address: str
    port: Optional[int] = 8000

class ConfigUpdateModel(BaseModel):
    RUN_MODE: Optional[str] = None
    AGENT_SHARED_SECRET: Optional[str] = None
    TELEGRAM_ENABLED: Optional[bool] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

class ScanModel(BaseModel):
    server_id: Optional[int] = 1

class ScanPostModel(BaseModel):
    server_id: Optional[int] = 1

class ForensicTriggerModel(BaseModel):
    server_id: Optional[int] = 1
    trigger_reason: Optional[str] = "Manual Trigger"

class TelegramTestModel(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None

class TelegramConfigModel(BaseModel):
    TELEGRAM_ENABLED: Optional[bool] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None


# ── Config ───────────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    return config.load_config()


@app.patch("/api/config")
def update_cfg(body: ConfigUpdateModel):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return config.update_config(updates)


# ── Servers ──────────────────────────────────────────────────────────────────

@app.get("/api/servers")
def list_servers():
    with database.get_connection() as conn:
        servers = conn.execute("SELECT * FROM servers ORDER BY id").fetchall()
    return {"servers": [dict(s) for s in servers]}


@app.post("/api/servers")
def add_server(body: ServerModel):
    with database.get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO servers (name, ip_address, port) VALUES (?, ?, ?)",
                (body.name, body.ip_address, body.port)
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "message": "Sunucu eklendi."}


@app.delete("/api/servers/{server_id}")
def delete_server(server_id: int):
    if server_id == 1:
        raise HTTPException(status_code=400, detail="Yerel sunucu silinemez.")
    with database.get_connection() as conn:
        result = conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Sunucu bulunamadı.")
    return {"success": True, "message": "Sunucu silindi."}


@app.get("/api/servers/probe-all")
def probe_all():
    results = agent_client.probe_all_servers()
    return {"results": results}


# ── Scan ─────────────────────────────────────────────────────────────────────

def _run_local_scan(server_id: int = 1) -> dict:
    try:
        results = engine.scan_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tarama sırasında hata: {str(e)}")

    if not results:
        return {"summary": {"total": 0, "warnings": 0, "ok": 0, "score": 0}, "results": []}

    total = len(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    scan_id = remediation_engine.save_scan_to_history(results, server_id=server_id)
    summary = {
        "total": total,
        "warnings": sum(1 for r in results if r["status"] == "warning"),
        "ok": ok,
        "score": int(ok / total * 100) if total > 0 else 0,
        "scan_id": scan_id,
    }
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE servers SET last_score = ? WHERE id = ?",
            (summary["score"], server_id)
        )
    return {"summary": summary, "results": results}


def _run_remote_scan(server_id: int) -> dict:
    with database.get_connection() as conn:
        srv = conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    if not srv:
        raise HTTPException(status_code=404, detail="Sunucu bulunamadı.")

    client = agent_client.PuyadAgentClient(srv["ip_address"], srv["port"])
    remote_result = client.trigger_remote_scan()
    if not remote_result["success"]:
        raise HTTPException(status_code=502, detail=remote_result.get("error", "Uzak tarama başarısız"))

    data = remote_result["data"]
    results = data.get("results", [])
    summary = data.get("summary", {})

    if results:
        scan_id = remediation_engine.save_scan_to_history(results, server_id=server_id)
        summary["scan_id"] = scan_id

    with database.get_connection() as conn:
        conn.execute(
            "UPDATE servers SET last_score = ? WHERE id = ?",
            (summary.get("score", 0), server_id)
        )

    return {"summary": summary, "results": results}


# POST /api/scan GET /api/scan/{rule_id} öncesinde tanımlı olmalı
@app.post("/api/scan")
def scan_post(body: ScanPostModel):
    server_id = body.server_id or 1
    if server_id == 1:
        return _run_local_scan(server_id=1)
    return _run_remote_scan(server_id)


@app.get("/api/scan")
def scan_get(server_id: int = 1):
    if server_id == 1:
        return _run_local_scan(server_id=1)
    return _run_remote_scan(server_id)


@app.get("/api/scan/{rule_id}")
def scan_single(rule_id: str):
    result = engine.check_single_rule(rule_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"'{rule_id}' ID'li kural bulunamadı.")
    return result


# ── Fix ──────────────────────────────────────────────────────────────────────

@app.post("/api/fix/{rule_id}")
def fix(rule_id: str, body: FixModel = FixModel()):
    if body.server_id == 1:
        result = remediation_engine.fix_with_snapshot(rule_id=rule_id, auto_snapshot=body.auto_snapshot)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result

    # uzak sunucu
    with database.get_connection() as conn:
        srv = conn.execute("SELECT * FROM servers WHERE id = ?", (body.server_id,)).fetchone()
    if not srv:
        raise HTTPException(status_code=404, detail="Sunucu bulunamadı.")

    client = agent_client.PuyadAgentClient(srv["ip_address"], srv["port"])
    remote_result = client.trigger_remote_fix(rule_id)
    if not remote_result["success"]:
        raise HTTPException(status_code=502, detail=remote_result.get("error", "Uzak düzeltme başarısız"))
    return remote_result["data"]


# ── Ignore ───────────────────────────────────────────────────────────────────

@app.post("/api/ignore/{rule_id}")
def ignore(rule_id: str):
    result = engine.ignore_rule(rule_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.delete("/api/ignore/{rule_id}")
def unignore(rule_id: str):
    return engine.unignore_rule(rule_id)


@app.get("/api/ignored")
def get_ignored():
    return {"ignored": engine.load_ignored()}


# ── Rules ────────────────────────────────────────────────────────────────────

@app.get("/api/rules")
def get_rules():
    rules = engine.load_rules()
    return {"rules": rules, "total": len(rules)}


@app.post("/api/rules")
def add_rule(rule: RuleModel):
    result = engine.add_rule(rule.model_dump())
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@app.put("/api/rules/{rule_id}")
def update_rule(rule_id: str, body: RuleModel):
    result = engine.update_rule(rule_id, body.model_dump())
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: str):
    result = engine.delete_rule(rule_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ── Snapshots ────────────────────────────────────────────────────────────────

@app.get("/api/snapshots")
def list_snapshots():
    return {"snapshots": backup_manager.list_snapshots()}


@app.post("/api/snapshots")
def create_snapshot(body: SnapshotCreateModel):
    result = backup_manager.create_snapshot(label=body.label)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Snapshot alinamadi."))
    return result


@app.post("/api/snapshots/{snapshot_id}/rollback")
def rollback(snapshot_id: str):
    result = backup_manager.rollback_snapshot(snapshot_id)
    return result


@app.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: str):
    result = backup_manager.delete_snapshot(snapshot_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ── History ──────────────────────────────────────────────────────────────────

@app.get("/api/history/fixes")
def fix_history(limit: int = 50):
    return {"history": remediation_engine.get_fix_history(limit)}


@app.get("/api/history/scans")
def scan_history(limit: int = 20):
    return {"history": remediation_engine.get_scan_history(limit)}


@app.get("/api/history/trend")
def score_trend():
    return {"trend": remediation_engine.get_score_trend()}


# ── Logs ─────────────────────────────────────────────────────────────────────

@app.get("/api/logs/tail")
def log_tail(lines: int = 100):
    return {"logs": log_monitor.get_log_tail(lines)}


@app.get("/api/logs/stream")
async def log_stream(lines_back: int = 50):
    async def safe_stream():
        try:
            async for chunk in log_monitor.tail_log_stream(lines_back):
                yield chunk
        except Exception as e:
            yield f"data: Akis hatasi: {e}|LEVEL:error\n\n"

    return StreamingResponse(
        safe_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/logs/active")
def active_log():
    try:
        source = log_monitor.get_log_source()
        return {"path": source["path"], "type": source["type"], "available": source["type"] != "none"}
    except Exception as e:
        return {"path": None, "type": "none", "available": False, "error": str(e)}


# ── Network ─────────────────────────────────────────────────────────────────

@app.get("/api/network/topology")
def network_topology(server_id: int = 1):
    topology = network_mapper.PuyadNetworkMapper.get_active_connections_map()
    return topology


@app.get("/api/network/attacks")
def network_attacks():
    attacks = network_mapper.PuyadNetworkMapper.get_attack_origins()
    return {"attacks": attacks}


@app.get("/api/network/geoip/{ip_address}")
def network_geoip(ip_address: str):
    geo = network_mapper.PuyadNetworkMapper.get_geoip_data(ip_address)
    return geo


# ── Forensic ────────────────────────────────────────────────────────────────

@app.post("/api/forensic/trigger")
def forensic_trigger(body: ForensicTriggerModel):
    evidence = forensic_manager.PuyadForensicManager.collect_evidence(
        trigger_reason=body.trigger_reason,
        server_id=body.server_id,
    )
    return {"success": True, "message": "Adli kanıt toplandı.", "evidence": evidence}


@app.get("/api/forensic/history")
def forensic_history(server_id: int = None, limit: int = 50):
    history = forensic_manager.PuyadForensicManager.get_history(server_id=server_id, limit=limit)
    return {"history": history}


@app.get("/api/forensic/evidence/{evidence_id}")
def forensic_evidence(evidence_id: int):
    evidence = forensic_manager.PuyadForensicManager.get_evidence(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Adli kanıt bulunamadı.")
    return evidence


@app.delete("/api/forensic/evidence/{evidence_id}")
def forensic_delete(evidence_id: int):
    result = forensic_manager.PuyadForensicManager.delete_evidence(evidence_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ── Telegram ────────────────────────────────────────────────────────────────

@app.post("/api/telegram/test")
def telegram_test(body: TelegramTestModel):
    import httpx as _httpx
    cfg = config.load_config()
    token = body.bot_token or cfg.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = body.chat_id or cfg.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Bot Token ve Chat ID gerekli.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = _httpx.post(url, json={
            "chat_id": chat_id,
            "text": "Puyad Kalkanı test mesajı. Bağlantı başarılı.",
        }, timeout=10)

        if resp.status_code == 200:
            return {"success": True, "message": "Test mesajı gönderildi."}

        # Telegram API hata detayını çek
        try:
            tg_error = resp.json()
            err_desc = tg_error.get("description", resp.text)
            err_code = tg_error.get("error_code", resp.status_code)
        except Exception:
            err_desc = resp.text
            err_code = resp.status_code

        # HTTP status koduna göre anlamlı mesaj
        error_map = {
            400: f"Geçersiz istek: {err_desc}",
            401: f"Geçersiz token: {err_desc}",
            403: f"Bot engellendi veya yetkisi yok: {err_desc}",
            404: f"Chat bulunamadı: {err_desc}",
        }
        detail = error_map.get(err_code, f"Telegram API hatası ({err_code}): {err_desc}")

        raise HTTPException(status_code=400, detail=detail)
    except HTTPException:
        raise
    except _httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Telegram API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin.")
    except _httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Telegram API zaman aşımına uğradı. Tekrar deneyin.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {str(e)}")


@app.get("/api/telegram/pending")
def telegram_pending():
    actions = telegram_manager.PuyadTelegramManager.get_pending_actions()
    return {"pending": actions}


@app.post("/api/telegram/approve/{approval_token}")
def telegram_approve(approval_token: str):
    result = telegram_manager.PuyadTelegramManager.approve_action(approval_token)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/telegram/reject/{approval_token}")
def telegram_reject(approval_token: str):
    result = telegram_manager.PuyadTelegramManager.reject_action(approval_token)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── CVE / Zafiyet Analizi ───────────────────────────────────────────────────

@app.get("/api/cve/scan")
def cve_scan(server_id: int = 1, use_osv: bool = False):
    result = cve_analyzer.run_cve_scan(use_osv=use_osv, server_id=server_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.get("/api/cve/history")
def cve_history(server_id: int = None, limit: int = 20):
    history = cve_analyzer.get_scan_history(server_id=server_id, limit=limit)
    return {"history": history}


@app.get("/api/cve/history/{scan_id}")
def cve_history_detail(scan_id: int):
    detail = cve_analyzer.get_scan_detail(scan_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")
    return detail


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.1.0"}




# ── PDF Report ───────────────────────────────────────────────────────────────

@app.get("/api/report/pdf")
def download_pdf(scan_id: int = None):
    try:
        pdf_bytes = pdf_reporter.generate_report(scan_id=scan_id)
        filename = f"puyad-kalkani-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF rapor üretilemedi: {e}")


# ── Scheduler ────────────────────────────────────────────────────────────────

@app.get("/api/scheduler/config")
def get_scheduler_config():
    return scheduler.load_config()


@app.post("/api/scheduler/config")
def set_scheduler_config(body: SchedulerConfigModel):
    return scheduler.update_schedule(
        enabled=body.enabled, interval=body.interval,
        day_of_week=body.day_of_week, hour=body.hour, minute=body.minute,
    )


@app.post("/api/scheduler/run-now")
def run_scan_now():
    return scheduler.run_now()


@app.get("/api/scheduler/alerts")
def get_alerts():
    return {"alerts": scheduler.get_alerts(), "unread_count": scheduler.get_unread_count()}


@app.post("/api/scheduler/alerts/read")
def mark_read():
    scheduler.mark_alerts_read()
    return {"success": True}


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(body: LoginModel):
    return auth.login(body.username, body.password)


@app.post("/api/auth/change-password")
def change_password(body: ChangePasswordModel, current_user: str = Depends(auth.get_current_user)):
    return auth.change_password(body.username, body.old_password, body.new_password)


@app.get("/api/auth/me")
def me(current_user: str = Depends(auth.get_current_user)):
    return {"username": current_user}


# ── HoneyPot ─────────────────────────────────────────────────────────────────

@app.get("/api/honeypot/active")
def honeypot_list():
    return {"pots": honeypot.list_active()}


@app.post("/api/honeypot/start")
def honeypot_start(body: HoneypotModel):
    if not (1 <= body.port <= 65535):
        raise HTTPException(status_code=400, detail="Geçersiz port numarası.")
    if body.port in (8000, 3000, 80, 443):
        raise HTTPException(status_code=400, detail="Bu port sistem tarafından kullanılmaktadır.")
    result = honeypot.start_honeypot(body.port, body.service, body.label)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.delete("/api/honeypot/stop/{port}")
def honeypot_stop(port: int):
    result = honeypot.stop_honeypot(port)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.get("/api/honeypot/hits")
def honeypot_hits(limit: int = 100, since_id: int = 0):
    if since_id > 0:
        return {"hits": honeypot.get_hits_since(since_id, limit)}
    return {"hits": honeypot.get_hits(limit)}


