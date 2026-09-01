# Puyad Kalkanı
# Canlı log izleme (auth.log / journald SSE)
import asyncio
import os
import subprocess
from pathlib import Path
from typing import AsyncGenerator

LOG_CANDIDATES = [
    "/var/log/auth.log",
    "/var/log/secure",
    "/var/log/syslog",
    "/var/log/messages",
    "/var/log/kern.log",
]

CRITICAL_KEYWORDS = [
    "Failed password",
    "Invalid user",
    "authentication failure",
    "BREAK-IN ATTEMPT",
    "sudo:",
    "ROOT LOGIN",
    "session opened for user root",
    "Accepted password",
    "Accepted publickey",
    "Connection closed",
    "error",
    "warning",
]


def get_active_log() -> str | None:
    for path in LOG_CANDIDATES:
        p = Path(path)
        try:
            if p.exists() and p.is_file() and os.access(str(p), os.R_OK):
                return path
        except Exception:
            continue
    return None


def _journald_available() -> bool:
    try:
        result = subprocess.run(
            ["journalctl", "--no-pager", "-n", "1"],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


def _docker_logs_available() -> bool:
    """Docker container icindeyse kendi log kaynaklarini kontrol eder."""
    try:
        result = subprocess.run(
            ["ls", "/var/log/"], capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
    except Exception:
        pass
    return False


def get_log_source() -> dict:
    file_path = get_active_log()
    if file_path:
        return {"type": "file", "path": file_path}
    if _journald_available():
        return {"type": "journald", "path": "journalctl (systemd)"}
    # Docker icindeyse /var/log altindaki herhangi bir dosyayi dene
    try:
        import glob as _glob
        log_files = sorted(_glob.glob("/var/log/*.log") + _glob.glob("/var/log/syslog*"))
        for lf in log_files:
            if os.path.isfile(lf) and os.access(lf, os.R_OK):
                return {"type": "file", "path": lf}
    except Exception:
        pass
    return {"type": "none", "path": None}


def get_log_tail(lines: int = 100) -> list[dict]:
    source = get_log_source()

    if source["type"] == "journald":
        return _journald_tail(lines)
    elif source["type"] == "file":
        return _file_tail(source["path"], lines)
    else:
        return [{"line": "Log kaynağı bulunamadı. rsyslog veya journald gerekli.", "level": "error"}]


def _file_tail(log_path: str, lines: int) -> list[dict]:
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            tail = all_lines[-lines:] if len(all_lines) >= lines else all_lines
        return [{"line": l.rstrip(), "level": _classify_line(l)} for l in tail if l.strip()]
    except PermissionError:
        return [{"line": f"İzin hatası: {log_path}", "level": "error"}]
    except Exception as e:
        return [{"line": str(e), "level": "error"}]


def _journald_tail(lines: int) -> list[dict]:
    try:
        result = subprocess.run(
            ["journalctl", "--no-pager", "-n", str(lines), "--output=short"],
            capture_output=True, text=True, timeout=10
        )
        return [
            {"line": l.rstrip(), "level": _classify_line(l)}
            for l in result.stdout.splitlines() if l.strip()
        ]
    except Exception as e:
        return [{"line": str(e), "level": "error"}]


async def tail_log_stream(lines_back: int = 50) -> AsyncGenerator[str, None]:
    source = get_log_source()

    yield f"data: Kaynak: {source['path'] or 'Bulunamadı'}|LEVEL:info\n\n"

    if source["type"] == "none":
        yield "data: Log kaynağı bulunamadı. 'sudo systemctl start rsyslog' komutunu deneyin.|LEVEL:error\n\n"
        return

    if source["type"] == "journald":
        async for chunk in _stream_journald(lines_back):
            yield chunk
    else:
        async for chunk in _stream_file(source["path"], lines_back):
            yield chunk


async def _stream_file(log_path: str, lines_back: int) -> AsyncGenerator[str, None]:
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            for line in all_lines[-lines_back:]:
                clean = line.rstrip()
                if clean:
                    yield f"data: {clean}|LEVEL:{_classify_line(clean)}\n\n"

            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    clean = line.rstrip()
                    if clean:
                        yield f"data: {clean}|LEVEL:{_classify_line(clean)}\n\n"
                else:
                    await asyncio.sleep(0.5)
    except PermissionError:
        yield f"data: İzin hatası: {log_path}|LEVEL:error\n\n"
    except Exception as e:
        yield f"data: Hata: {str(e)}|LEVEL:error\n\n"


async def _stream_journald(lines_back: int) -> AsyncGenerator[str, None]:
    try:
        result = subprocess.run(
            ["journalctl", "--no-pager", "-n", str(lines_back), "--output=short"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            clean = line.rstrip()
            if clean:
                yield f"data: {clean}|LEVEL:{_classify_line(clean)}\n\n"

        proc = await asyncio.create_subprocess_exec(
            "journalctl", "-f", "--output=short", "--no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            clean = line.decode("utf-8", errors="replace").rstrip()
            if clean:
                yield f"data: {clean}|LEVEL:{_classify_line(clean)}\n\n"

    except Exception as e:
        yield f"data: journald hatası: {str(e)}|LEVEL:error\n\n"


def _classify_line(line: str) -> str:
    line_lower = line.lower()
    critical = [
        "failed password", "invalid user", "authentication failure",
        "break-in attempt", "root login", "session opened for user root"
    ]
    warning = [
        "sudo:", "accepted password", "accepted publickey",
        "error", "warning", "disconnect"
    ]

    for kw in critical:
        if kw in line_lower:
            return "critical"
    for kw in warning:
        if kw in line_lower:
            return "warning"
    return "info"
