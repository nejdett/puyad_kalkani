import React, { useState, useEffect, useCallback } from "react";
import { RefreshCw, FileDown, TrendingUp, Wrench, ScanLine } from "lucide-react";
import { api } from "../api";
import "./HistoryView.css";

function formatDate(dt) {
  if (!dt) return "—";
  try { return new Date(dt).toLocaleString("tr-TR"); }
  catch { return dt; }
}

function ScoreBar({ score }) {
  const color = score >= 80 ? "var(--green)" : score >= 50 ? "var(--yellow)" : "var(--red)";
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-bg">
        <div className="score-bar-fill" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="score-label" style={{ color }}>{score}</span>
    </div>
  );
}

export default function HistoryView() {
  const [tab, setTab]                   = useState("scans");
  const [scans, setScans]               = useState([]);
  const [fixes, setFixes]               = useState([]);
  const [trend, setTrend]               = useState([]);
  const [loading, setLoading]           = useState(true);
  const [downloadingPdf, setDownloadingPdf] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [scanRes, fixRes, trendRes] = await Promise.all([
        api.get("/history/scans?limit=20"),
        api.get("/history/fixes?limit=50"),
        api.get("/history/trend"),
      ]);
      setScans(scanRes.data.history);
      setFixes(fixRes.data.history);
      setTrend(trendRes.data.trend);
    } catch (err) {
      console.error("Geçmiş yüklenemedi:", err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleDownloadPdf = useCallback(async (scanId = null) => {
    setDownloadingPdf(scanId || "latest");
    try {
      const url = scanId ? `/report/pdf?scan_id=${scanId}` : "/report/pdf";
      const res = await api.get(url, { responseType: "blob" });
      const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `puyad-kalkani-rapor-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("PDF hatası:", err.message);
    } finally {
      setDownloadingPdf(null);
    }
  }, []);

  return (
    <div className="history-view">
      <div className="page-header">
        <div>
          <h1 className="page-title">Geçmiş ve Analiz</h1>
          <p className="page-subtitle">Tarama ve düzeltme geçmişini inceleyin.</p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="btn btn-ghost"
            onClick={() => handleDownloadPdf(null)}
            disabled={downloadingPdf === "latest" || scans.length === 0}>
            <FileDown size={14} />
            {downloadingPdf === "latest" ? "Hazırlanıyor..." : "PDF Rapor"}
          </button>
          <button className="btn btn-secondary" onClick={fetchData}>
            <RefreshCw size={14} />
            Yenile
          </button>
        </div>
      </div>

      {trend.length > 0 && (
        <div className="card trend-box">
          <p className="section-title">
            <TrendingUp size={13} style={{ display: "inline", marginRight: "0.4rem" }} />
            Güvenlik Skoru Trendi
          </p>
          <div className="trend-bars">
            {trend.map((t, i) => {
              const color = t.score >= 80 ? "var(--green)" : t.score >= 50 ? "var(--yellow)" : "var(--red)";
              return (
                <div key={i} className="trend-bar-item">
                  <div className="trend-bar-outer">
                    <div className="trend-bar-inner"
                      style={{ height: `${t.score}%`, background: color }}
                      title={`${t.score} — ${formatDate(t.created_at)}`} />
                  </div>
                  <span className="trend-score" style={{ color }}>{t.score}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="tab-bar">
        <button className={`tab-btn ${tab === "scans" ? "active" : ""}`} onClick={() => setTab("scans")}>
          <ScanLine size={13} /> Tarama Geçmişi ({scans.length})
        </button>
        <button className={`tab-btn ${tab === "fixes" ? "active" : ""}`} onClick={() => setTab("fixes")}>
          <Wrench size={13} /> Düzeltme Geçmişi ({fixes.length})
        </button>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Yükleniyor...</p></div>
      ) : tab === "scans" ? (
        scans.length === 0 ? (
          <div className="empty-state"><ScanLine size={36} /><p>Kayıtlı tarama bulunmuyor.</p></div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tarih</th><th>Toplam</th><th>Uyarı</th><th>Güvenli</th><th>Skor</th><th>Rapor</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.id}>
                    <td className="td-date">{formatDate(s.created_at)}</td>
                    <td>{s.total}</td>
                    <td style={{ color: "var(--red)" }}>{s.warnings}</td>
                    <td style={{ color: "var(--green)" }}>{s.ok_count}</td>
                    <td><ScoreBar score={s.score} /></td>
                    <td>
                      <button className="btn btn-ghost btn-sm"
                        onClick={() => handleDownloadPdf(s.id)}
                        disabled={downloadingPdf === s.id}>
                        <FileDown size={12} />
                        {downloadingPdf === s.id ? "..." : "PDF"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        fixes.length === 0 ? (
          <div className="empty-state"><Wrench size={36} /><p>Kayıtlı düzeltme işlemi bulunmuyor.</p></div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th>Tarih</th><th>Kural</th><th>Durum</th><th>Snapshot</th></tr>
              </thead>
              <tbody>
                {fixes.map((f) => (
                  <tr key={f.id}>
                    <td className="td-date">{formatDate(f.created_at)}</td>
                    <td>
                      <div className="fix-rule-name">{f.rule_name}</div>
                      <code className="fix-rule-id mono">{f.rule_id}</code>
                    </td>
                    <td>
                      <span className={`badge ${f.status === "success" ? "badge-ok" : "badge-high"}`}>
                        {f.status === "success" ? "Başarılı" : "Başarısız"}
                      </span>
                    </td>
                    <td>
                      {f.snapshot_id
                        ? <code className="mono" style={{ color: "var(--accent-hover)", fontSize: "0.72rem" }}>{f.snapshot_id.slice(0, 8)}...</code>
                        : <span style={{ color: "var(--text-muted)" }}>—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
