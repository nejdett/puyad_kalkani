# Puyad Kalkanı
# Adli kanıt toplama motoru
import json
import subprocess
from datetime import datetime

import database


def _run(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


class PuyadForensicManager:

    @staticmethod
    def collect_evidence(trigger_reason: str, server_id: int = 1) -> dict:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        active_connections = _run("ss -tupn 2>/dev/null || netstat -tupn 2>/dev/null")
        running_processes = _run("ps aux --sort=-%cpu | head -n 20")
        logged_users = _run("who 2>/dev/null") + "\n---\n" + _run("w 2>/dev/null")
        last_logins = _run("last -n 10 2>/dev/null")
        listening_ports = _run("ss -tuln 2>/dev/null")

        evidence = {
            "timestamp": ts,
            "trigger_reason": trigger_reason,
            "server_id": server_id,
            "active_connections": active_connections,
            "running_processes": running_processes,
            "logged_users": logged_users,
            "last_logins": last_logins,
            "listening_ports": listening_ports,
        }

        with database.get_connection() as conn:
            conn.execute(
                "INSERT INTO forensic_history (server_id, trigger_reason, evidence_json) VALUES (?, ?, ?)",
                (server_id, trigger_reason, json.dumps(evidence, ensure_ascii=False))
            )

        return evidence

    @staticmethod
    def get_history(server_id: int = None, limit: int = 50) -> list[dict]:
        with database.get_connection() as conn:
            if server_id:
                rows = conn.execute(
                    "SELECT id, server_id, trigger_reason, created_at FROM forensic_history "
                    "WHERE server_id = ? ORDER BY created_at DESC LIMIT ?",
                    (server_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, server_id, trigger_reason, created_at FROM forensic_history "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_evidence(evidence_id: int) -> dict | None:
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM forensic_history WHERE id = ?", (evidence_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["evidence_data"] = json.loads(result["evidence_json"])
        return result

    @staticmethod
    def delete_evidence(evidence_id: int) -> dict:
        with database.get_connection() as conn:
            result = conn.execute("DELETE FROM forensic_history WHERE id = ?", (evidence_id,))
            if result.rowcount == 0:
                return {"success": False, "message": "Kayıt bulunamadı."}
        return {"success": True, "message": "Adli kanıt kaydı silindi."}
