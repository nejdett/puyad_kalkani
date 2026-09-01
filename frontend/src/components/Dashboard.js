import React, { useState, useCallback, useEffect } from "react";
import {
  ScanLine, Wrench, EyeOff, Eye, RefreshCw,
  FileDown, ShieldCheck, ShieldX, ShieldOff,
  AlertTriangle, CheckCircle, Clock, X
} from "lucide-react";
import { scanSystem, scanSingleRule, fixRule, ignoreRule, unignoreRule, getIgnored, getRules, api } from "../api";
import "./Dashboard.css";

const SEV_CONFIG = {
  high:   { label: "Yüksek", cls: "badge-high" },
  medium: { label: "Orta",   cls: "badge-medium" },
  low:    { label: "Düşük",  cls: "badge-low" },
};

function SummaryCard({ label, value, color, icon: Icon }) {
  return (
    <div className="summary-card">
      <div className="summary-card-icon" style={{ color }}>
        <Icon size={20} />
      </div>
      <div>
        <div className="summary-value" style={{ color }}>{value}</div>
        <div className="summary-label">{label}</div>
      </div>
    </div>
  );
}

function AlertRow({ result, onFix, onIgnore, onRescan, fixing, ignoring, rescanning }) {
  const sev = SEV_CONFIG[result.severity] || { label: result.severity, cls: "" };

  return (
    <div className={`alert-row status-${result.status}`}>
      <div className="alert-status-bar" />
      <div className="alert-info">
        <div className="alert-header">
          <span className="alert-name">{result.name}</span>
          <span className="alert-category">{result.category}</span>
          <span className={`badge ${sev.cls}`}>{sev.label}</span>
        </div>
        <p className="alert-description">{result.description}</p>
        {result.output && <code className="alert-output mono">{result.output}</code>}
      </div>
      <div className="alert-actions">
        {result.status === "warning" && (
          <>
            <button className="btn btn-success" onClick={() => onFix(result.id)}
              disabled={fixing === result.id || ignoring === result.id}>
              <Wrench size={13} />
              {fixing === result.id ? "İşleniyor..." : "Düzelt"}
            </button>
            <button className="btn btn-ghost" onClick={() => onIgnore(result.id)}
              disabled={fixing === result.id || ignoring === result.id}>
              <EyeOff size={13} />
              {ignoring === result.id ? "İşleniyor..." : "Görmezden Gel"}
            </button>
          </>
        )}
        {result.status === "ok" && (
          <span className="status-label ok">
            <CheckCircle size={13} /> Güvenli
          </span>
        )}
        {result.status === "timeout" && (
          <button className="btn btn-secondary" onClick={() => onRescan(result.id)}
            disabled={rescanning === result.id}>
            <RefreshCw size={13} />
            {rescanning === result.id ? "Taranıyor..." : "Yeniden Tara"}
          </button>
        )}
      </div>
    </div>
  );
}

