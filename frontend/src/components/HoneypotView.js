import React, { useState, useEffect, useRef, useCallback } from "react";
import { ShieldAlert, RefreshCw, Zap, Radio, Square } from "lucide-react";
import { api } from "../api";
import "./HoneypotView.css";

const SERVICE_OPTIONS = [
  { value: "ftp",    label: "FTP",    port: 21   },
  { value: "telnet", label: "Telnet", port: 23   },
  { value: "ssh",    label: "SSH",    port: 2222 },
  { value: "http",   label: "HTTP",   port: 8080 },
  { value: "smtp",   label: "SMTP",   port: 25   },
  { value: "custom", label: "Ozel",   port: 9999 },
];

function formatDate(dt) {
  if (!dt) return "--";
  try { return new Date(dt).toLocaleString("tr-TR"); }
  catch { return dt; }
}

export default function HoneypotView() {
  const [activePots, setActivePots] = useState([]);
  const [hits, setHits]             = useState([]);
  const [alarms, setAlarms]         = useState([]);
  const [monitoring, setMonitoring] = useState(false);
  const [service, setService]       = useState("ftp");
  const [port, setPort]             = useState(21);
  const [label, setLabel]           = useState("");
  const [starting, setStarting]     = useState(false);
  const [message, setMessage]       = useState(null);

  const bottomRef = useRef(null);
  const pollRef   = useRef(null);
  const lastIdRef = useRef(0);

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  // verileri yukle
  const fetchData = useCallback(async () => {
    try {
      const [potsRes, hitsRes] = await Promise.all([
        api.get("/honeypot/active"),
        api.get("/honeypot/hits?limit=50"),
      ]);
      setActivePots(potsRes.data.pots || []);
      setHits(hitsRes.data.hits || []);
      // lastId'yi guncelle
      const allHits = hitsRes.data.hits || [];
      if (allHits.length > 0) {
        lastIdRef.current = Math.max(lastIdRef.current, allHits[0].id || 0);
      }
    } catch (err) {
      console.error("Honeypot verisi alinamadi:", err.message);
    }
  }, []);

  // polling baslat: her 2sn yeni hit kontrol et
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    setMonitoring(true);
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/honeypot/hits?since_id=${lastIdRef.current}&limit=50`);
        const newHits = res.data.hits || [];
        if (newHits.length > 0) {
          // son id'yi guncelle
          lastIdRef.current = Math.max(lastIdRef.current, ...newHits.map(h => h.id));
          // alarm listesine ekle
          const newAlarms = newHits.map(h => ({
            line: `HONEYPOT HIT | Port: ${h.port} (${(h.service || "").toUpperCase()}) | Kaynak: ${h.src_ip}:${h.src_port}` + (h.data ? ` | Veri: ${h.data.substring(0, 80)}` : ""),
            level: "critical",
            id: h.id,
          }));
          setAlarms(prev => [...prev.slice(-200), ...newAlarms]);
          // hits listesini de guncelle
          setHits(prev => {
            const merged = [...newHits, ...prev];
            return merged.slice(0, 50);
          });
        }
      } catch (err) {
        console.error("Polling hatasi:", err.message);
      }
    }, 2000);
  }, []);

  // polling durdur
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setMonitoring(false);
  }, []);

  // component unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  // sayfa yukle
  useEffect(() => { fetchData(); }, [fetchData]);

  // aktif tuzak varsa otomatik polling baslat
  useEffect(() => {
    if (activePots.length > 0 && !monitoring) {
      startPolling();
    } else if (activePots.length === 0 && monitoring) {
      stopPolling();
    }
  }, [activePots.length, monitoring, startPolling, stopPolling]);

  // otomatik kaydir
  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: "smooth" });
  }, [alarms]);

  const handleServiceChange = (val) => {
    setService(val);
    setPort(SERVICE_OPTIONS.find((s) => s.value === val)?.port || 9999);
  };

  const handleStart = async () => {
    setStarting(true);

    try {
      const res = await api.post("/honeypot/start", { port, service, label });
      const data = res.data || res;
      showMessage(`Port ${port} (${service.toUpperCase()}) aktif edildi.`);

      setLabel("");
      fetchData();
      // polling otomatik baslar (useEffect ile activePots.length > 0 tetiklenir)
    } catch (err) {
      showMessage(err.response?.data?.detail || err.message, "error");
    } finally {
      setStarting(false);
    }
  };

  const handleStop = async (p) => {
    try {
      await api.delete(`/honeypot/stop/${p}`);
      showMessage(`Port ${p} durduruldu.`);
      fetchData();
    } catch (err) {
      showMessage(err.response?.data?.detail || err.message, "error");
    }
  };

  const handleManualPoll = async () => {
    try {
      const res = await api.get(`/honeypot/hits?since_id=${lastIdRef.current}&limit=50`);
      const newHits = res.data.hits || [];
      if (newHits.length > 0) {
        lastIdRef.current = Math.max(lastIdRef.current, ...newHits.map(h => h.id));
        const newAlarms = newHits.map(h => ({
          line: `HONEYPOT HIT | Port: ${h.port} (${(h.service || "").toUpperCase()}) | Kaynak: ${h.src_ip}:${h.src_port}` + (h.data ? ` | Veri: ${h.data.substring(0, 80)}` : ""),
          level: "critical",
          id: h.id,
        }));
        setAlarms(prev => [...prev.slice(-200), ...newAlarms]);
        setHits(prev => [...newHits, ...prev].slice(0, 50));
      }
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const LEVEL_COLOR = { critical: "var(--red)", warning: "var(--yellow)", info: "var(--text-muted)" };
  const LEVEL_BG    = { critical: "rgba(239,68,68,0.06)", warning: "rgba(245,158,11,0.04)", info: "transparent" };

  return (
    <div className="honeypot-view">
      <div className="page-header">
        <div>
          <h1 className="page-title">HoneyPot -- Tuzak Port</h1>
          <p className="page-subtitle">Sahte servisler tanimlayarak yetkisiz erisim girisimlerini tespit edin.</p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {monitoring && (
            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--green)", fontSize: "0.8rem" }}>
              <Radio size={12} className="blink" /> Canli Izleniyor
            </span>
          )}
          {monitoring ? (
            <button className="btn btn-danger" onClick={stopPolling}>
              <Square size={13} /> Durdur
            </button>
          ) : (
            <button className="btn btn-success" onClick={() => { fetchData(); startPolling(); }}>
              <Radio size={13} /> Izlemeyi Baslat
            </button>
          )}
          <button className="btn btn-ghost" onClick={() => { fetchData(); handleManualPoll(); }}>
            <RefreshCw size={13} /> Yenile
          </button>
        </div>
      </div>

      {message && (
        <div className={`msg ${message.type === "error" ? "msg-error" : "msg-success"}`}>
          {message.text}
        </div>
      )}



      <div className="hp-grid">
        <div className="card">
          <p className="section-title">Yeni Tuzak Tanimla</p>
          <div className="service-grid">
            {SERVICE_OPTIONS.map((s) => (
              <button key={s.value}
                className={`service-btn ${service === s.value ? "active" : ""}`}
                onClick={() => handleServiceChange(s.value)}>
                <span className="svc-label">{s.label}</span>
                <span className="svc-port">:{s.port}</span>
              </button>
            ))}
          </div>
          <div className="hp-form">
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Port</label>
                <input type="number" className="form-input" value={port} min="1" max="65535"
                  onChange={(e) => setPort(parseInt(e.target.value) || 21)} />
              </div>
              <div className="form-group" style={{ flex: 2 }}>
                <label className="form-label">Etiket (opsiyonel)</label>
                <input type="text" className="form-input" value={label}
                  placeholder="Orn: FTP Tuzagi"
                  onChange={(e) => setLabel(e.target.value)} />
              </div>
            </div>
            <button className="btn btn-primary" onClick={handleStart} disabled={starting} style={{ width: "100%", justifyContent: "center" }}>
              <Zap size={13} />
              {starting ? "Aktif ediliyor..." : "Tuzagi Aktif Et"}
            </button>
          </div>
        </div>

        <div className="card">
          <p className="section-title">Aktif Tuzaklar ({activePots.length})</p>
          {activePots.length === 0 ? (
            <div className="empty-state" style={{ padding: "2rem" }}>
              <ShieldAlert size={28} />
              <p>Aktif tuzak bulunmuyor.</p>
            </div>
          ) : (
            <div className="pots-list">
              {activePots.map((pot) => (
                <div key={pot.port} className="pot-item">
                  <div className="pot-info">
                    <span className="pot-indicator" />
                    <span className="pot-port mono">:{pot.port}</span>
                    <span className="pot-service">{(pot.service || "").toUpperCase()}</span>
                    <span className="pot-label">{pot.label}</span>
                  </div>
                  <button className="btn btn-danger btn-sm" onClick={() => handleStop(pot.port)}>
                    Durdur
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="alarm-header">
          <p className="section-title">
            Canli Alarm Akisi
            {monitoring && <span className="live-badge">CANLI</span>}
          </p>
          <span className="alarm-count" style={{ color: "var(--red)", fontSize: "0.78rem" }}>
            {alarms.filter((a) => a.level === "critical").length} alarm
          </span>
        </div>
        <div className="alarm-screen">
          {alarms.length === 0 && (
            <div className="log-empty">
              <p>Tuzaga dusen her baglanti burada goruntulenir. Izlemeyi baslatin veya tuzak aktif edin.</p>
            </div>
          )}
          {alarms.map((a) => (
            <div key={a.id} className="alarm-line" style={{ background: LEVEL_BG[a.level] }}>
              <span style={{ color: LEVEL_COLOR[a.level], fontSize: "0.55rem", marginTop: "0.4rem", flexShrink: 0 }}>&#9679;</span>
              <span className="mono" style={{ fontSize: "0.75rem", color: a.level === "critical" ? "#fca5a5" : a.level === "warning" ? "#fde68a" : "var(--text-secondary)", wordBreak: "break-all" }}>
                {a.line}
              </span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {hits.length > 0 && (
        <div className="card">
          <p className="section-title">Erisim Gecmisi ({hits.length})</p>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th>Tarih</th><th>Port</th><th>Servis</th><th>Kaynak IP</th><th>Veri</th></tr>
              </thead>
              <tbody>
                {hits.map((h) => (
                  <tr key={h.id}>
                    <td className="td-date">{formatDate(h.created_at)}</td>
                    <td><span className="pot-port mono">:{h.port}</span></td>
                    <td><span className="pot-service">{(h.service || "").toUpperCase()}</span></td>
                    <td style={{ color: "var(--red)", fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem" }}>{h.src_ip}:{h.src_port}</td>
                    <td><code className="mono" style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{h.data || "--"}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
