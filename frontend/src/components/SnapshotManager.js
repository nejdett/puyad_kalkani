import React, { useState, useEffect, useCallback } from "react";
import { Camera, RotateCcw, Trash2, Plus } from "lucide-react";
import { api } from "../api";
import "./SnapshotManager.css";

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const k = 1024, sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(dt) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("tr-TR");
}

export default function SnapshotManager() {
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [creating, setCreating]   = useState(false);
  const [rollingBack, setRollingBack] = useState(null);
  const [deleting, setDeleting]   = useState(null);
  const [label, setLabel]         = useState("");
  const [message, setMessage]     = useState(null);

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const fetchSnapshots = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/snapshots");
      setSnapshots(res.data.snapshots);
    } catch (err) {
      showMessage("Snapshot listesi alınamadı: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSnapshots(); }, [fetchSnapshots]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const res = await api.post("/snapshots", { label: label || "Manuel Yedek" });
      showMessage(`Snapshot alındı: ${formatBytes(res.data.size_bytes)}`);
      setLabel("");
      fetchSnapshots();
    } catch (err) {
      showMessage("Snapshot alınamadı: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setCreating(false);
    }
  };

  const handleRollback = async (snap) => {
    if (!window.confirm(`"${snap.label}" snapshot'ına geri dönmek istediğinizden emin misiniz?\n\nMevcut /etc dizini otomatik olarak yedeklenecek.`)) return;
    setRollingBack(snap.id);
    try {
      const res = await api.post(`/snapshots/${snap.id}/rollback`);
      if (res.data.success) {
        showMessage(res.data.message, "success");
      } else {
        showMessage(res.data.message || "Geri yükleme başarısız.", "error");
      }
      fetchSnapshots();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Bilinmeyen hata";
      showMessage("Rollback basarışız: " + detail, "error");
    } finally {
      setRollingBack(null);
    }
  };

  const handleDelete = async (snap) => {
    if (!window.confirm(`"${snap.label}" snapshot'ını silmek istediğinizden emin misiniz?`)) return;
    setDeleting(snap.id);
    try {
      await api.delete(`/snapshots/${snap.id}`);
      showMessage("Snapshot silindi.");
      setSnapshots((prev) => prev.filter((s) => s.id !== snap.id));
    } catch (err) {
      showMessage("Silme başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="snapshot-manager">
      <div className="page-header">
        <div>
          <h1 className="page-title">Snapshot / Rollback</h1>
          <p className="page-subtitle">/etc dizininin anlık yedeğini alın ve geri yükleyin.</p>
        </div>
      </div>

      {message && (
        <div className={`msg ${message.type === "error" ? "msg-error" : "msg-success"}`}>
          {message.text}
        </div>
      )}

      <div className="card create-box">
        <p className="section-title">Yeni Snapshot</p>
        <div className="create-row">
          <input
            className="form-input"
            placeholder="Etiket (opsiyonel)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
            <Camera size={14} />
            {creating ? "Alınıyor..." : "Snapshot Al"}
          </button>
        </div>
        <p className="hint-text">Düzeltme işlemleri otomatik snapshot alır. Manuel yedek için bu formu kullanın.</p>
      </div>

      <div className="card">
        <p className="section-title">Mevcut Snapshot'lar ({snapshots.length})</p>
        {loading ? (
          <div className="loading-state"><div className="spinner" /><p>Yükleniyor...</p></div>
        ) : snapshots.length === 0 ? (
          <div className="empty-state"><Camera size={36} /><p>Kayıtlı snapshot bulunmuyor.</p></div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Etiket</th>
                  <th>Boyut</th>
                  <th>Tarih</th>
                  <th>İşlem</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((snap) => (
                  <tr key={snap.id}>
                    <td>
                      <div className="snap-label">{snap.label}</div>
                      <code className="snap-id mono">{snap.id.slice(0, 8)}...</code>
                    </td>
                    <td className="snap-size">{formatBytes(snap.size_bytes)}</td>
                    <td className="td-date">{formatDate(snap.created_at)}</td>
                    <td>
                      <div className="row-actions">
                        <button className="btn btn-success btn-sm"
                          onClick={() => handleRollback(snap)}
                          disabled={rollingBack === snap.id || deleting === snap.id}>
                          <RotateCcw size={12} />
                          {rollingBack === snap.id ? "Yükleniyor..." : "Geri Yükle"}
                        </button>
                        <button className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(snap)}
                          disabled={rollingBack === snap.id || deleting === snap.id}>
                          <Trash2 size={12} />
                          {deleting === snap.id ? "..." : "Sil"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
