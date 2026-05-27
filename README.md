# Trading Bot — Bybit + DeFi + AI Analysis

Bot trading crypto otomatis dengan AI analysis, DeFi spot trading (Uniswap V3 multi-network), Bybit perpetual (long/short), Polymarket sentiment, auto-tuning risk, dan notifikasi Telegram lengkap.

---

## Fitur

### Dashboard
Halaman utama overview akun real-time:
- **Account metrics** — balance paper, equity, free margin
- **PnL** — daily / weekly / monthly profit & loss
- **Performance stats** — total trades, win rate, profit factor
- **Risk monitor** — daily loss bar, drawdown progress, consecutive losses
- **Bot status** — running/stopped, auto trade on/off
- Auto-refresh tiap 30 detik

### AI Analysis Scanner
Scanner otomatis coin menggunakan dua sumber data:
- **Bybit** — harga real-time, candle, volume, 24h change
- **Polymarket** — sentimen pasar dari prediction market

**Dua mode scan:**

| Mode | Cara kerja |
|---|---|
| **Watchlist** | Scan coin yang kamu pilih saja |
| **All Coins** | Satu API call ambil SEMUA USDT perpetual Bybit, filter by volume, sort by \|%change 24h\|, scan top N coin |

**Dua mode analisis per coin:**
- **Heuristic** — momentum + sentiment score, tanpa AI, selalu jalan, simpan ke DB
- **Deep Analysis** — AI (DeepSeek Cloud / Ollama lokal) analisis, beri rekomendasi BUY/SELL/HOLD + Entry/SL/TP

Auto-scan tiap 5 menit via Celery Beat. Frontend baca hasil dari DB, tidak hit Bybit ulang.

### DeFi Trading (Uniswap V3)
Trading spot otomatis di blockchain via Uniswap V3:
- **Buy** = swap USDC → token ketika ada BUY signal
- **Sell** = swap token → USDC ketika ada SELL signal
- Token discovery otomatis via DexScreener (tidak harus ada di static registry)
- Eksekusi SELL dulu (exit posisi) sebelum BUY baru

**Multi-network support:**

| Network | Gas token | Est. biaya/swap |
|---|---|---|
| Arbitrum | ETH | $0.01–$0.10 |
| Optimism | ETH | $0.01–$0.05 |
| Base | ETH | $0.01–$0.05 |
| Polygon | MATIC | $0.001–$0.01 |

Set `defi_networks = ["arbitrum", "base"]` untuk trade di beberapa network sekaligus. Tiap network butuh native token (ETH/MATIC) untuk gas dan USDC terpisah.

**Catatan:** DeFi hanya spot (beli/jual token fisik). Tidak ada leverage, tidak ada short.

### Bybit Real Trading (Perpetual)
Trading kontrak perpetual di Bybit dengan leverage:
- **Long** = beli kontrak naik
- **Short** = jual kontrak turun
- SL/TP di-set langsung di exchange saat open order
- Support semua coin perpetual Bybit (DOGE, AAVE, BTC, dll)

Aktifkan dengan `real_trade_enabled = True` + isi API key Bybit di settings.

### Active Trades
Monitor paper/real trade terbuka:
- Symbol, direction (LONG/SHORT), entry price
- Stop Loss dan Take Profit
- Unrealized PnL real-time
- Tombol close manual

### Trade History
Riwayat trade tertutup:
- PnL aktual per trade
- Alasan penutupan (SL hit / TP hit / signal exit / manual)
- Filter dan pagination

### Bot Settings
Konfigurasi lengkap:
- **Market Config** — symbol, leverage
- **Scanner Config** — mode all-coins atau watchlist, max coins, min volume filter, paper balance
- **Bot Options** — auto trade, AI enabled, scan interval
- **DeFi Config** — wallet address, private key (encrypted), network(s), slippage, trade percent
- **Bybit API** — api key, api secret untuk real trading
- **Telegram Test** — tombol test notifikasi langsung

### Risk Settings
Konfigurasi batas risiko + auto-tuning:
- Risk per trade (%)
- Daily loss limit, max drawdown, consecutive loss limit
- Max open trades

**Auto-Tuning Risk:**
- Analisis performa 30 hari terakhir (win rate, profit factor, consecutive losses)
- Otomatis sesuaikan `risk_percent` sesuai performa
- Frekuensi: daily / weekly / monthly
- Mode approval manual: kirim rekomendasi ke Telegram dengan tombol Approve / Reject
- History semua tuning tersimpan di dashboard

