import React, { useState, useEffect, useCallback } from "react";
import {
  Server, Plus, Trash2, RefreshCw, Wifi, WifiOff,
  ShieldCheck, Monitor, AlertTriangle
} from "lucide-react";
import { api } from "../api";
import "./ServerManagement.css";

export default function ServerManagement() {
  const [servers, setServers] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [probing, setProbing] = useState(false);
  const [scanning, setScanning] = useState(null);
  const [message, setMessage] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", ip_address: "", port: 8000 });

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [serversRes, configRes] = await Promise.all([
        api.get("/servers"),
        api.get("/config"),
      ]);
      setServers(serversRes.data.servers);
      setConfig(configRes.data);
    } catch (err) {
      showMessage("Veriler yüklenemedi: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleAddServer = async (e) => {
    e.preventDefault();
    if (!form.name || !form.ip_address) {
      showMessage("Sunucu adı ve IP zorunludur.", "error");
      return;
    }
    try {
      await api.post("/servers", form);
      showMessage("Sunucu eklendi.");
      setForm({ name: "", ip_address: "", port: 8000 });
      setShowForm(false);
      loadData();
    } catch (err) {
      showMessage("Eklenemedi: " + (err.response?.data?.detail || err.message), "error");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Bu sunucuyu silmek istediğinize emin misiniz?")) return;
    try {
      await api.delete(`/servers/${id}`);
      showMessage("Sunucu silindi.");
      loadData();
    } catch (err) {
      showMessage("Silinemedi: " + (err.response?.data?.detail || err.message), "error");
    }
  };

  const handleProbeAll = async () => {
    setProbing(true);
    try {
      const res = await api.get("/servers/probe-all");
      const probeResults = res.data?.results || [];
      if (probeResults.length > 0) {
        setServers((prev) => prev.map((s) => {
          const pr = probeResults.find((r) => r.id === s.id);
          return pr ? { ...s, status: pr.status, last_score: pr.last_score ?? s.last_score } : s;
        }));
        const scanned = probeResults.filter((r) => r.last_score !== undefined && r.last_score !== null);
        if (scanned.length > 0) {
          showMessage(`${scanned.length} sunucu tarandı, sonuçlar güncellendi.`);
        } else {
          showMessage("Tüm sunucular kontrol edildi.");
        }
      } else {
        showMessage("Tüm sunucular kontrol edildi.");
      }
    } catch (err) {
      showMessage("Kontrol başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setProbing(false);
    }
  };

  const handleScan = async (serverId) => {
    setScanning(serverId);
    try {
      let res;
      if (serverId === 1) {
        // yerel sunucu — doğrudan POST ile tara
        res = await api.post("/scan", { server_id: 1 }, { timeout: 120000 });
      } else {
        // uzak sunucu
        res = await api.get("/scan", { params: { server_id: serverId }, timeout: 120000 });
      }
      const score = res.data.summary?.score ?? 0;
      setServers((prev) => prev.map((s) => s.id === serverId ? { ...s, last_score: score } : s));
      showMessage(`Tarama tamamlandı. Skor: ${score}/100`);
    } catch (err) {
      console.error("Scan error:", err);
      const detail = err.response?.data?.detail || err.message || "Bilinmeyen hata";
      showMessage("Tarama başarısız: " + detail, "error");
    } finally {
      setScanning(null);
    }
  };

  const handleToggleMode = async () => {
    const newMode = config?.RUN_MODE === "controller" ? "standalone" : "controller";
    try {
      await api.patch("/config", { RUN_MODE: newMode });
      setConfig((prev) => ({ ...prev, RUN_MODE: newMode }));
      showMessage(`Mod değiştirildi: ${newMode}`);
    } catch (err) {
      showMessage("Mod değiştirilemedi.", "error");
    }
  };

  const isController = config?.RUN_MODE === "controller";

  return (
    <div className="server-management">
      <div className="sm-header">
        <div>
          <h1 className="page-title">Sunucu Yönetimi</h1>
          <p className="page-subtitle">Tüm sunucuları tek panelden yönetin.</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-ghost" onClick={handleProbeAll} disabled={probing}>
            <RefreshCw size={14} className={probing ? "spin" : ""} />
            {probing ? "Kontrol Ediliyor..." : "Tümünü Kontrol Et"}
          </button>
          {isController && (
            <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
              <Plus size={14} />
              Sunucu Ekle
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className={`msg ${message.type === "error" ? "msg-error" : "msg-success"}`}>
          {message.type === "error" ? <AlertTriangle size={14} /> : <ShieldCheck size={14} />}
          {message.text}
        </div>
      )}

      {config && (
        <div className="mode-banner">
          <Monitor size={16} />
          <span>
            Çalışma Modu: <strong>{isController ? "Controller" : "Standalone"}</strong>
          </span>
          <button className="btn btn-ghost btn-sm" onClick={handleToggleMode}>
            {isController ? "Standalone Moduna Geç" : "Controller Moduna Geç"}
          </button>
        </div>
      )}

      {showForm && (
        <form className="add-server-form" onSubmit={handleAddServer}>
          <input
            type="text"
            placeholder="Sunucu Adı"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            type="text"
            placeholder="IP Adresi"
            value={form.ip_address}
            onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
          />
          <input
            type="number"
            placeholder="Port"
            value={form.port}
            onChange={(e) => setForm({ ...form, port: parseInt(e.target.value) || 8000 })}
          />
          <button type="submit" className="btn btn-primary">Ekle</button>
          <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>İptal</button>
        </form>
      )}

      {loading ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>Sunucular yükleniyor...</p>
        </div>
      ) : servers.length === 0 ? (
        <div className="empty-state">
          <Server size={44} />
          <p>Henüz sunucu eklenmemiş.</p>
        </div>
      ) : (
        <div className="servers-grid">
          {servers.map((srv) => (
            <div key={srv.id} className={`server-card ${srv.status}`}>
              <div className="server-card-header">
                <div className="server-info">
                  <Server size={18} />
                  <div>
                    <h3 className="server-name">{srv.name}</h3>
                    <code className="server-ip">{srv.ip_address}:{srv.port}</code>
                  </div>
                </div>
                <span className={`status-badge ${srv.status}`}>
                  {srv.status === "online" ? <Wifi size={12} /> : <WifiOff size={12} />}
                  {srv.status === "online" ? "Online" : "Offline"}
                </span>
              </div>

              <div className="server-card-body">
                <div className="server-score">
                  <span className="score-label">Son Tarama</span>
                  <span className={`score-value ${srv.last_score >= 80 ? "good" : srv.last_score >= 50 ? "warn" : "bad"}`}>
                    {srv.last_score}/100
                  </span>
                </div>
              </div>

              <div className="server-card-actions">
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleScan(srv.id)}
                  disabled={scanning === srv.id || srv.status === "offline"}
                >
                  {scanning === srv.id ? "Taranıyor..." : "Şimdi Tara"}
                </button>
                {srv.id !== 1 && (
                  <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(srv.id)}>
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
