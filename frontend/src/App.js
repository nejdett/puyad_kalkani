import React, { useState, useEffect } from "react";
import {
  LayoutDashboard, Camera, History, Clock, ShieldAlert,
  ScrollText, Settings, LogOut, Shield, Server, FileSearch,
  Globe, Bell, Bug, ChevronLeft, ChevronRight
} from "lucide-react";
import Dashboard from "./components/Dashboard";
import RuleManager from "./components/RuleManager";
import SnapshotManager from "./components/SnapshotManager";
import LogMonitor from "./components/LogMonitor";
import HistoryView from "./components/HistoryView";
import SchedulerView from "./components/SchedulerView";
import HoneypotView from "./components/HoneypotView";
import LoginPage from "./components/LoginPage";
import ServerManagement from "./components/ServerManagement";
import ForensicEvidence from "./components/ForensicEvidence";
import NetworkMap from "./components/NetworkMap";
import TelegramSettings from "./components/TelegramSettings";
import VulnerabilityScanner from "./components/VulnerabilityScanner";
import { api } from "./api";
import "./App.css";

const SIDEBAR_GROUPS = [
  {
    label: "GENEL",
    items: [
      { id: "dashboard", label: "Kontrol Paneli", icon: LayoutDashboard, component: Dashboard },
      { id: "servers", label: "Sunucu Yönetimi", icon: Server, component: ServerManagement },
    ],
  },
  {
    label: "GUVENLIK & TARAMA",
    items: [
      { id: "rules", label: "Kural Yönetimi", icon: Settings, component: RuleManager },
      { id: "scheduler", label: "Oto Tarama", icon: Clock, component: SchedulerView },
      { id: "vuln", label: "Zafiyet Analizi", icon: Bug, component: VulnerabilityScanner },
      { id: "honeypot", label: "HoneyPot", icon: ShieldAlert, component: HoneypotView },
    ],
  },
  {
    label: "ANALIZ & ADLI BILISIM",
    items: [
      { id: "logs", label: "Canlı Log", icon: ScrollText, component: LogMonitor },
      { id: "forensic", label: "Adli Bilişim", icon: FileSearch, component: ForensicEvidence },
      { id: "network", label: "Ağ Haritası", icon: Globe, component: NetworkMap },
    ],
  },
  {
    label: "IZLEME & SISTEM",
    items: [
      { id: "snapshots", label: "Snapshot", icon: Camera, component: SnapshotManager },
      { id: "history", label: "Geçmiş", icon: History, component: HistoryView },
      { id: "telegram", label: "Telegram Ayarları", icon: Bell, component: TelegramSettings },
    ],
  },
];

const ALL_PAGES = SIDEBAR_GROUPS.flatMap((g) => g.items);

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [user, setUser] = useState(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [runMode, setRunMode] = useState("standalone");

  useEffect(() => {
    const token = localStorage.getItem("puyad_token");
    const savedUser = localStorage.getItem("puyad_user");
    if (token && savedUser) setUser(savedUser);
  }, []);

  useEffect(() => {
    if (!user) return;
    api.get("/config").then((res) => {
      setRunMode(res.data?.RUN_MODE || "standalone");
    }).catch(() => {});
    const interval = setInterval(async () => {
      try {
        const [pend, cfg] = await Promise.all([
          api.get("/telegram/pending"),
          api.get("/config"),
        ]);
        setPendingCount((pend.data?.pending || []).length);
        setRunMode(cfg.data?.RUN_MODE || "standalone");
      } catch (e) {}
    }, 15000);
    return () => clearInterval(interval);
  }, [user]);

  const handleLogin = (username) => setUser(username);

  const handleLogout = () => {
    localStorage.removeItem("puyad_token");
    localStorage.removeItem("puyad_user");
    setUser(null);
  };

  if (!user) return <LoginPage onLogin={handleLogin} />;

  const ActiveComponent = ALL_PAGES.find((p) => p.id === activePage)?.component || Dashboard;

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="sidebar-brand">
          <div className="sidebar-logo">
            <Shield size={16} />
          </div>
          {!sidebarCollapsed && (
            <div className="sidebar-brand-text">
              <span className="sidebar-title">Puyad Kalkanı</span>
              <span className="sidebar-version">v2.1.0</span>
            </div>
          )}
        </div>

        <nav className="sidebar-nav">
          {SIDEBAR_GROUPS.map((group) => (
            <div key={group.label} className="sidebar-group">
              {!sidebarCollapsed && (
                <div className="sidebar-group-label">{group.label}</div>
              )}
              {group.items.map((page) => {
                const Icon = page.icon;
                return (
                  <button
                    key={page.id}
                    className={`sidebar-item ${activePage === page.id ? "active" : ""}`}
                    onClick={() => setActivePage(page.id)}
                    title={sidebarCollapsed ? page.label : undefined}
                    style={page.id === "telegram" ? { position: "relative" } : undefined}
                  >
                    <Icon size={16} />
                    {!sidebarCollapsed && <span>{page.label}</span>}
                    {page.id === "telegram" && pendingCount > 0 && (
                      <span className="sidebar-badge">{pendingCount}</span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="sidebar-item logout-item" onClick={handleLogout} title={sidebarCollapsed ? "Oturumu Kapat" : undefined}>
            <LogOut size={16} />
            {!sidebarCollapsed && <span>{user} &middot; Çıkış</span>}
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="sidebar-toggle"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            >
              {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
            <h1 className="topbar-title">
              {ALL_PAGES.find((p) => p.id === activePage)?.label || "Dashboard"}
            </h1>
          </div>
          <div className="topbar-right">
            <div className={`topbar-badge ${runMode === "controller" ? "controller-badge" : "standalone-badge"}`}>
              <Shield size={12} />
              <span>{runMode === "controller" ? "Controller" : "Standalone"}</span>
            </div>
            {pendingCount > 0 && (
              <div className="topbar-badge alert-badge">
                <Bell size={12} />
                <span>{pendingCount}</span>
              </div>
            )}
          </div>
        </header>

        <main className="main-content">
          <ActiveComponent />
        </main>

        <footer className="app-footer">
          <span>Puyad Kalkanı v2.1.0</span>
          <span>Nejdet Yılmaz tarafından geliştirilmiştir.</span>
        </footer>
      </div>
    </div>
  );
}