### Telegram Notifications
Notifikasi otomatis:
- Sinyal BUY/SELL baru dari scanner (detail lengkap per coin: Entry, SL, TP, Sentiment, Volume)
- DeFi skip BUY karena sudah in position → tombol inline **💰 Take Profit (Sell Now)**
- SL moved to breakeven pada Bybit position → tombol inline **💰 Take Profit Now**
- DeFi BUY skipped karena token tidak tersedia di network — saran gunakan Bybit
- Trade tertutup (SL/TP hit, signal exit) dengan PnL
- Rekomendasi auto-tuning dengan tombol inline Approve / Reject
- Scan selesai tanpa data → notif "no market data returned"

### Telegram Bot Commands
Kontrol bot langsung dari Telegram:

| Command | Fungsi |
|---|---|
| `/status` | Overview bot: running/paused, mode scan, risk settings, balance |
| `/risk` | Status risiko: daily loss, drawdown, consecutive losses |
| `/report` | Statistik trade: win rate, total PnL, open positions |
| `/pause` | Hentikan bot (disable trading) |
| `/resume` | Nyalakan kembali bot |
| `/enable_autotrade` | Toggle auto-trade on/off |
| `/close_all` | Tutup semua paper trade terbuka |
| `/watch ETHUSDT ARBUSDT` | Tambah ke watchlist + scan langsung |
| `/unwatch ETHUSDT` | Hapus dari watchlist |
| `/watchlist` | Lihat watchlist aktif |
| `/scan` | Trigger manual scan |
| `/buy ARBUSDT` | Force-buy token dengan USDC via DeFi |
| `/sell ARBUSDT` | Force-sell semua token → USDC via DeFi (take profit manual) |
| `/help` | Daftar semua command |

> Command hanya diproses dari `TELEGRAM_CHAT_ID` yang terdaftar — unauthorized chat diabaikan.

---

## Stack Teknologi

| Layer | Teknologi |
|---|---|
| Backend | FastAPI (Python 3.12) + SQLAlchemy async |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7 + Celery |
| Frontend | React 18 + Vite + TailwindCSS + lucide-react |
| AI | DeepSeek Cloud API atau Ollama (lokal) |
| Market Data | Bybit public API (no auth required) |
| Sentiment | Polymarket Gamma API (public) |
| DeFi | Web3.py + Uniswap V3 (Arbitrum/Optimism/Base/Polygon) |
| CEX Trading | Bybit V5 API (perpetual long/short) |
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

```bash
cp .env.example .env
```

Edit `.env`:

```env
# WAJIB — generate random string panjang
SECRET_KEY="ganti-dengan-random-string-panjang"
JWT_SECRET_KEY="ganti-dengan-random-string-jwt"
DB_PASSWORD="password-database-kamu"

# AI — pilih salah satu:
# Option A: DeepSeek Cloud (rekomen)
DEEPSEEK_API_KEY="sk-xxxx"

# Option B: Ollama lokal (gratis, butuh GPU/CPU kuat)
# Kosongkan DEEPSEEK_API_KEY, aktifkan profile ollama di docker compose

# Bybit — untuk real trading (opsional, public data tidak perlu)
BYBIT_API_KEY=""
BYBIT_API_SECRET=""

# Telegram (opsional tapi direkomendasikan)
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

### 6. Buat akun

Buka http://localhost → klik **Register** → isi username, email, password.

Setelah login, buka **Bot Settings** → konfigurasi scanner dan paper balance → klik **Save**.

---

## Setup Telegram

1. Buka Telegram → cari `@BotFather`
2. Kirim `/newbot` → ikuti instruksi → dapat **BOT_TOKEN**
3. Cari `@userinfobot` → kirim `/start` → dapat **CHAT_ID**
4. Isi `.env`:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:AAExxx...
   TELEGRAM_CHAT_ID=123456789
   ```
5. Restart backend:
   ```bash
   docker compose restart backend celery_worker celery_beat
   ```
6. Buka **Bot Settings** → klik **Test Kirim Notifikasi**
7. Kirim `/help` ke bot untuk cek semua command aktif

---

## Setup DeFi Trading

