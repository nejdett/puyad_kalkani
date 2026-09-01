# Puyad Kalkanı

Linux sunucularının güvenlik durumunu CIS/NIST standartlarına göre değerlendiren, sorunları tespit eden ve düzeltme önerileri sunan web tabanlı bir güvenlik yönetim aracıdır.

Tamamen Türkçe arayüze sahiptir. Sunucu yönetimi, tarama, düzeltme, log izleme, honeypot, adli bilişim, ağ haritası, CVE zafiyet analizi ve Telegram bildirim gibi modülleri içerir.

---

> **Önemli:** Proje, HoneyPot, snapshot ve hardening komutları gibi işlemler için root yetkisi gerektirir. Tüm komutları root olarak çalıştırın.

---

## Özellikler

### v2.1.0 ile Gelen Özellikler

- **Çoklu Sunucu Yönetimi** — Tek panelden birden fazla Linux sunucusunu izleme ve yönetme. Controller/Stand-alone çalışma modları.
- **Gelişmiş Adli Bilişim** — HoneyPot/BruteForce alarm anlarında sistem durumunu dondurarak kanıt paketi oluşturma.
- **Görsel Ağ Haritası** — Aktif bağlantılar, açık portlar ve saldırı kaynaklarının coğrafi harita üzerinde görselleşmesi.
- **Telegram Bildirimleri** — Kritik tehdit anında Telegram'a anlık bildirim ve butonlar üzerinden uzaktan IP engelleme.
- **CVE Zafiyet Analizi** — Yerel veritabanı ve OSV.dev API ile çift katmanlı paket taraması, 0-100 güvenlik skoru.
- **HoneyPot Tuzakları** — FTP, SSH, Telnet, HTTP, SMTP gibi servisleri taklit eden tuzak portları.
- **Periyodik Tarama** — APScheduler ile otomatik zamanlanmış tarama görevleri.
- **Log İzleme** — Sistem loglarının canlı olarak izlenmesi.
- **Snapshot ve Geri Yükleme** — Sistem konfigürasyonunun yedeği ve tek tıkla geri yükleme.
- **PDF Rapor** — Tarama sonuçlarının PDF olarak dışa aktarılması.

### v2.1.0 Güvenlik Yaması

Bu sürümde aşağıdaki güvenlik düzeltmeleri uygulanmıştır:

- **Şifreleme:** SHA-256'dan bcrypt'e geçiş, salt ekleme, token karşılaştırmalarında constant-time karşılaştırma.
- **API Güvenliği:** CORS sadece localhost adreslerine kısıtlandı. Agent shared secret sabitlendi, her başlatıldığında üretilmiyor.
- **Komut Çalıştırma Güvenliği:** Whitelist tabanlı komut filtreleme. Tehlikeli kalıp ve shell builtins otomatik olarak reddediliyor.
- **Telegram Güvenliği:** Bot token ve chat ID değerleri kaynak koddan kaldırıldı. config.json üzerinden yönetiliyor.

---

## Gereksinimler

- Python 3.11 ve üstü
- Node.js 18 ve üstü
- Debian/Ubuntu tabanlı Linux işletim sistemi
- Root yetkisi

---

## Hızlı Kurulum

```bash
# 1. Projeyi klonlayın
git clone https://github.com/nejdett/puyad_kalkani.git
cd puyad_kalkani

# 2. Python sanal ortamı oluşturun ve bağımlılıkları kurun
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt

# 3. Konfigürasyon dosyasını oluşturun
cp config.json.example config.json

# 4. Backend'i başlatın
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Frontend için ayrı bir terminal açın:

```bash
cd frontend
npm install
npm start
```

Tarayıcıdan erişim:
- Panel: http://localhost:3000
- API: http://localhost:8000/docs

---

## Çalışma Modları

### Standalone

Sadece yerel sunucuyu yönetir. Varsayılan moddur.

### Controller

Birden fazla sunucuyu tek panelden yönetir. Uzak sunuculara bağlanarak tarama ve düzeltme işlemleri yapılır.

Mod değişikliği için config.json dosyasındaki RUN_MODE değeri değiştirilir:

```json
{
  "RUN_MODE": "controller",
  "AGENT_SHARED_SECRET": "guclu-bir-sifre"
}
```

---

## Proje Yapısı

```
puyad-kalkani/
├── backend/
│   ├── main.py                 FastAPI uygulaması ve endpoint'ler
│   ├── engine.py               Kural çalıştırma motoru
│   ├── remediation_engine.py   Düzeltme + snapshot + geçmiş yönetimi
│   ├── backup_manager.py       Snapshot oluşturma ve geri yükleme
│   ├── honeypot.py             Tuzak port dinleyicisi
│   ├── log_monitor.py          auth.log / journald SSE akışı
│   ├── scheduler.py            Periyodik tarama zamanlayıcısı
│   ├── pdf_reporter.py         PDF rapor üretici
│   ├── auth.py                 Token tabanlı kimlik doğrulama
│   ├── database.py             SQLite bağlantı ve yönetimi
│   ├── config.py               Konfigürasyon yönetimi
│   ├── agent_client.py         Uzak sunucu iletişim katmanı
│   ├── migrate.py              Veritabanı geçiş scripti
│   ├── forensic_manager.py     Adli kanıt toplama motoru
│   ├── network_mapper.py       Ağ haritası ve GeoIP
│   ├── telegram_manager.py     Telegram bildirim ve onay
│   ├── cve_analyzer.py         CVE zafiyet tarama motoru
│   ├── cve_database.json       Yerel CVE veritabanı
│   ├── rules.json              Güvenlik kuralları
│   └── requirements.txt        Python bağımlılıkları
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.js
│   │   ├── App.css
│   │   ├── api.js
│   │   └── components/
│   │       ├── Dashboard.js
│   │       ├── ServerManagement.js
│   │       ├── RuleManager.js
│   │       ├── SchedulerView.js
│   │       ├── VulnerabilityScanner.js
│   │       ├── HoneypotView.js
│   │       ├── LogMonitor.js
│   │       ├── ForensicEvidence.js
│   │       ├── NetworkMap.js
│   │       ├── SnapshotManager.js
│   │       ├── HistoryView.js
│   │       ├── TelegramSettings.js
│   │       └── LoginPage.js
│   └── package.json
├── config.json.example         Konfigürasyon şablonu
└── LICENSE                     Lisans dosyası
```

---

## Sorun Giderme

**Port 8000 meşgulse:**

```bash
lsof -i :8000
kill -9 <PID>
```

**Frontend bağlantı hatası:**

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"2.1.0"}
```

---

## Gelecek Sürüm Planları

- **Light Agent** — Uzak sunucular için hafif, bağımsız bir agent modeli.
- **Webhook Entegrasyonu** — Slack, Discord ve özel webhook adreslerine bildirim gönderme.
- **RBAC (Role-Based Access Control)** — Rol tabanlı erişim kontrolü, kullanıcı yetkilendirme sistemi.
- **Multi-tenant Desteği** — Aynı panel üzerinden farklı organizasyonların yönetilmesi.
- **Yeni Rapor Şablonları** — CVE, hardening ve adli bilişim için detaylı PDF/HTML rapor şablonları.

---

## Lisans

MIT Lisansı

---

## Geliştirici

Nejdet Yılmaz
