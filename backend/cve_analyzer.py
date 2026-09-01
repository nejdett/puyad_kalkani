# Puyad Kalkanı
# CVE ve paket zafiyet analiz motoru
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime

import httpx
import database

CVE_DB_FILE = Path(__file__).parent / "cve_database.json"

# dpkg-query paket adlari ile cve_database.json arasindaki eslesme
# Bazı paketlerin dpkg adlari farkli olabilir
PACKAGE_ALIASES = {
    "glibc": ["libc6"],
    "krb5-libs": ["libk5crypto3", "libkrb5-3", "libgssapi-krb5-2"],
    "nettle": ["libnettle8", "libhogweed6"],
    "libcurl4": ["libcurl4"],
}


def _load_cve_db() -> list[dict]:
    if not CVE_DB_FILE.exists():
        return []
    with open(CVE_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_version(raw: str) -> str:
    """Debian epoch ve revision eklerini temizle. 1:9.7p1-2ubuntu1 -> 9.7p1"""
    ver = raw.strip()
    # epoch: 1:xxxxx
    if ":" in ver:
        ver = ver.split(":", 1)[1]
    # revision: -2ubuntu1, -0+deb12u1 etc
    match = re.match(r"^([0-9][a-zA-Z0-9.]*?)(?:[-+].*)?$", ver)
    if match:
        return match.group(1)
    return ver


def _get_installed_packages() -> dict[str, str]:
    """dpkg-query ile yüklü paketleri ve versiyonlarını çek."""
    packages = {}
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f", "${Package}\t${Version}\n"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            # dpkg-query hata verdi — dpkg mevcut mu kontrol et
            try:
                subprocess.run(["dpkg", "--version"], capture_output=True, timeout=5)
            except FileNotFoundError:
                return packages
            return packages
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[0].strip():
                packages[parts[0].strip()] = parts[1].strip()
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return packages


def _version_is_affected(installed: str, affected_below: str) -> bool:
    """Yüklü versiyon, etkilenen versiyondan eski mi?"""
    inst = _parse_version(installed)
    aff = _parse_version(affected_below)
    if not inst or not aff:
        return False

    # sayısal karşılaştırma için parçalara ayır
    def split_ver(v):
        parts = []
        for p in re.split(r"[.\-]", v):
            m = re.match(r"(\d+)(.*)", p)
            if m:
                parts.append((int(m.group(1)), m.group(2)))
            else:
                parts.append((0, p))
        return parts

    iv = split_ver(inst)
    av = split_ver(aff)

    for i in range(max(len(iv), len(av))):
        inum, ilet = iv[i] if i < len(iv) else (0, "")
        anum, alet = av[i] if i < len(av) else (0, "")
        if inum != anum:
            return inum < anum
        if ilet != alet:
            return ilet < alet
    return False


def _query_osv_api(packages: dict[str, str]) -> list[dict]:
    """OSV.dev API'inden zafiyetleri çek."""
    results = []
    try:
        with httpx.Client(timeout=15) as client:
            for pkg_name, pkg_ver in packages.items():
                try:
                    resp = client.post(
                        "https://api.osv.dev/v1/query",
                        json={
                            "package": {
                                "name": pkg_name,
                                "ecosystem": "Debian",
                            },
                            "version": pkg_ver,
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for vuln in data.get("vulns", []):
                            cve_id = vuln.get("id", "")
                            summary = vuln.get("summary", "")

                            # severity çek
                            severity = "medium"
                            for s in vuln.get("severity", []):
                                stype = s.get("type", "")
                                if stype == "CVSS_V3":
                                    score_str = s.get("score", "")
                                    # basit heuristik
                                    if "CVSS:" in score_str:
                                        try:
                                            parts = score_str.split("/")
                                            for part in parts:
                                                if part.startswith("CVSS:3"):
                                                    continue
                                        except Exception:
                                            pass

                            # severity listesinden al
                            for sev in vuln.get("severity", []):
                                if sev.get("type") == "CVSS_V3":
                                    score = sev.get("score", "")
                                    # base score'dan severity tahmini
                                    try:
                                        # AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H formatında
                                        parts = score.split("/")
                                        for p in parts:
                                            if p.startswith("AV:N"):
                                                severity = "high"
                                    except Exception:
                                        pass

                            affected_range = ""
                            for aff in vuln.get("affected", []):
                                for r in aff.get("ranges", []):
                                    events = r.get("events", [])
                                    for ev in events:
                                        if "introduced" in ev:
                                            affected_range += f"from {ev['introduced']} "
                                        if "fixed" in ev:
                                            affected_range += f"to {ev['fixed']} "

                            results.append({
                                "package": pkg_name,
                                "cve_id": cve_id,
                                "severity": severity,
                                "description": summary,
                                "affected_range": affected_range.strip(),
                                "fix": f"apt install --only-upgrade {pkg_name}",
                                "source": "osv.dev",
                            })
                except Exception:
                    continue
    except Exception:
        pass
    return results


def _calculate_score(critical: int, high: int, medium: int, low: int) -> int:
    """Yazılım güvenlik skorunu hesapla (0-100)."""
    penalty = critical * 25 + high * 10 + medium * 5 + low * 2
    score = 100 - penalty
    return max(0, min(100, score))


def run_cve_scan(use_osv: bool = False, server_id: int = 1) -> dict:
    try:
        return _run_cve_scan_inner(use_osv, server_id)
    except Exception as e:
        return {
            "success": False,
            "message": f"Tarama sırasında hata: {str(e)}",
        }


def _run_cve_scan_inner(use_osv: bool = False, server_id: int = 1) -> dict:
    cve_db = _load_cve_db()

    if not cve_db:
        return {
            "success": False,
            "message": "CVE veritabanı dosyası (cve_database.json) bulunamadı veya boş.",
        }

    installed = _get_installed_packages()

    if not installed:
        return {
            "success": False,
            "message": (
                "Paket listesi alınamadı. dpkg-query komutu çalışmadı. "
                "Bu ortamda dpkg/paket yöneticisi mevcut olmayabilir."
            ),
        }

    found_vulns = []
    checked = set()
    matched_pkgs = []

    # Katman 1: yerel DB tarama
    for entry in cve_db:
        pkg = entry["package"]

        # paket adi eslesme kontrolu
        actual_pkg = pkg
        if pkg not in installed:
            aliases = PACKAGE_ALIASES.get(pkg, [])
            found = False
            for alias in aliases:
                if alias in installed:
                    actual_pkg = alias
                    found = True
                    break
            if not found:
                continue

        installed_ver = installed[actual_pkg]
        matched_pkgs.append(actual_pkg)
        key = f"{actual_pkg}:{entry['cve_id']}"
        if key in checked:
            continue
        checked.add(key)

        if _version_is_affected(installed_ver, entry["affected_below"]):
            found_vulns.append({
                "package": actual_pkg,
                "installed_version": installed_ver,
                "cve_id": entry["cve_id"],
                "severity": entry["severity"],
                "description": entry["description"],
                "fix": entry.get("fix", f"apt install --only-upgrade {actual_pkg}"),
                "source": "local_db",
            })

    # Katman 2: OSV.dev API
    if use_osv:
        osv_results = _query_osv_api(installed)
        # deduplication
        existing_ids = {v["cve_id"] for v in found_vulns}
        for vuln in osv_results:
            if vuln["cve_id"] not in existing_ids:
                found_vulns.append({
                    "package": vuln["package"],
                    "installed_version": installed.get(vuln["package"], "unknown"),
                    **vuln,
                })
                existing_ids.add(vuln["cve_id"])

    # skor hesapla
    critical = sum(1 for v in found_vulns if v["severity"] == "critical")
    high = sum(1 for v in found_vulns if v["severity"] == "high")
    medium = sum(1 for v in found_vulns if v["severity"] == "medium")
    low = sum(1 for v in found_vulns if v["severity"] == "low")
    score = _calculate_score(critical, high, medium, low)

    # DB'ye kaydet
    scan_results_json = json.dumps(found_vulns, ensure_ascii=False)
    with database.get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO cve_scans
               (server_id, vulnerability_score, critical_count, high_count,
                medium_count, low_count, scan_results)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (server_id, score, critical, high, medium, low, scan_results_json)
        )
        scan_id = cursor.lastrowid

    return {
        "success": True,
        "scan_id": scan_id,
        "message": f"{len(installed)} paket tarandı, {len(matched_pkgs)} paket CVE veritabanıyla eşleşti." if found_vulns else f"{len(installed)} paket tarandı. Zafiyet bulunamadı.",
        "summary": {
            "total": len(found_vulns),
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "score": score,
            "packages_checked": len(installed),
            "packages_matched": len(matched_pkgs),
        },
        "results": found_vulns,
    }


def get_scan_history(server_id: int = None, limit: int = 20) -> list[dict]:
    """Geçmiş CVE taramalarını listele."""
    with database.get_connection() as conn:
        if server_id:
            rows = conn.execute(
                """SELECT id, server_id, vulnerability_score, critical_count,
                          high_count, medium_count, low_count, created_at
                   FROM cve_scans WHERE server_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (server_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, server_id, vulnerability_score, critical_count,
                          high_count, medium_count, low_count, created_at
                   FROM cve_scans ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_scan_detail(scan_id: int) -> dict | None:
    """Belirli bir taramanın detaylarını döndür."""
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cve_scans WHERE id = ?", (scan_id,)
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    if result.get("scan_results"):
        result["scan_results"] = json.loads(result["scan_results"])
    return result
