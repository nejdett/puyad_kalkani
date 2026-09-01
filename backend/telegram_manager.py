# Puyad Kalkanı
# Telegram bildirim ve onay mekanizması
import hashlib
import hmac
import time
import json
import threading
import httpx

import database
import config

_polling_active = False
_polling_thread = None


class PuyadTelegramManager:

    @staticmethod
    def _get_credentials() -> tuple[str, str]:
        cfg = config.load_config()
        return cfg.get("TELEGRAM_BOT_TOKEN", ""), cfg.get("TELEGRAM_CHAT_ID", "")

    @staticmethod
    def _is_enabled() -> bool:
        cfg = config.load_config()
        return bool(cfg.get("TELEGRAM_ENABLED")) and bool(cfg.get("TELEGRAM_BOT_TOKEN"))

    @staticmethod
    def _generate_token(action_type: str, payload: dict) -> str:
        raw = f"{action_type}:{json.dumps(payload, sort_keys=True)}:{time.time()}"
        return hmac.new(b"puyad-approval", raw.encode(), hashlib.sha256).hexdigest()[:32]

    @staticmethod
    def send_approval_notification(title: str, message: str, action_type: str, payload: dict) -> dict:
        token, chat_id = PuyadTelegramManager._get_credentials()
        if not token or not chat_id:
            return {"success": False, "error": "Telegram yapılandırılmamış."}

        approval_token = PuyadTelegramManager._generate_token(action_type, payload)

        # pending_actions'a kaydet
        try:
            with database.get_connection() as conn:
                conn.execute(
                    "INSERT INTO pending_actions (token, action_type, target_payload, status) VALUES (?, ?, ?, 'pending')",
                    (approval_token, action_type, json.dumps(payload))
                )
        except Exception as e:
            return {"success": False, "error": f"DB kaydı başarısız: {e}"}

        # Telegram butonları
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "Onayla ve IP'yi Engelle", "callback_data": f"approve:{approval_token}"},
                ],
                [
                    {"text": "Iptal Et", "callback_data": f"reject:{approval_token}"},
                ],
            ]
        }

        html_text = (
            f"<b>{title}</b>\n\n"
            f"{message}\n\n"
            f"<code>Token: {approval_token[:8]}...</code>\n"
            f"<i>Butonlara basarak işlemi onaylayın veya iptal edin.</i>"
        )

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        }, timeout=10)

        if resp.status_code == 200:
            return {"success": True, "token": approval_token}
        return {"success": False, "error": f"Telegram API hata: {resp.text}"}

    @staticmethod
    def send_simple_message(text: str) -> dict:
        token, chat_id = PuyadTelegramManager._get_credentials()
        if not token or not chat_id:
            return {"success": False, "error": "Telegram yapılandırılmamış."}

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=10)

        if resp.status_code == 200:
            return {"success": True}
        return {"success": False, "error": f"Telegram API hata: {resp.text}"}

    @staticmethod
    def approve_action(approval_token: str, msg_id: int = None, chat_id: int = None) -> dict:
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pending_actions WHERE token = ? AND status = 'pending'",
                (approval_token,)
            ).fetchone()

            if not row:
                return {"success": False, "error": "Geçersiz veya zaten işlenmiş token."}

            payload = json.loads(row["target_payload"])
            action_type = row["action_type"]

            # IP engelleme islemi
            if action_type == "block_ip" and "ip" in payload:
                import engine
                try:
                    engine.run_command(f"iptables -A INPUT -s {payload['ip']} -j DROP")
                except Exception as e:
                    return {"success": False, "error": f"IP engelleme başarısız: {e}"}

            conn.execute(
                "UPDATE pending_actions SET status = 'approved' WHERE token = ?",
                (approval_token,)
            )

        if msg_id and chat_id:
            PuyadTelegramManager._update_callback_message(msg_id, chat_id, "İşlem Onaylandı ve IP Engellendi.")

        return {"success": True, "message": "İşlem onaylandı."}

    @staticmethod
    def reject_action(approval_token: str, msg_id: int = None, chat_id: int = None) -> dict:
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pending_actions WHERE token = ? AND status = 'pending'",
                (approval_token,)
            ).fetchone()

            if not row:
                return {"success": False, "error": "Geçersiz veya zaten işlenmiş token."}

            conn.execute(
                "UPDATE pending_actions SET status = 'rejected' WHERE token = ?",
                (approval_token,)
            )

        if msg_id and chat_id:
            PuyadTelegramManager._update_callback_message(msg_id, chat_id, "İşlem İptal Edildi.")

        return {"success": True, "message": "İşlem iptal edildi."}

    @staticmethod
    def _update_callback_message(msg_id: int, chat_id: int, new_text: str):
        token, _ = PuyadTelegramManager._get_credentials()
        if not token or not msg_id or not chat_id:
            return

        try:
            httpx.post(
                f"https://api.telegram.org/bot{token}/editMessageText",
                json={"chat_id": chat_id, "message_id": msg_id, "text": new_text},
                timeout=5,
            )
        except Exception:
            pass

    @staticmethod
    def get_pending_actions() -> list[dict]:
        with database.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_actions WHERE status = 'pending' ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def poll_telegram_callbacks():
        global _polling_active
        token, _ = PuyadTelegramManager._get_credentials()
        if not token:
            return

        offset = 0
        _polling_active = True

        while _polling_active:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                resp = httpx.get(url, params={"offset": offset, "timeout": 30}, timeout=35)

                if resp.status_code != 200:
                    time.sleep(5)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    callback = update.get("callback_query")
                    if not callback:
                        continue

                    cb_id = callback.get("id", "")
                    cb_data = callback.get("data", "")
                    msg = callback.get("message", {})
                    msg_id = msg.get("message_id")
                    chat_id_cb = msg.get("chat", {}).get("id")

                    # callback'i telegram'a bildir (yükleme spinner'ını kaldır)
                    try:
                        httpx.post(
                            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                            json={"callback_query_id": cb_id},
                            timeout=5,
                        )
                    except Exception:
                        pass

                    if cb_data.startswith("approve:"):
                        tk = cb_data.split("approve:", 1)[1]
                        PuyadTelegramManager.approve_action(tk, msg_id=msg_id, chat_id=chat_id_cb)
                    elif cb_data.startswith("reject:"):
                        tk = cb_data.split("reject:", 1)[1]
                        PuyadTelegramManager.reject_action(tk, msg_id=msg_id, chat_id=chat_id_cb)

            except Exception:
                time.sleep(5)

    @staticmethod
    def start_polling():
        global _polling_thread
        if _polling_active and _polling_thread and _polling_thread.is_alive():
            return
        if not PuyadTelegramManager._is_enabled():
            return
        _polling_thread = threading.Thread(
            target=PuyadTelegramManager.poll_telegram_callbacks,
            daemon=True,
        )
        _polling_thread.start()


def stop_polling():
    global _polling_active
    _polling_active = False
