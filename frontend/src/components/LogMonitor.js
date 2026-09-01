import React, { useState, useEffect, useRef, useCallback } from "react";
import { Play, Square, Search } from "lucide-react";
import { api } from "../api";
import "./LogMonitor.css";

const LEVEL_LABELS = { all: "Tümü", critical: "Kritik", warning: "Uyarı", info: "Bilgi" };

export default function LogMonitor() {
  const [logs, setLogs]             = useState([]);
  const [streaming, setStreaming]   = useState(false);
  const [activeLog, setActiveLog]   = useState(null);
  const [filter, setFilter]         = useState("all");
  const [search, setSearch]         = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef      = useRef(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    api.get("/logs/active")
      .then((r) => {
        const d = r.data || r;
        setActiveLog(d.path || (d.type === "journald" ? "journalctl (systemd)" : null));
      })
      .catch(() => setActiveLog(null));
  }, []);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const startStream = useCallback(() => {
    if (eventSourceRef.current) eventSourceRef.current.close();
    setLogs([]);
    setStreaming(true);
    const es = new EventSource("/api/logs/stream?lines_back=100");
    eventSourceRef.current = es;
    es.onmessage = (e) => {
      const parts = e.data.split("|LEVEL:");
      setLogs((prev) => [...prev.slice(-500), { line: parts[0], level: parts[1] || "info", id: Date.now() + Math.random() }]);
    };
    es.onerror = () => { setStreaming(false); es.close(); };
  }, []);

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) { eventSourceRef.current.close(); eventSourceRef.current = null; }
    setStreaming(false);
  }, []);

  useEffect(() => () => stopStream(), [stopStream]);

  const filteredLogs = logs.filter((log) => {
    const levelMatch  = filter === "all" || log.level === filter;
    const searchMatch = !search || log.line.toLowerCase().includes(search.toLowerCase());
    return levelMatch && searchMatch;
  });

  const LEVEL_COLOR = { critical: "var(--red)", warning: "var(--yellow)", info: "var(--text-muted)" };
  const LEVEL_BG    = { critical: "rgba(239,68,68,0.06)", warning: "rgba(245,158,11,0.04)", info: "transparent" };

  return (
    <div className="log-monitor">
      <div className="page-header">
        <div>
          <h1 className="page-title">Canlı Log İzleme</h1>
          <p className="page-subtitle mono" style={{ fontSize: "0.78rem" }}>
            {activeLog || "Log kaynağı bulunamadı"}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {!streaming ? (
            <button className="btn btn-success" onClick={startStream}>
              <Play size={13} /> Başlat
            </button>
          ) : (
            <button className="btn btn-danger" onClick={stopStream}>
              <Square size={13} /> Durdur
            </button>
          )}
        </div>
      </div>

      <div className="log-toolbar card">
        <div className="filter-group">
          {["all", "critical", "warning", "info"].map((f) => (
            <button key={f} className={`filter-chip ${filter === f ? "active" : ""} chip-${f}`}
              onClick={() => setFilter(f)}>
              {LEVEL_LABELS[f]}
              {f !== "all" && <span className="chip-count">{logs.filter((l) => l.level === f).length}</span>}
            </button>
          ))}
        </div>
        <div className="log-search-wrap">
          <Search size={13} className="search-icon" />
          <input className="log-search" placeholder="Satırlarda ara..."
            value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <label className="autoscroll-toggle">
          <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />
          Otomatik kaydır
        </label>
      </div>

      <div className="log-screen">
        {!streaming && logs.length === 0 && (
          <div className="log-empty">
            <p>Akışı başlatmak için "Başlat" butonunu kullanın.</p>
          </div>
        )}
        {filteredLogs.map((log) => (
          <div key={log.id} className={`log-line log-${log.level}`} style={{ background: LEVEL_BG[log.level] }}>
            <span className="log-dot" style={{ color: LEVEL_COLOR[log.level] }}>●</span>
            <span className="log-text mono">{log.line}</span>
          </div>
        ))}
        {streaming && (
          <div className="log-line log-streaming">
            <span className="log-dot blink" style={{ color: "var(--green)" }}>●</span>
            <span className="log-text mono" style={{ color: "var(--green)" }}>Canlı izleniyor</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {logs.length > 0 && (
        <div className="log-stats">
          <span>Toplam: <strong>{logs.length}</strong></span>
          <span style={{ color: "var(--red)" }}>Kritik: <strong>{logs.filter((l) => l.level === "critical").length}</strong></span>
          <span style={{ color: "var(--yellow)" }}>Uyarı: <strong>{logs.filter((l) => l.level === "warning").length}</strong></span>
        </div>
      )}
    </div>
  );
}
