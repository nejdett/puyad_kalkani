# Puyad Kalkanı
# Uzak ajan iletişim katmanı
import httpx
import database
import config
from datetime import datetime


class PuyadAgentClient:
    def __init__(self, server_ip: str, server_port: int = 8000):
        self.base_url = f"http://{server_ip}:{server_port}"
        self.timeout = 15.0
        cfg = config.load_config()
        self.headers = {
            "X-Puyad-Key": cfg.get("AGENT_SHARED_SECRET", ""),
            "Content-Type": "application/json",
        }

    def check_agent_status(self) -> dict:
        try:
            resp = httpx.get(
                f"{self.base_url}/api/health",
                headers=self.headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return {"online": True, "data": resp.json()}
            return {"online": False, "error": f"HTTP {resp.status_code}"}
        except httpx.ConnectError:
            return {"online": False, "error": "Bağlantı kurulamadı"}
        except httpx.TimeoutException:
            return {"online": False, "error": "Zaman aşımı"}
        except Exception as e:
            return {"online": False, "error": str(e)}

    def trigger_remote_scan(self) -> dict:
        try:
            resp = httpx.get(
                f"{self.base_url}/api/scan",
                headers=self.headers,
                timeout=120.0,
            )
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def trigger_remote_fix(self, rule_id: str) -> dict:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/fix/{rule_id}",
                headers=self.headers,
                timeout=60.0,
            )
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def probe_all_servers() -> list[dict]:
    with database.get_connection() as conn:
        servers = conn.execute("SELECT * FROM servers").fetchall()

    import engine
    import remediation_engine
    results = []
    for srv in servers:
        srv = dict(srv)
        server_id = srv["id"]
        client = PuyadAgentClient(srv["ip_address"], srv["port"])
        status_info = client.check_agent_status()
        is_online = status_info["online"]
        new_status = "online" if is_online else "offline"

        scan_score = srv.get("last_score", 0) or 0

        if is_online and server_id == 1:
            try:
                scan_results = engine.scan_all()
                if scan_results:
                    ok = sum(1 for r in scan_results if r["status"] == "ok")
                    total = len(scan_results)
                    scan_score = int(ok / total * 100) if total > 0 else 0
                    remediation_engine.save_scan_to_history(scan_results, server_id=server_id)
            except Exception:
                pass
        elif is_online and server_id != 1:
            remote = client.trigger_remote_scan()
            if remote["success"]:
                data = remote["data"]
                scan_score = data.get("summary", {}).get("score", 0)

        with database.get_connection() as conn:
            conn.execute(
                "UPDATE servers SET status = ?, last_score = ? WHERE id = ?",
                (new_status, scan_score, server_id),
            )

        results.append({
            "id": server_id,
            "name": srv["name"],
            "ip_address": srv["ip_address"],
            "port": srv["port"],
            "status": new_status,
            "last_score": scan_score,
        })

    return results
