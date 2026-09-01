import React, { useState, useEffect, useCallback } from "react";
import { Plus, X, Trash2, Pencil } from "lucide-react";
import { getRules, addRule, updateRule, deleteRule } from "../api";
import "./RuleManager.css";

const EMPTY_FORM = {
  id: "", name: "", category: "", severity: "medium",
  check_command: "", fix_command: "", description: "",
};

const SEV_CONFIG = {
  high:   { label: "Yüksek", cls: "badge-high" },
  medium: { label: "Orta",   cls: "badge-medium" },
  low:    { label: "Düşük",  cls: "badge-low" },
};

export default function RuleManager() {
  const [rules, setRules]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [form, setForm]         = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [message, setMessage]   = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editId, setEditId]     = useState(null);

  const showMessage = (text, type = "success") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getRules();
      const rulesData = res.data?.rules || res.data;
      setRules(Array.isArray(rulesData) ? rulesData : []);
    } catch (err) {
      console.error("Rule fetch error:", err);
      showMessage("Kurallar yüklenemedi: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const handleChange = (e) => setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setShowForm(false);
    setEditMode(false);
    setEditId(null);
  };

  const openEdit = (rule) => {
    setForm({
      id: rule.id,
      name: rule.name,
      category: rule.category,
      severity: rule.severity,
      check_command: rule.check_command,
      fix_command: rule.fix_command,
      description: rule.description,
    });
    setEditId(rule.id);
    setEditMode(true);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const required = ["id", "name", "category", "check_command", "fix_command", "description"];
    for (const f of required) {
      if (!form[f].trim()) { showMessage(`"${f}" alanı boş bırakılamaz.`, "error"); return; }
    }
    if (!/^[a-z0-9_]+$/.test(form.id)) {
      showMessage("ID yalnızca küçük harf, rakam ve alt çizgi içerebilir.", "error"); return;
    }
    setSubmitting(true);
    try {
      if (editMode && editId) {
        await updateRule(editId, form);
        showMessage(`"${form.name}" kuralı güncellendi.`);
      } else {
        await addRule(form);
        showMessage(`"${form.name}" kuralı eklendi.`);
      }
      resetForm();
      fetchRules();
    } catch (err) {
      showMessage((editMode ? "Güncelleme" : "Ekleme") + " başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (ruleId, ruleName) => {
    if (!window.confirm(`"${ruleName}" kuralını silmek istediğinizden emin misiniz?`)) return;
    setDeleting(ruleId);
    try {
      await deleteRule(ruleId);
      showMessage(`"${ruleName}" kuralı silindi.`);
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
    } catch (err) {
      showMessage("Silme başarısız: " + (err.response?.data?.detail || err.message), "error");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="rule-manager">
      <div className="page-header">
        <div>
          <h1 className="page-title">Kural Yönetimi</h1>
          <p className="page-subtitle">Sıkılaştırma kurallarını görüntüleyin, ekleyin veya silin.</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm((v) => !v); }}>
          {showForm ? <><X size={14} /> İptal</> : <><Plus size={14} /> Yeni Kural</>}
        </button>
      </div>

      {message && (
        <div className={`msg ${message.type === "error" ? "msg-error" : "msg-success"}`}>
          {message.text}
        </div>
      )}

      {showForm && (
        <div className="card rule-form-card">
          <p className="section-title">{editMode ? "Kuralı Düzenle" : "Yeni Kural Tanımla"}</p>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">ID <span className="required">*</span></label>
                <input name="id" value={form.id} onChange={handleChange}
                  placeholder="ornek_kural_id" className="form-input" disabled={editMode} />
                <span className="form-hint">{editMode ? "ID değiştirilemez." : "Küçük harf, rakam ve alt çizgi."}</span>
              </div>
              <div className="form-group">
                <label className="form-label">Kural Adı <span className="required">*</span></label>
                <input name="name" value={form.name} onChange={handleChange}
                  placeholder="SSH Root Login Kapalı Olmalı" className="form-input" />
              </div>
              <div className="form-group">
                <label className="form-label">Kategori <span className="required">*</span></label>
                <input name="category" value={form.category} onChange={handleChange}
                  placeholder="SSH, Ağ, Sistem..." className="form-input" />
              </div>
              <div className="form-group">
                <label className="form-label">Önem Derecesi</label>
                <select name="severity" value={form.severity} onChange={handleChange} className="form-input">
                  <option value="high">Yüksek</option>
                  <option value="medium">Orta</option>
                  <option value="low">Düşük</option>
                </select>
              </div>
              <div className="form-group full-width">
                <label className="form-label">Kontrol Komutu <span className="required">*</span></label>
                <textarea name="check_command" value={form.check_command} onChange={handleChange}
                  placeholder="grep -q 'PermitRootLogin no' /etc/ssh/sshd_config && echo 'OK' || echo 'FAIL'"
                  className="form-input" rows={3} />
                <span className="form-hint">Çıktıda "OK" varsa kural geçer, "FAIL" varsa uyarı verilir.</span>
              </div>
              <div className="form-group full-width">
                <label className="form-label">Düzeltme Komutu <span className="required">*</span></label>
                <textarea name="fix_command" value={form.fix_command} onChange={handleChange}
                  placeholder="sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
                  className="form-input" rows={3} />
              </div>
              <div className="form-group full-width">
                <label className="form-label">Açıklama <span className="required">*</span></label>
                <textarea name="description" value={form.description} onChange={handleChange}
                  placeholder="Bu kural ne kontrol eder ve neden önemlidir?"
                  className="form-input" rows={2} />
              </div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? "Kaydediliyor..." : editMode ? "Güncelle" : "Kaydet"}
              </button>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>
                İptal
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Yükleniyor...</p></div>
      ) : rules.length === 0 ? (
        <div className="empty-state"><p>Henüz kural eklenmemiş.</p></div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Kural Adı</th>
                <th>Kategori</th>
                <th>Önem</th>
                <th>Açıklama</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => {
                const sev = SEV_CONFIG[rule.severity] || { label: rule.severity, cls: "" };
                return (
                  <tr key={rule.id}>
                    <td>
                      <div className="rule-name">{rule.name}</div>
                      <code className="rule-id mono">{rule.id}</code>
                    </td>
                    <td>
                      <span className="category-tag">{rule.category}</span>
                    </td>
                    <td>
                      <span className={`badge ${sev.cls}`}>{sev.label}</span>
                    </td>
                    <td className="rule-desc">{rule.description}</td>
                    <td>
                      <div className="action-btns">
                        <button className="btn btn-ghost btn-sm"
                          onClick={() => openEdit(rule)}>
                          <Pencil size={12} />
                          Düzenle
                        </button>
                        <button className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(rule.id, rule.name)}
                          disabled={deleting === rule.id}>
                          <Trash2 size={12} />
                          {deleting === rule.id ? "Siliniyor..." : "Sil"}
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
    </div>
  );
}