function IgnoredRow({ rule, onUnignore, unignoring }) {
  const sev = SEV_CONFIG[rule.severity] || { label: rule.severity, cls: "" };
  return (
    <div className="alert-row status-ignored">
      <div className="alert-status-bar" />
      <div className="alert-info">
        <div className="alert-header">
          <span className="alert-name">{rule.name}</span>
          <span className="alert-category">{rule.category}</span>
          <span className={`badge ${sev.cls}`}>{sev.label}</span>
        </div>
        <p className="alert-description">{rule.description}</p>
      </div>
      <div className="alert-actions">
        <button className="btn btn-ghost" onClick={() => onUnignore(rule.id)}
          disabled={unignoring === rule.id}>
          <Eye size={13} />
          {unignoring === rule.id ? "İşleniyor..." : "Aktif Et"}
        </button>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [scanResults, setScanResults]     = useState(null);
  const [ignoredRules, setIgnoredRules]   = useState([]);
  const [summary, setSummary]             = useState(null);
  const [scanning, setScanning]           = useState(false);
  const [fixing, setFixing]               = useState(null);
  const [ignoring, setIgnoring]           = useState(null);
  const [unignoring, setUnignoring]       = useState(null);
  const [rescanning, setRescanning]       = useState(null);
  const [message, setMessage]             = useState(null);
  const [filter, setFilter]               = useState("all");
  const [criticalAlert, setCriticalAlert] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  useEffect(() => {
    api.get("/scheduler/alerts")
      .then((res) => {
        const unread = res.data.alerts.filter((a) => !a.read);
        if (unread.length > 0) setCriticalAlert(unread[0]);
      })
      .catch(() => {});
  }, []);

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const handleScan = useCallback(async () => {
    setScanning(true);
    setScanResults(null);
    setIgnoredRules([]);
    setMessage(null);
    try {
      const [scanRes, ignoredRes, allRulesRes] = await Promise.all([
        scanSystem(), getIgnored(), getRules(),
      ]);
      setScanResults(scanRes.data.results);
      setSummary(scanRes.data.summary);
      const ids = ignoredRes.data.ignored;
      setIgnoredRules(allRulesRes.data.rules.filter((r) => ids.includes(r.id)));
    } catch (err) {
      showMessage("Tarama başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setScanning(false);
    }
  }, []);

  const handleFix = useCallback(async (ruleId) => {
    setFixing(ruleId);
    try {
      const res = await fixRule(ruleId);
      showMessage(res.data.message);
      setScanResults((prev) => prev.map((r) => r.id === ruleId ? { ...r, status: "ok" } : r));
      setSummary((prev) => prev ? { ...prev, warnings: prev.warnings - 1, ok: prev.ok + 1 } : prev);
    } catch (err) {
      showMessage("Düzeltme başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setFixing(null);
    }
  }, []);

  const handleIgnore = useCallback(async (ruleId) => {
    setIgnoring(ruleId);
    try {
      await ignoreRule(ruleId);
      showMessage("Kural görmezden gelinenler listesine alındı.");
      const rule = scanResults.find((r) => r.id === ruleId);
      setScanResults((prev) => prev.filter((r) => r.id !== ruleId));
      setSummary((prev) => prev ? { ...prev, total: prev.total - 1, warnings: prev.warnings - 1 } : prev);
      if (rule) setIgnoredRules((prev) => [...prev, rule]);
    } catch (err) {
      showMessage("İşlem başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setIgnoring(null);
    }
  }, [scanResults]);

  const handleUnignore = useCallback(async (ruleId) => {
    setUnignoring(ruleId);
    try {
      await unignoreRule(ruleId);
      showMessage("Kural aktif edildi. Yeniden tarama yapınız.");
      setIgnoredRules((prev) => prev.filter((r) => r.id !== ruleId));
    } catch (err) {
      showMessage("İşlem başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setUnignoring(null);
    }
  }, []);

  const handleRescan = useCallback(async (ruleId) => {
    setRescanning(ruleId);
    try {
      const res = await scanSingleRule(ruleId);
      const updated = res.data;
      setScanResults((prev) => prev.map((r) => r.id === ruleId ? updated : r));
      showMessage(updated.status === "ok" ? "Kural geçti." : "Kural uyarı veriyor.", updated.status === "ok" ? "success" : "error");
    } catch (err) {
      showMessage("Tarama başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setRescanning(null);
    }
  }, []);

  const handleDownloadPdf = useCallback(async () => {
    setDownloadingPdf(true);
    try {
      const res = await api.get("/report/pdf", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `puyad-kalkani-rapor-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      showMessage("PDF oluşturulamadı: " + err.message, "error");
    } finally {
      setDownloadingPdf(false);
    }
  }, []);

  const filteredResults = scanResults
    ? scanResults.filter((r) => filter === "all" || r.status === filter)
    : [];

  const FILTERS = [
    { key: "all",     label: "Tümü",               count: scanResults?.length },
    { key: "warning", label: "Uyarılar",            count: scanResults?.filter((r) => r.status === "warning").length },
    { key: "ok",      label: "Güvenli",             count: scanResults?.filter((r) => r.status === "ok").length },
    { key: "ignored", label: "Görmezden Gelinen",   count: ignoredRules.length },
  ];

  return (
    <div className="dashboard">
      {criticalAlert && (
        <div className="critical-banner">
          <AlertTriangle size={16} />
          <div>
            <strong>Güvenlik Uyarısı</strong>
            <p>{criticalAlert.message}</p>
          </div>
          <button className="critical-close" onClick={async () => {
            await api.post("/scheduler/alerts/read").catch(() => {});
            setCriticalAlert(null);
          }}>
            <X size={14} />
          </button>
        </div>
      )}

      <div className="dashboard-header">
        <div>
          <h1 className="page-title">Güvenlik Taraması</h1>
          <p className="page-subtitle">Sistem sıkılaştırma durumunu kontrol edin ve yönetin.</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-ghost" onClick={handleDownloadPdf}
            disabled={downloadingPdf || !scanResults}>
            <FileDown size={14} />
            {downloadingPdf ? "Hazırlanıyor..." : "PDF Rapor"}
          </button>
          <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
            <ScanLine size={14} />
            {scanning ? "Taranıyor..." : "Taramayı Başlat"}
          </button>
        </div>
      </div>

      {message && (
        <div className={`msg ${message.type === "error" ? "msg-error" : "msg-success"}`}>
          {message.type === "error" ? <ShieldX size={14} /> : <ShieldCheck size={14} />}
          {message.text}
        </div>
      )}

      {summary && (
        <div className="summary-grid">
          <SummaryCard label="Toplam Kural"      value={summary.total}       color="var(--accent-hover)" icon={ScanLine} />
          <SummaryCard label="Uyarı"             value={summary.warnings}    color="var(--red)"          icon={ShieldX} />
          <SummaryCard label="Güvenli"           value={summary.ok}          color="var(--green)"        icon={ShieldCheck} />
          <SummaryCard label="Görmezden Gelinen" value={ignoredRules.length} color="var(--text-muted)"   icon={ShieldOff} />
        </div>
      )}

      {scanResults && (
        <div className="filter-bar">
          {FILTERS.map((f) => (
            <button key={f.key}
              className={`filter-btn ${filter === f.key ? "active" : ""}`}
              onClick={() => setFilter(f.key)}>
              {f.label}
              <span className="filter-count">{f.count ?? 0}</span>
            </button>
          ))}
        </div>
      )}

      {scanning && (
        <div className="loading-state">
          <div className="spinner" />
          <p>Sistem taranıyor, lütfen bekleyin...</p>
        </div>
      )}

      {!scanning && filter === "ignored" && (
        ignoredRules.length === 0 ? (
          <div className="empty-state">
            <ShieldOff size={40} />
            <p>Görmezden gelinen kural bulunmuyor.</p>
          </div>
        ) : (
          <div className="alert-list">
            {ignoredRules.map((rule) => (
              <IgnoredRow key={rule.id} rule={rule} onUnignore={handleUnignore} unignoring={unignoring} />
            ))}
          </div>
        )
      )}

      {!scanning && filter !== "ignored" && scanResults && filteredResults.length === 0 && (
        <div className="empty-state">
          <ShieldCheck size={40} />
          <p>Bu kategoride sonuç bulunmuyor.</p>
        </div>
      )}

      {!scanning && filter !== "ignored" && filteredResults.length > 0 && (
        <div className="alert-list">
          {filteredResults.map((result) => (
            <AlertRow key={result.id} result={result}
              onFix={handleFix} onIgnore={handleIgnore} onRescan={handleRescan}
              fixing={fixing} ignoring={ignoring} rescanning={rescanning} />
          ))}
        </div>
      )}

      {!scanning && !scanResults && (
        <div className="empty-state">
          <ScanLine size={44} />
          <p>Sistem analizini başlatmak için "Taramayı Başlat" butonunu kullanın.</p>
        </div>
      )}
    </div>
  );
}
