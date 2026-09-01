import React, { useState } from "react";
import { api } from "../api";
import { Shield, User, Lock, LogIn } from "lucide-react";
import "./LoginPage.css";

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError("Kullanıcı adı ve şifre zorunludur.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/login", { username, password });
      localStorage.setItem("puyad_token", res.data.access_token);
      localStorage.setItem("puyad_user", res.data.username);
      onLogin(res.data.username);
    } catch (err) {
      setError(err.response?.data?.detail || "Kimlik doğrulama başarısız.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-logo">
            <Shield size={22} />
          </div>
          <h1 className="login-title">Puyad Kalkanı</h1>
          <p className="login-subtitle">Linux Hardening Platform</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && (
            <div className="login-error">
              <span>{error}</span>
            </div>
          )}

          <div className="login-field">
            <label className="form-label">Kullanıcı Adı</label>
            <div className="input-wrap">
              <User size={15} className="input-icon" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoFocus
                autoComplete="username"
              />
            </div>
          </div>

          <div className="login-field">
            <label className="form-label">Şifre</label>
            <div className="input-wrap">
              <Lock size={15} className="input-icon" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
          </div>

          <button type="submit" className="login-btn" disabled={loading}>
            <LogIn size={15} />
            {loading ? "Doğrulanıyor..." : "Giriş Yap"}
          </button>
        </form>

        <p className="login-hint">
          Varsayılan: <code>admin</code> / <code>puyad2026</code>
        </p>
      </div>
    </div>
  );
}
