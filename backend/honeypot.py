# Puyad Kalkanı
# HoneyPot modülü
import socket
import threading
import json
from datetime import datetime
from pathlib import Path
import database
import forensic_manager

# Active honeypot servers: {port: {"thread": ..., "server": ..., "config": ...}}
_active_pots: dict = {}
_lock = threading.Lock()

CONFIG_FILE = Path(__file__).parent / "honeypot_config.json"

BANNERS = {
    "ftp":    b"220 FTP Server Ready\r\n",
    "telnet": b"\xff\xfd\x18\xff\xfd\x20\xff\xfd\x23\xff\xfd\x27Welcome to Linux\r\n",
    "ssh":    b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.1\r\n",
    "http":   b"HTTP/1.1 200 OK\r\nServer: Apache/2.4.41\r\nContent-Length: 0\r\n\r\n",
    "smtp":   b"220 mail.server.com ESMTP Postfix\r\n",
    "custom": b"",
}


def load_config() -> list[dict]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_config(pots: list[dict]) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(pots, f, indent=2, ensure_ascii=False)


def _ensure_table() -> None:
    with database.get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS honeypot_hits (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                port       INTEGER NOT NULL,
                service    TEXT,
                src_ip     TEXT NOT NULL,
                src_port   INTEGER,
                data       TEXT,
                created_at DATETIME DEFAULT (datetime('now','localtime'))
            )
        """)


def _log_hit(port: int, service: str, src_ip: str, src_port: int, data: str = "") -> None:
    _ensure_table()
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO honeypot_hits (port, service, src_ip, src_port, data) VALUES (?,?,?,?,?)",
            (port, service, src_ip, src_port, data[:500])
        )


def get_hits(limit: int = 100) -> list[dict]:
    _ensure_table()
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM honeypot_hits ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_hits_since(since_id: int, limit: int = 100) -> list[dict]:
    """son_id'den buyuk ID'li hitleri dondurur (polling icin)."""
    _ensure_table()
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM honeypot_hits WHERE id > ? ORDER BY id ASC LIMIT ?",
            (since_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def _handle_connection(conn_sock: socket.socket, addr: tuple,
                       port: int, service: str, banner: bytes) -> None:
    src_ip = addr[0]
    src_port = addr[1]

    try:
        if banner:
            conn_sock.sendall(banner)

        conn_sock.settimeout(3)
        try:
            data = conn_sock.recv(1024).decode("utf-8", errors="replace").strip()
        except Exception:
            data = ""
    finally:
        conn_sock.close()

    _log_hit(port, service, src_ip, src_port, data)

    msg = (
        f"HONEYPOT HIT | Port: {port} ({service.upper()}) | "
        f"Source: {src_ip}:{src_port}"
        + (f" | Data: {data[:80]}" if data else "")
    )
    event = f"data: {msg}|LEVEL:critical\n\n"



    print(f"[HoneyPot] {msg}")

    # adli kanıt topla
    try:
        threading.Thread(
            target=forensic_manager.PuyadForensicManager.collect_evidence,
            args=("HoneyPot Alert", 1),
            daemon=True
        ).start()
    except Exception:
        pass

    # telegram bildirimi
    try:
        from telegram_manager import PuyadTelegramManager
        PuyadTelegramManager.send_approval_notification(
            "HoneyPot Saldırı Tespiti",
            f"Saldırı Kaynağı: <b>{src_ip}:{src_port}</b>\nPort: {port} ({service.upper()})",
            "block_ip",
            {"ip": src_ip}
        )
    except Exception:
        pass


def _server_loop(port: int, service: str, banner: bytes, stop_event: threading.Event) -> None:
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(10)
        srv.settimeout(1.0)

        with _lock:
            if port in _active_pots:
                _active_pots[port]["server"] = srv

        while not stop_event.is_set():
            try:
                client_sock, addr = srv.accept()
                t = threading.Thread(
                    target=_handle_connection,
                    args=(client_sock, addr, port, service, banner),
                    daemon=True
                )
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

        srv.close()
    except Exception as e:
        print(f"[HoneyPot] Port {port} başlatılamadı: {e}")
        with _lock:
            _active_pots.pop(port, None)


def _is_port_available(port: int) -> bool:
    """Portun bos olup olmadigini kontrol eder."""
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_sock.bind(("0.0.0.0", port))
        test_sock.close()
        return True
    except OSError:
        return False


def start_honeypot(port: int, service: str = "custom", label: str = "") -> dict:
    with _lock:
        if port in _active_pots:
            return {"success": False, "message": f"Port {port} zaten aktif."}

    # Port musaitlik kontrolu
    if not _is_port_available(port):
        return {
            "success": False,
            "message": f"Port {port} baska bir servis tarafindan kullaniliyor. Baska bir port secin.",
        }

    banner = BANNERS.get(service, b"")
    stop_event = threading.Event()

    t = threading.Thread(
        target=_server_loop,
        args=(port, service, banner, stop_event),
        daemon=True
    )

    with _lock:
        _active_pots[port] = {
            "thread": t,
            "stop_event": stop_event,
            "server": None,
            "config": {
                "port": port,
                "service": service,
                "label": label or f"Tuzak {service.upper()} ({port})",
                "started_at": datetime.now().isoformat(),
                "active": True,
            }
        }

    t.start()
    _persist_config()

    return {
        "success": True,
        "message": f"Port {port} ({service.upper()}) honeypot olarak aktif edildi.",
        "port": port,
        "service": service,
    }


def stop_honeypot(port: int) -> dict:
    with _lock:
        pot = _active_pots.get(port)
        if not pot:
            return {"success": False, "message": f"Port {port} aktif değil."}

        pot["stop_event"].set()
        if pot.get("server"):
            try:
                pot["server"].close()
            except Exception:
                pass
        _active_pots.pop(port, None)

    _persist_config()
    return {"success": True, "message": f"Port {port} honeypot'u durduruldu."}


def list_active() -> list[dict]:
    with _lock:
        return [pot["config"] for pot in _active_pots.values()]


def _persist_config() -> None:
    with _lock:
        configs = [pot["config"] for pot in _active_pots.values()]
    save_config(configs)


def restore_from_config() -> None:
    saved = load_config()
    for cfg in saved:
        if cfg.get("active"):
            start_honeypot(cfg["port"], cfg.get("service", "custom"), cfg.get("label", ""))