1. Siapkan wallet EVM (MetaMask atau wallet baru khusus bot)
2. Isi wallet dengan:
   - **USDC** untuk trading
   - **ETH** (Arbitrum/Optimism/Base) atau **MATIC** (Polygon) untuk gas fee
3. Di **Bot Settings**, isi:
   - `defi_wallet_address` — alamat public wallet
   - `defi_wallet_private_key` — private key (disimpan encrypted di DB)
   - `defi_network` — network utama (`arbitrum` / `optimism` / `base` / `polygon`)
   - `defi_networks` — list semua network (opsional, untuk multi-network)
   - `defi_trade_percent` — % USDC yang dipakai per trade (default 50%)
   - `defi_slippage` — slippage tolerance dalam % (default 0.5)
4. Aktifkan `defi_enabled = true`
5. Aktifkan `auto_trade = true` untuk eksekusi otomatis

> **Peringatan:** Private key disimpan encrypted. Gunakan wallet terpisah khusus bot — jangan gunakan wallet utama.

---

## Setup Bybit Real Trading

1. Login Bybit → buka API Management
2. Buat API key baru:
   - Permission: **Derivatives Trading** (bukan withdrawal)
   - IP whitelist: opsional tapi direkomendasikan
3. Di **Bot Settings**, isi `polymarket_api_key` dan `polymarket_api_secret` dengan Bybit API key kamu
4. Aktifkan `real_trade_enabled = true`
5. Set `leverage` sesuai risk tolerance (default 10x, rekomen 3–5x untuk modal kecil)

---

## Struktur Proyek

```
trading-bot/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   ├── trade.py
│   │   │   ├── settings.py          # virtual props di JSON column
│   │   │   ├── tuning.py            # TuningHistory model
│   │   │   └── ...
│   │   ├── routers/
│   │   │   ├── tuning.py            # GET/POST tuning endpoints
│   │   │   ├── defi.py              # DeFi wallet + balance endpoints
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── ai_service.py               # DeepSeek/Ollama + heuristic
│   │   │   ├── exchange_service.py         # Bybit + Polymarket data
│   │   │   ├── scanner_service.py          # Market scanner + DeFi/Bybit execution
│   │   │   ├── trading_service.py          # Paper trade management
│   │   │   ├── risk_service.py             # Risk monitoring
│   │   │   ├── tuning_service.py           # Auto-tuning risk logic
│   │   │   ├── defi_service.py             # Uniswap V3 swap + multi-network
│   │   │   ├── bybit_order_service.py      # Bybit V5 order placement + position mgmt
│   │   │   ├── telegram_service.py         # Telegram send/edit/keyboard
│   │   │   └── telegram_callback_service.py # getUpdates polling + commands + TP buttons
│   │   ├── workers/
│   │   │   ├── celery_app.py               # Celery + Beat schedule
│   │   │   └── tasks.py                    # Background tasks
│   │   └── main.py
│   ├── alembic/                     # Database migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.jsx
│       │   ├── AIAnalysis.jsx
│       │   ├── BotSettings.jsx
│       │   ├── RiskSettings.jsx
│       │   └── ...
│       ├── services/api.js
│       └── components/
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## Celery Tasks (Background Jobs)

| Task | Interval | Fungsi |
|---|---|---|
| `scan_market_opportunities` | 5 menit | Scan coin, AI analysis, eksekusi DeFi/Bybit, kirim Telegram |
| `check_stop_loss_take_profit` | 30 detik | Auto close paper trade jika SL/TP kena |
| `check_risk_limits` | 60 detik | Monitor dan log risk events |
| `run_auto_tuning` | Daily 02:00 UTC | Analisis performa, sesuaikan risk_percent |
| `process_telegram_callbacks` | 30 detik | Poll getUpdates: command handler + inline button callbacks |
| `monitor_defi_positions` | 60 detik | Cek token held di semua DeFi networks, auto-exit jika SELL signal |
| `monitor_bybit_positions` | 60 detik | Sync Bybit position → DB, signal-exit, geser SL ke breakeven |

---

## Auto-Tuning Risk Logic

Aturan penyesuaian `risk_percent` (butuh minimal 5 closed trades dalam 30 hari):

| Kondisi | Aksi |
|---|---|
| Win rate < 35% | Kurangi 0.2% |
| Consecutive losses ≥ limit | Kurangi 0.15% |
| Win rate ≥ 60% + PF ≥ 1.5 + trades ≥ 10 | Tambah 0.1% |
| Kondisi netral | Tidak ada perubahan |

Batas: minimum **0.1%**, maksimum **5.0%**.

Jika `require_manual_approval_for_tuning` aktif → kirim ke Telegram dengan tombol **✅ Approve** / **❌ Reject**.
Jika tidak → langsung terapkan (`auto_applied`).

---

## Proteksi Risiko Otomatis

### DeFi (Uniswap)
- Bot pantau token held tiap 60 detik via `monitor_defi_positions`
- Signal SELL muncul → langsung swap token → USDC
- Skip SELL ketika tidak hold token (tidak ada notif spam)
- Skip BUY ketika token tidak tersedia di DeFi → notif ke Telegram + saran Bybit

### Bybit Perpetual
- SL/TP di-set di exchange saat open order (Bybit handle secara native)
- Bot sync posisi tiap 60 detik: jika Bybit sudah close → update DB otomatis
- Signal flip kuat → close position via market order
- Profit ≥ 1.5% → geser SL ke breakeven (tidak bisa rugi dari sana)
- Telegram notif dengan tombol **💰 Take Profit Now** untuk close manual

---

## Perintah Berguna

```bash
# Lihat logs
docker logs tradingbot_backend --tail 50
docker logs tradingbot_celery_worker --tail 30
docker logs tradingbot_celery_beat --tail 30

