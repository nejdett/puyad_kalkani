# Puyad Kalkanı
# SQLite veritabanı
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "history.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS servers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            ip_address  TEXT    NOT NULL,
            port        INTEGER DEFAULT 8000,
            status      TEXT    DEFAULT 'offline',
            last_score  INTEGER DEFAULT 0,
            created_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS fix_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id     TEXT    NOT NULL,
            rule_name   TEXT    NOT NULL,
            status      TEXT    NOT NULL,
            output      TEXT,
            snapshot_id TEXT,
            server_id   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id          TEXT    PRIMARY KEY,
            label       TEXT    NOT NULL,
            path        TEXT    NOT NULL,
            size_bytes  INTEGER DEFAULT 0,
            server_id   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS scan_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            total       INTEGER DEFAULT 0,
            warnings    INTEGER DEFAULT 0,
            ok_count    INTEGER DEFAULT 0,
            score       INTEGER DEFAULT 0,
            server_id   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS scan_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id     INTEGER NOT NULL REFERENCES scan_history(id),
            rule_id     TEXT    NOT NULL,
            rule_name   TEXT    NOT NULL,
            status      TEXT    NOT NULL,
            output      TEXT
        );

        CREATE TABLE IF NOT EXISTS forensic_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id       INTEGER DEFAULT 1,
            trigger_reason  TEXT    NOT NULL,
            evidence_json   TEXT    NOT NULL,
            created_at      DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS pending_actions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id       INTEGER DEFAULT 1,
            token           TEXT    UNIQUE NOT NULL,
            action_type     TEXT    NOT NULL,
            target_payload  TEXT,
            status          TEXT    DEFAULT 'pending',
            created_at      DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS cve_scans (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id           INTEGER DEFAULT 1,
            vulnerability_score INTEGER DEFAULT 0,
            critical_count      INTEGER DEFAULT 0,
            high_count          INTEGER DEFAULT 0,
            medium_count        INTEGER DEFAULT 0,
            low_count           INTEGER DEFAULT 0,
            scan_results        TEXT,
            created_at          DATETIME DEFAULT (datetime('now','localtime'))
        );
        """)

        # localhost sunucusunu seed et
        existing = conn.execute("SELECT id FROM servers WHERE id = 1").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO servers (id, name, ip_address, port, status) VALUES (?, ?, ?, ?, ?)",
                (1, "Yerel Sunucu", "127.0.0.1", 8000, "online")
            )


init_db()
