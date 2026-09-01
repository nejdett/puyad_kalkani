# Puyad Kalkanı
# Düzeltme motoru - snapshot + geçmiş yönetimi
import database
import backup_manager
from engine import run_command, load_rules


def fix_with_snapshot(rule_id: str, auto_snapshot: bool = True, server_id: int = 1) -> dict:
    rules = load_rules()
    rule = next((r for r in rules if r["id"] == rule_id), None)

    if not rule:
        return {
            "success": False,
            "message": f"'{rule_id}' ID'li kural bulunamadı.",
            "output": "",
            "snapshot_id": None
        }

    snapshot_id = None

    if auto_snapshot:
        snap = backup_manager.create_snapshot(
            label=f"Fix öncesi: {rule['name'][:50]}"
        )
        if snap.get("success"):
            snapshot_id = snap["snapshot_id"]

    result = run_command(rule["fix_command"], timeout=120)
    success = result["success"]
    output = result["stdout"] or result["stderr"]

    with database.get_connection() as conn:
        conn.execute(
            """INSERT INTO fix_history (rule_id, rule_name, status, output, snapshot_id, server_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                rule_id,
                rule["name"],
                "success" if success else "failed",
                output[:2000],
                snapshot_id,
                server_id
            )
        )

    return {
        "success": success,
        "message": "Düzeltme başarıyla uygulandı." if success else "Düzeltme sırasında hata oluştu.",
        "output": output,
        "snapshot_id": snapshot_id
    }


def get_fix_history(limit: int = 50) -> list[dict]:
    with database.get_connection() as conn:
        rows = conn.execute(
            """SELECT id, rule_id, rule_name, status, output, snapshot_id, created_at
               FROM fix_history ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def save_scan_to_history(results: list[dict], server_id: int = 1) -> int:
    total = len(results)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    warnings = sum(1 for r in results if r["status"] == "warning")
    score = int((ok_count / total * 100)) if total > 0 else 0

    with database.get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO scan_history (total, warnings, ok_count, score, server_id)
               VALUES (?, ?, ?, ?, ?)""",
            (total, warnings, ok_count, score, server_id)
        )
        scan_id = cursor.lastrowid

        conn.executemany(
            """INSERT INTO scan_results (scan_id, rule_id, rule_name, status, output)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (scan_id, r["id"], r["name"], r["status"], r.get("output", "")[:1000])
                for r in results
            ]
        )

    return scan_id


def get_scan_history(limit: int = 20) -> list[dict]:
    with database.get_connection() as conn:
        rows = conn.execute(
            """SELECT id, total, warnings, ok_count, score, created_at
               FROM scan_history ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_score_trend() -> list[dict]:
    with database.get_connection() as conn:
        rows = conn.execute(
            """SELECT score, created_at FROM scan_history
               ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()
    return [dict(r) for r in reversed(rows)]
