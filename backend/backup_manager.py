# Puyad Kalkanı
# /etc snapshot ve geri yükleme
import os
import uuid
import tarfile
import shutil
from datetime import datetime
from pathlib import Path

import database

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"
SNAPSHOT_DIR.mkdir(exist_ok=True)

BACKUP_PATHS = ["/etc"]


def create_snapshot(label: str = "") -> dict:
    snap_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace(" ", "_")[:40] if label else "manual"
    filename = f"{timestamp}_{safe_label}_{snap_id[:8]}.tar.gz"
    snap_path = SNAPSHOT_DIR / filename

    try:
        with tarfile.open(str(snap_path), "w:gz") as tar:
            for path in BACKUP_PATHS:
                p = Path(path)
                if p.exists():
                    try:
                        tar.add(str(p), arcname=p.name)
                    except (PermissionError, OSError):
                        # Izin verilmeyen dosyalari atla
                        continue

        size = snap_path.stat().st_size

        with database.get_connection() as conn:
            conn.execute(
                "INSERT INTO snapshots (id, label, path, size_bytes) VALUES (?, ?, ?, ?)",
                (snap_id, label or "Manuel Yedek", str(snap_path), size)
            )

        return {
            "success": True,
            "snapshot_id": snap_id,
            "path": str(snap_path),
            "label": label or "Manuel Yedek",
            "size_bytes": size,
            "created_at": datetime.now().isoformat()
        }

    except Exception as e:
        if snap_path.exists():
            snap_path.unlink()
        return {
            "success": False,
            "message": f"Snapshot alınamadı: {str(e)}"
        }


def list_snapshots() -> list[dict]:
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT id, label, path, size_bytes, created_at FROM snapshots ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_snapshot(snapshot_id: str) -> dict:
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT path FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()

        if not row:
            return {"success": False, "message": "Snapshot bulunamadı."}

        snap_path = Path(row["path"])
        if snap_path.exists():
            snap_path.unlink()

        conn.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))

    return {"success": True, "message": "Snapshot silindi."}


def rollback_snapshot(snapshot_id: str) -> dict:
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT path, label FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()

    if not row:
        return {"success": False, "message": "Snapshot bulunamadı."}

    snap_path = Path(row["path"])
    if not snap_path.exists():
        return {"success": False, "message": "Snapshot dosyası diskte bulunamadı."}

    pre_rollback = create_snapshot(label="Rollback öncesi otomatik yedek")
    if not pre_rollback.get("success"):
        return {"success": False, "message": "Geri yükleme öncesi otomatik yedek alınamadı."}

    temp_dir = SNAPSHOT_DIR / f"_restore_{snapshot_id[:8]}"
    try:
        # temizle ve olustur
        if temp_dir.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        # tar ac
        with tarfile.open(str(snap_path), "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                try:
                    tar.extract(member, str(temp_dir))
                except Exception:
                    continue

        # etc dizinini geri yukle
        extracted_etc = temp_dir / "etc"
        if not extracted_etc.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)
            return {"success": False, "message": "Snapshot icerisinde /etc dizini bulunamadi."}

        # /etc altindaki dosyalari tek tek kopyala (copytree yerine)
        restored_count = 0
        failed_count = 0
        for item in extracted_etc.rglob("*"):
            try:
                item_str = str(item)
                rel = item.relative_to(extracted_etc)
                target = Path("/") / rel
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif item.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item_str, str(target))
                    restored_count += 1
            except Exception:
                failed_count += 1
                continue

        shutil.rmtree(str(temp_dir), ignore_errors=True)

        msg = f"'{row['label']}' basariyla geri yuklendi. ({restored_count} dosya geri yuklendi)"
        if failed_count > 0:
            msg += f" ({failed_count} dosyaya erisilemedi)"

        return {
            "success": True,
            "message": msg,
            "pre_rollback_snapshot_id": pre_rollback["snapshot_id"],
            "restored": restored_count,
            "failed": failed_count,
        }

    except Exception as e:
        shutil.rmtree(str(temp_dir), ignore_errors=True)
        try:
            err_msg = str(e)
        except Exception:
            err_msg = "Bilinmeyen hata"
        return {
            "success": False,
            "message": f"Geri yukleme sirasinda hata: {err_msg}"
        }
