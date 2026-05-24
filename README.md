# Trading Bot — Bybit + Polymarket + AI Analysis

Bot trading crypto paper simulation dengan AI analysis, Polymarket sentiment, dan notifikasi Telegram otomatis.

---

## Fitur

### 📊 Dashboard
Halaman utama yang menampilkan overview akun secara real-time:
- **Account metrics** — balance paper, equity, free margin
- **PnL** — daily / weekly / monthly profit & loss
- **Performance stats** — total trades, win rate, profit factor
- **Risk monitor** — daily loss bar, drawdown progress, consecutive losses
- **Bot status** — running/stopped, auto trade on/off
- Auto-refresh tiap 30 detik

### 🤖 AI Analysis Scanner
Scanner otomatis coin dari watchlist menggunakan dua sumber data:
- **Bybit** — harga real-time, candle, volume, 24h change
- **Polymarket** — sentimen pasar dari prediction market (yes/no price bias)

Dua mode analisis:
- **Heuristic** — kalkulasi momentum + sentiment score tanpa AI (cepat, selalu jalan)
- **Deep Analysis** — AI (DeepSeek Cloud API atau Ollama lokal) analisis dan beri rekomendasi BUY/SELL/HOLD + entry/SL/TP

Auto-scan tiap 5 menit via Celery Beat. Frontend refresh hasil dari DB tiap 60 detik tanpa hit Bybit ulang.

Browser notification otomatis saat sinyal BUY/SELL berubah.

### 📈 Active Trades
Monitor semua paper trade yang sedang terbuka:
- Symbol, direction (LONG/SHORT), entry price
- Stop Loss dan Take Profit
- Unrealized PnL real-time
- Tombol close manual

### 📋 Trade History
Riwayat semua trade yang sudah tertutup:
- PnL aktual per trade
- Alasan penutupan (SL hit / TP hit / manual)
- Filter dan pagination

### ⚙️ Bot Settings
Konfigurasi lengkap bot:
- **Market Config** — symbol, leverage
- **Scanner Config** — watchlist coins, paper balance
- **Bot Options** — auto trade, AI enabled, scan interval
- **Polymarket API** — credentials opsional
- **Telegram Test** — tombol test notifikasi langsung

### 🛡️ Risk Settings
Konfigurasi batas risiko:
- Daily loss limit percent
- Max drawdown percent
- Consecutive loss limit
- Max open trades

### 🔔 Telegram Notifications
Notifikasi otomatis ke Telegram saat:
- Scan menemukan sinyal BUY/SELL baru
- Paper trade terbuka (entry, SL, TP)
- Trade tertutup karena SL atau TP hit (dengan PnL hasil)

---

## Stack Teknologi

| Layer | Teknologi |
|---|---|
| Backend | FastAPI (Python 3.12) + SQLAlchemy async |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7 + Celery |
| Frontend | React 18 + Vite + TailwindCSS |
| AI | DeepSeek Cloud API atau Ollama (lokal) |
| Market Data | Bybit public API (no auth required) |
| Sentiment | Polymarket Gamma API (public) |
| Notifications | Telegram Bot API |
| Proxy | Nginx |
| Container | Docker Compose |

---

## Cara Install

### Kebutuhan
- Docker Desktop (Windows/Mac) atau Docker Engine + Docker Compose (Linux)
- Git

### 1. Clone repository

```bash
git clone https://github.com/username/trading-bot.git
cd trading-bot
```

### 2. Buat file `.env`

Copy dari template:
```bash
cp .env.example .env
```

Edit `.env` dan isi nilai yang diperlukan:

```env
# WAJIB — generate random string panjang
SECRET_KEY="ganti-dengan-random-string-panjang"
JWT_SECRET_KEY="ganti-dengan-random-string-jwt"
DB_PASSWORD="password-database-kamu"

# AI — pilih salah satu:
# Option A: DeepSeek Cloud (rekomen, lebih cepat)
DEEPSEEK_API_KEY="sk-xxxx"

# Option B: Ollama lokal (gratis, butuh GPU/CPU kuat)
# Kosongkan DEEPSEEK_API_KEY, aktifkan profile ollama

# Bybit — public data tidak perlu API key
BYBIT_API_KEY=""
BYBIT_API_SECRET=""

# Telegram (opsional)
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""

# Security
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]
```

Generate SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3. Jalankan dengan Docker Compose

