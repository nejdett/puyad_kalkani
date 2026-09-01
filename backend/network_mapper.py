# Puyad Kalkanı
# Ağ haritası ve GeoIP modülü
import re
import subprocess
import httpx
from datetime import datetime

import database

# GeoIP önbellek
_geoip_cache: dict = {}
CACHE_MAX = 500


def _run(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _parse_ss_output(raw: str) -> list[dict]:
    """ss -tupn çıktısını parsed connection listesine çevir."""
    connections = []
    for line in raw.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        state = parts[1] if parts[1] in ("ESTAB", "LISTEN", "SYN-SENT", "TIME-WAIT", "CLOSE-WAIT") else parts[1]
        local = parts[3] if len(parts) > 3 else ""
        peer = parts[4] if len(parts) > 4 else ""
        process = ""
        for p in parts[5:]:
            if "users:" in p:
                match = re.search(r'\("([^"]+)"', p)
                if match:
                    process = match.group(1)
                break

        local_ip, local_port = "", ""
        if ":" in local:
            last_colon = local.rfind(":")
            local_ip = local[:last_colon]
            local_port = local[last_colon + 1:]

        peer_ip, peer_port = "", ""
        if peer and ":" in peer:
            last_colon = peer.rfind(":")
            peer_ip = peer[:last_colon]
            peer_port = peer[last_colon + 1:]

        connections.append({
            "proto": proto,
            "state": state,
            "local_ip": local_ip,
            "local_port": local_port,
            "peer_ip": peer_ip,
            "peer_port": peer_port,
            "process": process,
        })
    return connections


class PuyadNetworkMapper:

    @staticmethod
    def get_geoip_data(ip_address: str) -> dict:
        if ip_address in _geoip_cache:
            return _geoip_cache[ip_address]

        # özel/yerel adres kontrolü
        if _is_private(ip_address):
            result = {"ip": ip_address, "country": "Yerel", "city": "Yerel Ağ",
                      "lat": 0, "lon": 0, "org": "Private Network", "is_private": True}
            _geoip_cache[ip_address] = result
            return result

        try:
            resp = httpx.get(f"http://ip-api.com/json/{ip_address}?fields=status,country,countryCode,city,lat,lon,org,isp", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    result = {
                        "ip": ip_address,
                        "country": data.get("country", "Bilinmiyor"),
                        "country_code": data.get("countryCode", ""),
                        "city": data.get("city", "Bilinmiyor"),
                        "lat": data.get("lat", 0),
                        "lon": data.get("lon", 0),
                        "org": data.get("org", ""),
                        "isp": data.get("isp", ""),
                        "is_private": False,
                    }
                    if len(_geoip_cache) < CACHE_MAX:
                        _geoip_cache[ip_address] = result
                    return result
        except Exception:
            pass
        # fallback: ip-api basarisizsa bile kayit dondur
        try:
            resp2 = httpx.get(f"http://ip-api.com/json/{ip_address}", timeout=5.0)
            if resp2.status_code == 200:
                data2 = resp2.json()
                if data2.get("status") == "success":
                    result = {
                        "ip": ip_address,
                        "country": data2.get("country", "Bilinmiyor"),
                        "country_code": data2.get("countryCode", ""),
                        "city": data2.get("city", "Bilinmiyor"),
                        "lat": data2.get("lat", 0),
                        "lon": data2.get("lon", 0),
                        "org": data2.get("org", ""),
                        "isp": data2.get("isp", ""),
                        "is_private": False,
                    }
                    if len(_geoip_cache) < CACHE_MAX:
                        _geoip_cache[ip_address] = result
                    return result
        except Exception:
            pass

        return {"ip": ip_address, "country": "Bilinmiyor", "city": "Bilinmiyor",
                "lat": 0, "lon": 0, "org": "", "is_private": False}

    @staticmethod
    def get_active_connections_map() -> dict:
        raw = _run("ss -tupn 2>/dev/null || netstat -tupn 2>/dev/null")
        connections = _parse_ss_output(raw)

        # dinleyen portları topla
        listening = [c for c in connections if c["state"] == "LISTEN"]
        established = [c for c in connections if c["state"] == "ESTAB"]

        # düğümleri oluştur
        nodes = []
        edges = []

        # merkezi sunucu düğümü
        nodes.append({"id": "server", "label": "Sunucu", "type": "server", "ip": "127.0.0.1"})

        # dinleyen portlar
        seen_ports = set()
        for c in listening:
            port_key = f"{c['local_ip']}:{c['local_port']}"
            if port_key not in seen_ports:
                seen_ports.add(port_key)
                nodes.append({
                    "id": f"port_{c['local_port']}",
                    "label": f":{c['local_port']}",
                    "type": "port",
                    "ip": c["local_ip"],
                    "port": c["local_port"],
                    "process": c["process"],
                })
                edges.append({"from": "server", "to": f"port_{c['local_port']}", "label": c["process"]})

        # aktif bağlantılar
        seen_peers = set()
        for c in established:
            if c["peer_ip"] and c["peer_ip"] not in seen_peers:
                seen_peers.add(c["peer_ip"])
                node_id = f"client_{c['peer_ip']}"
                nodes.append({
                    "id": node_id,
                    "label": c["peer_ip"],
                    "type": "client",
                    "ip": c["peer_ip"],
                    "port": c["peer_port"],
                })
                port_node = f"port_{c['local_port']}"
                edges.append({"from": port_node, "to": node_id, "label": c["peer_port"]})

        return {"nodes": nodes, "edges": edges, "total_connections": len(connections)}

    @staticmethod
    def get_attack_origins() -> list[dict]:
        attacks = []

        # honeypot hits
        try:
            with database.get_connection() as conn:
                hits = conn.execute(
                    "SELECT src_ip, port, service, created_at FROM honeypot_hits ORDER BY created_at DESC LIMIT 100"
                ).fetchall()
                for h in hits:
                    h = dict(h)
                    if h["src_ip"] and not _is_private(h["src_ip"]):
                        geo = PuyadNetworkMapper.get_geoip_data(h["src_ip"])
                        attacks.append({
                            "ip": h["src_ip"],
                            "type": "HoneyPot",
                            "port": h["port"],
                            "service": h["service"],
                            "date": h["created_at"],
                            "lat": geo.get("lat", 0),
                            "lon": geo.get("lon", 0),
                            "country": geo.get("country", "Bilinmiyor"),
                            "country_code": geo.get("country_code", ""),
                            "city": geo.get("city", "Bilinmiyor"),
                        })
        except Exception:
            pass

        # brute force logs
        try:
            with database.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS bruteforce_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        src_ip TEXT NOT NULL,
                        attempts INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT (datetime('now','localtime'))
                    )
                """)
                bf = conn.execute(
                    "SELECT src_ip, attempts, created_at FROM bruteforce_log ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
                for b in bf:
                    b = dict(b)
                    if b["src_ip"] and not _is_private(b["src_ip"]):
                        geo = PuyadNetworkMapper.get_geoip_data(b["src_ip"])
                        attacks.append({
                            "ip": b["src_ip"],
                            "type": "BruteForce",
                            "attempts": b["attempts"],
                            "date": b["created_at"],
                            "lat": geo.get("lat", 0),
                            "lon": geo.get("lon", 0),
                            "country": geo.get("country", "Bilinmiyor"),
                            "country_code": geo.get("country_code", ""),
                            "city": geo.get("city", "Bilinmiyor"),
                        })
        except Exception:
            pass

        return attacks


def _is_private(ip: str) -> bool:
    if not ip:
        return True
    parts = ip.split(".")
    if len(parts) != 4:
        return True
    try:
        first = int(parts[0])
        second = int(parts[1])
    except ValueError:
        return True
    if first == 10:
        return True
    if first == 172 and 16 <= second <= 31:
        return True
    if first == 192 and second == 168:
        return True
    if first == 127:
        return True
    return False
