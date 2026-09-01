# Puyad Kalkanı
# Tek seferlik veritabanı geçiş scripti
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "history.db"


def migrate():
    if not DB_FILE.exists():
        print("Veritabanı bulunamadı, init_db() zaten yeni şemayı oluşturur.")
        return

    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()

    # servers tablosu var mı kontrol et
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='servers'")
    if not cursor.fetchone():
        print("servers tablosu ekleniyor...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                ip_address  TEXT    NOT NULL,
                port        INTEGER DEFAULT 8000,
                status      TEXT    DEFAULT 'offline',
                last_score  INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT (datetime('now','localtime'))
            )
        """)
        cursor.execute(
            "INSERT INTO servers (id, name, ip_address, port, status) VALUES (?, ?, ?, ?, ?)",
            (1, "Yerel Sunucu", "127.0.0.1", 8000, "online")
        )
        print("servers tablosu oluşturuldu, localhost seed edildi.")
    else:
        print("servers tablosu zaten mevcut.")

    # mevcut tablolara server_id ekle
    tables_to_update = ["fix_history", "snapshots", "scan_history"]
    for table in tables_to_update:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]

        if "server_id" not in columns:
            print(f"{table} tablosuna server_id ekleniyor...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN server_id INTEGER DEFAULT 1")
            print(f"{table} güncellendi.")
        else:
            print(f"{table} tablosunda server_id zaten mevcut.")

    # forensic_history tablosu
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='forensic_history'")
    if not cursor.fetchone():
        print("forensic_history tablosu ekleniyor...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forensic_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id       INTEGER DEFAULT 1,
                trigger_reason  TEXT    NOT NULL,
                evidence_json   TEXT    NOT NULL,
                created_at      DATETIME DEFAULT (datetime('now','localtime'))
            )
        """)
        print("forensic_history tablosu oluşturuldu.")
    else:
        print("forensic_history tablosu zaten mevcut.")

    # pending_actions tablosu
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_actions'")
    if not cursor.fetchone():
        print("pending_actions tablosu ekleniyor...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_actions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id       INTEGER DEFAULT 1,
                token           TEXT    UNIQUE NOT NULL,
                action_type     TEXT    NOT NULL,
                target_payload  TEXT,
                status          TEXT    DEFAULT 'pending',
                created_at      DATETIME DEFAULT (datetime('now','localtime'))
            )
        """)
        print("pending_actions tablosu oluşturuldu.")
    else:
        print("pending_actions tablosu zaten mevcut.")

    # cve_scans tablosu
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cve_scans'")
    if not cursor.fetchone():
        print("cve_scans tablosu ekleniyor...")
        cursor.execute("""
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
            )
        """)
        print("cve_scans tablosu olusturuldu.")
    else:
        print("cve_scans tablosu zaten mevcut.")

    # localhost'un silinmesini engelle - trigger ekle
    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='prevent_delete_localhost'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TRIGGER prevent_delete_localhost
            BEFORE DELETE ON servers
            WHEN OLD.id = 1
            BEGIN
                SELECT RAISE(ABORT, 'Yerel sunucu (id=1) silinemez.');
            END
        """)
        print("localhost koruma trigger'ı eklendi.")

    conn.commit()
    conn.close()
    print("Geçiş tamamlandı.")


if __name__ == "__main__":
    migrate()
