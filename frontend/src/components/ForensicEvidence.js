import React, { useState, useEffect, useCallback } from "react";
import {
  FileSearch, Camera, Trash2, Eye, X, RefreshCw,
  Wifi, Cpu, Users, Terminal, ShieldCheck, AlertTriangle
} from "lucide-react";
import { api } from "../api";
import "./ForensicEvidence.css";

const REASON_STYLES = {
  "Manual Trigger": { cls: "badge-low", icon: Terminal },
  "HoneyPot Alert": { cls: "badge-high", icon: AlertTriangle },
  "BruteForce Attack": { cls: "badge-medium", icon: ShieldCheck },
};

const TABS = [
  { key: "connections", label: "Aktif Bağlantılar", icon: Wifi },
  { key: "processes", label: "Süreçler", icon: Cpu },
  { key: "sessions", label: "Oturumlar", icon: Users },
  { key: "raw", label: "Ham JSON", icon: Terminal },
];

function EvidenceModal({ evidence, onClose }) {
  const [activeTab, setActiveTab] = useState("connections");

  if (!evidence) return null;
  const data = evidence.evidence_data || {};

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Kanıt Detayı — #{evidence.id}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="modal-tabs">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button key={tab.key}
                className={`modal-tab ${activeTab === tab.key ? "active" : ""}`}
                onClick={() => setActiveTab(tab.key)}>
                <Icon size={13} />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="modal-body">
          {activeTab === "connections" && (
            <pre className="evidence-pre">{data.active_connections || "Veri bulunamadı."}</pre>
          )}
          {activeTab === "processes" && (
            <pre className="evidence-pre">{data.running_processes || "Veri bulunamadı."}</pre>
          )}
          {activeTab === "sessions" && (
            <div>
              <h4 className="evidence-sub">Aktif Oturumlar</h4>
              <pre className="evidence-pre">{data.logged_users || "Veri bulunamadı."}</pre>
              <h4 className="evidence-sub">Son Girişler</h4>
              <pre className="evidence-pre">{data.last_logins || "Veri bulunamadı."}</pre>
            </div>
          )}
          {activeTab === "raw" && (
            <pre className="evidence-pre raw">{JSON.stringify(data, null, 2)}</pre>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ForensicEvidence() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [message, setMessage] = useState(null);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [detailLoading, setDetailLoading] = useState(null);

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/forensic/history");
      setHistory(res.data.history);
    } catch (err) {
      showMessage("Geçmiş yüklenemedi.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const handleCollect = async () => {
    setCollecting(true);
    try {
      await api.post("/forensic/trigger", { server_id: 1, trigger_reason: "Manual Trigger" });
      showMessage("Adli kanıt toplandı.");
      loadHistory();
    } catch (err) {
      showMessage("Toplama başarısız.", "error");
    } finally {
      setCollecting(false);
    }
  };

  const handleDetail = async (id) => {
    setDetailLoading(id);
    try {
      const res = await api.get(`/forensic/evidence/${id}`);
      setSelectedEvidence(res.data);
    } catch (err) {
      showMessage("Detay yüklenemedi.", "error");
    } finally {
      setDetailLoading(null);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Bu kanıt kaydını silmek istediğinize emin misiniz?")) return;
    try {
      await api.delete(`/forensic/evidence/${id}`);
      showMessage("Kayıt silindi.");
      loadHistory();
    } catch (err) {
      showMessage("Silinemedi.", "error");
    }
  };

  return (
    <div className="forensic-page">
      <div className="forensic-header">
        <div>
          <h1 className="page-title">Adli Bilişim</h1>
          <p className="page-subtitle">Sistem adli kanıt paketlerini toplayın ve inceleyin.</p>
        </div>
        <button className="btn btn-primary" onClick={handleCollect} disabled={collecting}>
          <Camera size={14} />
          {collecting ? "Toplanıyor..." : "Anlık Kanıt Topla"}
        </button>
      </div>

      {message && (
        <div className={`msg ${message.type === "error" ? "msg-error" : "msg-success"}`}>
          {message.type === "error" ? <AlertTriangle size={14} /> : <ShieldCheck size={14} />}
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>Yükleniyor...</p>
        </div>
      ) : history.length === 0 ? (
        <div className="empty-state">
          <FileSearch size={44} />
          <p>Henüz adli kanıt kaydı bulunmuyor.</p>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Tetikleme Sebebi</th>
                <th>Sunucu ID</th>
                <th>Tarih</th>
                <th>İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => {
                const style = REASON_STYLES[item.trigger_reason] || { cls: "badge-low", icon: Terminal };
                const ReasonIcon = style.icon;
                return (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>
                      <span className={`badge ${style.cls}`}>
                        <ReasonIcon size={11} />
                        {item.trigger_reason}
                      </span>
                    </td>
                    <td>{item.server_id}</td>
                    <td className="mono">{item.created_at}</td>
                    <td>
                      <div className="table-actions">
                        <button className="btn btn-ghost btn-sm"
                          onClick={() => handleDetail(item.id)}
                          disabled={detailLoading === item.id}>
                          <Eye size={13} />
                          {detailLoading === item.id ? "Yükleniyor..." : "İncele"}
                        </button>
                        <button className="btn btn-ghost btn-sm"
                          onClick={() => handleDelete(item.id)}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedEvidence && (
        <EvidenceModal evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />
      )}
    </div>
  );
}
