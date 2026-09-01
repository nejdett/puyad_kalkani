import React, { useState, useEffect, useCallback } from "react";
import { Play, Save, Bell, BellOff } from "lucide-react";
import { api } from "../api";
import "./SchedulerView.css";

function formatDate(dt) {
  if (!dt) return "—";
  try { return new Date(dt).toLocaleString("tr-TR"); }
  catch { return dt; }
}

export default function SchedulerView() {
  const [config, setConfig]   = useState(null);
  const [alerts, setAlerts]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState(null);
  const [form, setForm] = useState({ enabled: false, interval: "weekly", day_of_week: "mon", hour: 3, minute: 0 });

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [cfgRes, alertRes] = await Promise.all([
        api.get("/scheduler/config"),
        api.get("/scheduler/alerts"),
      ]);
      setConfig(cfgRes.data);
      setAlerts(alertRes.data.alerts);
      setForm({
        enabled:     cfgRes.data.enabled,
        interval:    cfgRes.data.interval    || "weekly",
        day_of_week: cfgRes.data.day_of_week || "mon",
        hour:        cfgRes.data.hour   ?? 3,
        minute:      cfgRes.data.minute ?? 0,
      });
    } catch (err) {
      showMessage("Ayarlar yüklenemedi: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.post("/scheduler/config", form);
      setConfig(res.data);
      showMessage(form.enabled ? "Otomatik tarama aktif edildi." : "Otomatik tarama devre dışı bırakıldı.");
    } catch (err) {
      showMessage("Kayıt başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      await api.post("/scheduler/run-now");
      showMessage("Tarama arka planda başlatıldı.");
    } catch (err) {
      showMessage("İşlem başarısız: " + err.message, "error");
    } finally {
      setTimeout(() => setRunning(false), 3000);
    }
  };

  const handleMarkRead = async () => {
    await api.post("/scheduler/alerts/read").catch(() => {});
    setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
  };

  const DAY_LABELS = {
    mon: "Pazartesi", tue: "Salı", wed: "Çarşamba",
    thu: "Perşembe",  fri: "Cuma", sat: "Cumartesi", sun: "Pazar"
  };

  return (
    <div className="scheduler-view">
      <div className="page-header">
        <div>
          <h1 className="page-title">Otomatik Tarama</h1>
          <p className="page-subtitle">Periyodik güvenlik taraması zamanlayıcısını yapılandırın.</p>
        </div>
        <button className="btn btn-primary" onClick={handleRunNow} disabled={running}>
          <Play size={13} />
          {running ? "Çalıştırılıyor..." : "Şimdi Çalıştır"}
        </button>
      </div>

      {message && (
        <div className={`msg ${message.type === "error" ? "msg-error" : "msg-success"}`}>
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Yükleniyor...</p></div>
      ) : (
        <>
          <div className="card config-box">
            <p className="section-title">Zamanlama Ayarları</p>

            <div className="toggle-row">
              <div className={`toggle-switch ${form.enabled ? "on" : ""}`}
                onClick={() => setForm((p) => ({ ...p, enabled: !p.enabled }))}>
                <div className="toggle-knob" />
              </div>
              <span className="toggle-label">{form.enabled ? "Aktif" : "Devre Dışı"}</span>
            </div>

            {form.enabled && (
              <div className="sched-form-grid">
                <div className="form-group">
                  <label className="form-label">Periyot</label>
                  <select className="form-input" value={form.interval}
                    onChange={(e) => setForm((p) => ({ ...p, interval: e.target.value }))}>
                    <option value="daily">Her Gün</option>
                    <option value="weekly">Her Hafta</option>
                    <option value="monthly">Her Ay</option>
                  </select>
                </div>
                {form.interval === "weekly" && (
                  <div className="form-group">
                    <label className="form-label">Gün</label>
                    <select className="form-input" value={form.day_of_week}
                      onChange={(e) => setForm((p) => ({ ...p, day_of_week: e.target.value }))}>
                      {Object.entries(DAY_LABELS).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="form-group">
                  <label className="form-label">Saat</label>
                  <input type="number" className="form-input" min="0" max="23" value={form.hour}
                    onChange={(e) => setForm((p) => ({ ...p, hour: parseInt(e.target.value) || 0 }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Dakika</label>
                  <input type="number" className="form-input" min="0" max="59" value={form.minute}
                    onChange={(e) => setForm((p) => ({ ...p, minute: parseInt(e.target.value) || 0 }))} />
                </div>
              </div>
            )}

            <div className="config-meta">
              {config?.last_run  && <span>Son çalışma: {formatDate(config.last_run)}</span>}
              {config?.next_run  && <span>Sonraki çalışma: {formatDate(config.next_run)}</span>}
            </div>

            <button className="btn btn-primary" onClick={handleSave} disabled={saving} style={{ marginTop: "1rem" }}>
              <Save size={13} />
              {saving ? "Kaydediliyor..." : "Kaydet"}
            </button>
          </div>

          <div className="card alerts-box">
            <div className="alerts-header">
              <p className="section-title">
                <Bell size={12} style={{ display: "inline", marginRight: "0.4rem" }} />
                Zamanlayıcı Uyarıları ({alerts.length})
              </p>
              {alerts.some((a) => !a.read) && (
                <button className="btn btn-ghost btn-sm" onClick={handleMarkRead}>
                  <BellOff size={12} /> Tümünü Okundu İşaretle
                </button>
              )}
            </div>

            {alerts.length === 0 ? (
              <div className="empty-state" style={{ padding: "2rem" }}>
                <Bell size={28} />
                <p>Kayıtlı uyarı bulunmuyor.</p>
              </div>
            ) : (
              <div className="alert-items">
                {alerts.map((a, i) => (
                  <div key={i} className={`alert-item ${a.read ? "read" : "unread"} ${a.score < 60 ? "critical" : ""}`}>
                    <div className="alert-item-body">
                      <p className="alert-item-msg">{a.message}</p>
                      <span className="alert-item-date">{formatDate(a.created_at)}</span>
                    </div>
                    {!a.read && <span className="unread-dot" />}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