# Restart services
docker compose restart backend celery_worker celery_beat

# Build ulang setelah perubahan kode
docker compose up -d --build backend celery_worker celery_beat

# Akses database
docker exec -it tradingbot_postgres psql -U tradingbot -d tradingbot_db

# Jalankan migrasi
docker exec tradingbot_backend alembic upgrade head

# Test notifikasi Telegram manual
docker exec tradingbot_backend python3 -c "
import asyncio
from app.services.telegram_service import TelegramService
asyncio.run(TelegramService().send_message('test'))
"

# Jalankan unit tests
docker exec tradingbot_backend python -m pytest tests/ -v

# Cek Celery tasks aktif
docker compose exec celery_worker celery -A app.workers.celery_app inspect active
```

---

## Catatan Penting

- **Paper trading** — simulasi trading tanpa eksekusi nyata (mode default)
- **DeFi trading** — eksekusi nyata di blockchain. Gunakan wallet terpisah, tidak untuk dana utama
- **Bybit real trading** — eksekusi nyata di exchange. Mulai dengan modal kecil untuk verifikasi
- Bot menggunakan data harga **real Bybit** untuk semua analisis
- Bybit public API tidak perlu API key (hanya untuk data, bukan trading)
- DeepSeek API key: daftar di [platform.deepseek.com](https://platform.deepseek.com)
- Jangan commit file `.env` ke repository — semua secrets harus di `.env` lokal saja

---

## Troubleshooting

**Dashboard error 500:**
```bash
docker exec tradingbot_backend alembic upgrade head
```

**Scanner gagal "No market data":**
```bash
docker exec tradingbot_backend python3 -c \
  "import urllib.request; print(urllib.request.urlopen('https://api.bybit.com').status)"
```

**DeFi swap gagal "insufficient gas":**
Pastikan wallet punya ETH (Arbitrum/Optimism/Base) atau MATIC (Polygon) untuk gas fee.

**DeFi swap gagal "slippage":**
Naikkan `defi_slippage` di settings (coba 1.0 atau 2.0 untuk token dengan liquiditas rendah).

**Telegram command tidak respons:**
Pastikan `TELEGRAM_CHAT_ID` di `.env` sama dengan chat ID kamu. Cek log:
```bash
docker logs tradingbot_celery_beat --tail 50 | grep telegram
```

**Telegram tidak terkirim:**
Cek `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` sudah benar di `.env`, lalu:
```bash
docker compose restart celery_worker celery_beat
```

**Auto-tuning tidak jalan:**
Pastikan `auto_tuning_enabled = true` di Risk Settings. Minimal 5 closed trades diperlukan untuk analisis.

**Bybit order error "leverage not modified":**
Normal — Bybit return kode 110043 ketika leverage sudah sama. Bot handle ini otomatis.

**Port sudah dipakai:**
Edit `docker-compose.yml` bagian `ports` untuk ganti port.