**Dengan DeepSeek API (rekomendasi):**
```bash
docker compose up -d
```

**Dengan Ollama lokal (GPU):**
```bash
docker compose --profile ollama up -d
docker exec tradingbot_ollama ollama pull deepseek-r1:7b
```

### 4. Jalankan migrasi database

```bash
docker exec tradingbot_backend alembic upgrade head
```

### 5. Akses aplikasi

| Service | URL |
|---|---|
| Frontend (via Nginx) | http://localhost |
| Backend API | http://localhost:8000 |
| Frontend direct | http://localhost:3000 |

### 6. Buat akun pertama

Buka http://localhost → klik **Register** → isi username, email, password.

Setelah login, buka **Bot Settings** → konfigurasi watchlist dan paper balance → klik **Save**.

---

## Setup Telegram (Opsional)

1. Buka Telegram → cari `@BotFather`
2. Kirim `/newbot` → ikuti instruksi → dapat **BOT_TOKEN**
3. Cari `@userinfobot` → kirim `/start` → dapat **CHAT_ID**
4. Isi `.env`:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:AAExxx...
   TELEGRAM_CHAT_ID=123456789
   ```
5. Restart backend: `docker compose restart backend celery_worker celery_beat`
6. Buka **Bot Settings** → klik **📨 Test Kirim Notifikasi**

---

## Struktur Proyek

```
trading-bot/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models
│   │   ├── routers/         # FastAPI endpoints
│   │   ├── services/        # Business logic
│   │   │   ├── ai_service.py        # DeepSeek/Ollama integration
│   │   │   ├── exchange_service.py  # Bybit + Polymarket data
│   │   │   ├── scanner_service.py   # Market scanner
│   │   │   ├── trading_service.py   # Trade management
│   │   │   ├── risk_service.py      # Risk monitoring
│   │   │   └── telegram_service.py  # Telegram notifications
│   │   ├── workers/
│   │   │   ├── celery_app.py        # Celery + Beat schedule
│   │   │   └── tasks.py             # Background tasks
│   │   └── main.py
│   └── alembic/             # Database migrations
├── frontend/
│   └── src/
│       ├── pages/           # Dashboard, AIAnalysis, Trades, dll
│       ├── services/api.js  # Axios API client
│       └── hooks/           # WebSocket hook
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .env.example             # Template konfigurasi
└── .gitignore
```

---

## Celery Tasks (Background Jobs)

| Task | Interval | Fungsi |
|---|---|---|
| `scan_market_opportunities` | 5 menit | Scan watchlist, AI analysis, kirim Telegram |
| `check_stop_loss_take_profit` | 30 detik | Auto close trade jika SL/TP kena |
| `check_risk_limits` | 60 detik | Monitor dan log risk events |

---

## Perintah Berguna

```bash
# Lihat logs
docker logs tradingbot_backend --tail 50
docker logs tradingbot_celery_worker --tail 30

# Restart services
docker compose restart backend
docker compose up -d --build backend celery_worker celery_beat

# Akses database
docker exec -it tradingbot_postgres psql -U tradingbot -d tradingbot_db

# Jalankan migrasi
docker exec tradingbot_backend alembic upgrade head

# Test Telegram manual
docker exec tradingbot_backend python3 -c "
import asyncio
from app.services.telegram_service import TelegramService
asyncio.run(TelegramService().send_message('test'))
"
```

---

## Catatan Penting

- **Paper trading only** — tidak ada eksekusi order nyata ke exchange
- Bot menggunakan data harga **real Bybit** untuk simulasi yang realistis
- Bybit public API tidak perlu API key (hanya baca data pasar)
- DeepSeek API key perlu daftar di [platform.deepseek.com](https://platform.deepseek.com)
- Jangan commit file `.env` ke repository — semua secrets harus di `.env` lokal saja

---

## Troubleshooting

**Dashboard error 500:**
Pastikan migrasi sudah dijalankan: `docker exec tradingbot_backend alembic upgrade head`

**Scanner gagal "No market data":**
Backend tidak bisa koneksi ke Bybit. Cek: `docker exec tradingbot_backend python3 -c "import urllib.request; print(urllib.request.urlopen('https://api.bybit.com').status)"`

**Telegram tidak terkirim:**
Cek `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` sudah benar di `.env`, lalu restart container.

**Port sudah dipakai:**
Edit `docker-compose.yml` bagian `ports` untuk ganti port.
