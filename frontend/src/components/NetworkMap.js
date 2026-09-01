import React, { useState, useEffect, useCallback } from "react";
import { Map, Globe, RefreshCw, Server, Wifi, AlertTriangle, ShieldCheck } from "lucide-react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import { api } from "../api";
import "leaflet/dist/leaflet.css";
import "./NetworkMap.css";

function TopologyGraph({ topology }) {
  if (!topology || !topology.nodes) return <div className="empty-state"><p>Veri bulunamadı.</p></div>;

  const { nodes, edges } = topology;
  const centerX = 400;
  const centerY = 250;
  const portRadius = 120;

  // port düğümlerini daire etrafına yerleştir
  const portNodes = nodes.filter((n) => n.type === "port");
  const clientNodes = nodes.filter((n) => n.type === "client");

  const portPositions = {};
  portNodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(portNodes.length, 1) - Math.PI / 2;
    portPositions[n.id] = {
      x: centerX + portRadius * Math.cos(angle),
      y: centerY + portRadius * Math.sin(angle),
    };
  });

  // client'ları port etrafında dağıt
  const clientPositions = {};
  clientNodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(clientNodes.length, 1) - Math.PI / 2;
    const r = portRadius + 100;
    clientPositions[n.id] = {
      x: centerX + r * Math.cos(angle),
      y: centerY + r * Math.sin(angle),
    };
  });

  const allPositions = { ...portPositions, ...clientPositions };
  allPositions["server"] = { x: centerX, y: centerY };

  return (
    <div className="topology-container">
      <svg viewBox="0 0 800 500" className="topology-svg">
        {/* çizgiler */}
        {edges.map((e, i) => {
          const from = allPositions[e.from];
          const to = allPositions[e.to];
          if (!from || !to) return null;
          return (
            <line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke="var(--border)" strokeWidth="1.5" strokeDasharray="4,3" opacity="0.6" />
          );
        })}

        {/* sunucu düğümü */}
        <circle cx={centerX} cy={centerY} r="28" fill="var(--accent)" opacity="0.2" />
        <circle cx={centerX} cy={centerY} r="18" fill="var(--accent)" />
        <text x={centerX} y={centerY + 4} textAnchor="middle" fill="#fff" fontSize="10" fontWeight="600">
          SRV
        </text>

        {/* port düğümleri */}
        {portNodes.map((n) => {
          const pos = portPositions[n.id];
          if (!pos) return null;
          return (
            <g key={n.id}>
              <circle cx={pos.x} cy={pos.y} r="14" fill="var(--bg-elevated)" stroke="var(--accent)" strokeWidth="1.5" />
              <text x={pos.x} y={pos.y + 4} textAnchor="middle" fill="var(--accent)" fontSize="9" fontWeight="500">
                {n.label}
              </text>
            </g>
          );
        })}

        {/* client düğümleri */}
        {clientNodes.map((n) => {
          const pos = clientPositions[n.id];
          if (!pos) return null;
          return (
            <g key={n.id}>
              <circle cx={pos.x} cy={pos.y} r="12" fill="var(--bg-card)" stroke="var(--border)" strokeWidth="1.5" />
              <text x={pos.x} y={pos.y + 3} textAnchor="middle" fill="var(--text-muted)" fontSize="7">
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function AttackMap({ attacks, onMarkerClick }) {
  return (
    <div className="attack-map-wrapper">
      <MapContainer center={[20, 0]} zoom={2} className="attack-map"
        zoomControl={true} attributionControl={false}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" className="dark-tiles" />
        {attacks.map((a, i) => (
          <CircleMarker key={i} center={[a.lat, a.lon]} radius={8}
            pathOptions={{ color: a.type === "HoneyPot" ? "#ef4444" : "#f59e0b",
              fillColor: a.type === "HoneyPot" ? "#ef4444" : "#f59e0b",
              fillOpacity: 0.6, weight: 2 }}
            eventHandlers={{ click: () => onMarkerClick(a) }}>
            <Popup>
              <div className="map-popup">
                <strong>{a.ip}</strong><br />
                {a.country} / {a.city}<br />
                Tür: {a.type}
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}

export default function NetworkMap() {
  const [topology, setTopology] = useState(null);
  const [attacks, setAttacks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("topology");
  const [selectedAttack, setSelectedAttack] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [topRes, atkRes] = await Promise.all([
        api.get("/network/topology"),
        api.get("/network/attacks"),
      ]);
      setTopology(topRes.data);
      setAttacks(atkRes.data.attacks);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <div className="network-map-page">
      <div className="nm-header">
        <div>
          <h1 className="page-title">Ağ Haritası</h1>
          <p className="page-subtitle">Aktif bağlantılar ve saldırı kaynakları.</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-ghost" onClick={loadData}>
            <RefreshCw size={14} />
            Yenile
          </button>
        </div>
      </div>

      <div className="nm-tabs">
        <button className={`nm-tab ${activeTab === "topology" ? "active" : ""}`}
          onClick={() => setActiveTab("topology")}>
          <Server size={14} />
          Ağ Topolojisi
        </button>
        <button className={`nm-tab ${activeTab === "geoip" ? "active" : ""}`}
          onClick={() => setActiveTab("geoip")}>
          <Globe size={14} />
          Tehdit Haritası
          {attacks.length > 0 && <span className="nm-badge">{attacks.length}</span>}
        </button>
      </div>

      <div className="nm-content">
        {activeTab === "topology" && (
          loading ? (
            <div className="loading-state"><div className="spinner" /><p>Yükleniyor...</p></div>
          ) : (
            <TopologyGraph topology={topology} />
          )
        )}
        {activeTab === "geoip" && (
          loading ? (
            <div className="loading-state"><div className="spinner" /><p>Yükleniyor...</p></div>
          ) : (
            <div className="geoip-section">
              <AttackMap attacks={attacks} onMarkerClick={setSelectedAttack} />
              {selectedAttack && (
                <div className="attack-detail-panel">
                  <div className="adp-header">
                    <h3>Saldırı Detayı</h3>
                    <button className="btn btn-ghost btn-sm" onClick={() => setSelectedAttack(null)}>Kapat</button>
                  </div>
                  <div className="adp-body">
                    <div className="adp-row"><span>IP</span><code>{selectedAttack.ip}</code></div>
                    <div className="adp-row"><span>Ülke</span><span>{selectedAttack.country_code} {selectedAttack.country}</span></div>
                    <div className="adp-row"><span>Şehir</span><span>{selectedAttack.city}</span></div>
                    <div className="adp-row"><span>Tür</span>
                      <span className={`badge ${selectedAttack.type === "HoneyPot" ? "badge-high" : "badge-medium"}`}>
                        {selectedAttack.type}
                      </span>
                    </div>
                    {selectedAttack.port && <div className="adp-row"><span>Port</span><code>{selectedAttack.port}</code></div>}
                    {selectedAttack.date && <div className="adp-row"><span>Tarih</span><span className="mono">{selectedAttack.date}</span></div>}
                  </div>
                </div>
              )}
            </div>
          )
        )}
      </div>
    </div>
  );
}
