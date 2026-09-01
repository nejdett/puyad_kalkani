# Puyad Kalkanı
import subprocess
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RULES_FILE   = Path(__file__).parent / "rules.json"
IGNORED_FILE = Path(__file__).parent / "ignored.json"

ALLOWED_CMD_PREFIXES = [
    "grep", "awk", "sed", "find", "stat", "dpkg", "systemctl",
    "ufw", "iptables", "sysctl", "mount", "ss", "chown", "chmod",
    "passwd", "useradd", "usermod", "userdel", "apt-get", "auditctl",
    "journalctl", "python3",
    "echo", "tee", "cp", "printf",
    "xargs", "test", "true", "false", "source",
    "print", "tr", "head", "tail", "cut", "sort", "uniq", "wc",
]

SHELL_BUILTINS = {
    "[", "]", "if", "then", "else", "elif", "fi",
    "for", "while", "until", "do", "done", "done)", "in",
    "case", "esac", "select", "time", "function",
    "}", "}",
}

DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"(?<!>)>\s*/etc/",
    r"mkfs",
    r"dd\s+if=",
    r":(){ :|:& };:",
    r"curl\s+.*\|\s*(ba)?sh",
    r"wget\s+.*\|\s*(ba)?sh",
]


def _extract_first_tokens(command: str) -> list[str]:
    tokens = []
    for part in command.split(";"):
        part = part.strip()
        if not part:
            continue
        words = part.split()
        if not words:
            continue
        w0 = words[0]
        if w0 in ("&&", "||", "!"):
            words = words[1:]
        if words:
            tokens.append(words[0])
    return tokens


def validate_command(command: str) -> tuple[bool, str]:
    if not command or not command.strip():
        return False, "Komut boş olamaz"

    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, command):
            return False, f"Tehlikeli kalıp: {pat}"

    stripped = command.strip()
    if stripped.startswith("python3"):
        return True, "OK"

    tokens = _extract_first_tokens(command)
    for t in tokens:
        if "=" in t or "$" in t:
            continue
        if t in SHELL_BUILTINS:
            continue
        if t in ALLOWED_CMD_PREFIXES:
            continue
        return False, f"İzin verilmeyen komut: {t}"

    return True, "OK"


def load_rules() -> list[dict]:
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_rules(rules: list[dict]) -> None:
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

def load_ignored() -> list[str]:
    if not IGNORED_FILE.exists():
        return []
    with open(IGNORED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_ignored(ignored: list[str]) -> None:
    with open(IGNORED_FILE, "w", encoding="utf-8") as f:
        json.dump(ignored, f, ensure_ascii=False, indent=2)

def run_command(command: str, timeout: int = 30) -> dict:
    valid, msg = validate_command(command)
    if not valid:
        return {"success": False, "stdout": "", "stderr": f"Güvenlik hatası: {msg}", "returncode": -1}

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "TIMEOUT", "stderr": "Komut zaman aşımına uğradı.", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

def check_rule(rule: dict) -> dict:
    result = run_command(rule["check_command"], timeout=30)
    last_line = result["stdout"].strip().splitlines()[-1].upper() if result["stdout"].strip() else ""
    status = "ok" if "OK" in last_line else "warning"

    return {
        "id":          rule["id"],
        "name":        rule["name"],
        "category":    rule["category"],
        "severity":    rule["severity"],
        "description": rule["description"],
        "status":      status,
        "output":      result["stdout"] or result["stderr"],
    }

def check_single_rule(rule_id: str) -> dict | None:
    rules = load_rules()
    rule = next((r for r in rules if r["id"] == rule_id), None)
    return check_rule(rule) if rule else None

def scan_all() -> list[dict]:
    rules        = load_rules()
    ignored      = load_ignored()
    active_rules = [r for r in rules if r["id"] not in ignored]
    results_map  = {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_rule = {executor.submit(check_rule, rule): rule for rule in active_rules}
        for future in as_completed(future_to_rule):
            rule = future_to_rule[future]
            try:
                result = future.result()
            except Exception as e:
                result = {
                    "id": rule["id"], "name": rule["name"],
                    "category": rule["category"], "severity": rule["severity"],
                    "description": rule["description"],
                    "status": "warning", "output": f"Beklenmeyen hata: {e}",
                }
            results_map[rule["id"]] = result

    return [results_map[r["id"]] for r in active_rules if r["id"] in results_map]

def fix_rule(rule_id: str) -> dict:
    rules = load_rules()
    rule  = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        return {"success": False, "message": f"'{rule_id}' ID'li kural bulunamadı.", "output": ""}

    result = run_command(rule["fix_command"], timeout=120)
    return {
        "success": result["success"],
        "message": "Düzeltme başarıyla uygulandı." if result["success"] else "Düzeltme sırasında hata oluştu.",
        "output":  result["stdout"] or result["stderr"],
    }

def ignore_rule(rule_id: str) -> dict:
    rules = load_rules()
    if not any(r["id"] == rule_id for r in rules):
        return {"success": False, "message": f"'{rule_id}' ID'li kural bulunamadı."}
    ignored = load_ignored()
    if rule_id not in ignored:
        ignored.append(rule_id)
        save_ignored(ignored)
    return {"success": True, "message": f"'{rule_id}' kuralı görmezden gelinenler listesine eklendi."}

def unignore_rule(rule_id: str) -> dict:
    ignored = load_ignored()
    if rule_id in ignored:
        ignored.remove(rule_id)
        save_ignored(ignored)
    return {"success": True, "message": f"'{rule_id}' kuralı görmezden gelinenler listesinden çıkarıldı."}

def add_rule(rule: dict) -> dict:
    rules = load_rules()
    if any(r["id"] == rule["id"] for r in rules):
        return {"success": False, "message": f"'{rule['id']}' ID'li bir kural zaten mevcut."}

    for field in ["check_command", "fix_command"]:
        if field in rule:
            valid, msg = validate_command(rule[field])
            if not valid:
                return {"success": False, "message": f"{field} güvenli değil: {msg}"}

    rules.append(rule)
    save_rules(rules)
    return {"success": True, "message": f"'{rule['name']}' kuralı başarıyla eklendi."}

def update_rule(rule_id: str, updates: dict) -> dict:
    rules = load_rules()
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        return {"success": False, "message": f"'{rule_id}' ID'li kural bulunamadı."}

    if "id" in updates and updates["id"] != rule_id:
        if any(r["id"] == updates["id"] for r in rules):
            return {"success": False, "message": f"'{updates['id']}' ID'li bir kural zaten mevcut."}
        if not re.match(r'^[a-z0-9_]+$', updates["id"]):
            return {"success": False, "message": "ID yalnızca küçük harf, rakam ve alt çizgi içerebilir."}

    for field in ["check_command", "fix_command"]:
        if field in updates:
            valid, msg = validate_command(updates[field])
            if not valid:
                return {"success": False, "message": f"{field} güvenli değil: {msg}"}

    rule.update({k: v for k, v in updates.items() if v is not None})
    save_rules(rules)
    return {"success": True, "message": f"'{rule['name']}' kuralı güncellendi."}


def delete_rule(rule_id: str) -> dict:
    rules     = load_rules()
    new_rules = [r for r in rules if r["id"] != rule_id]
    if len(new_rules) == len(rules):
        return {"success": False, "message": f"'{rule_id}' ID'li kural bulunamadı."}
    save_rules(new_rules)
    return {"success": True, "message": f"'{rule_id}' kuralı başarıyla silindi."}
