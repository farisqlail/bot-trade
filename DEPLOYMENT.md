# VPS Ubuntu Deployment Guide

## Prerequisites
- Ubuntu 22.04 LTS VPS (min 4GB RAM, 2 vCPU — 8GB+ for Ollama/DeepSeek GPU)
- Domain pointing to VPS IP (optional)
- SSH access as root or sudo user

---

## Step 1 — Upload project to VPS

```bash
# From local machine
scp -r trading-bot/ user@YOUR_VPS_IP:/opt/tradingbot
# or
git clone https://github.com/yourrepo/trading-bot /opt/tradingbot
```

## Step 2 — Install Docker

```bash
apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable docker && systemctl start docker
```

## Step 3 — Configure environment

```bash
cd /opt/tradingbot
cp .env.example .env
nano .env
```

Required fields:
```env
# WAJIB
SECRET_KEY=<generate: openssl rand -base64 48>
JWT_SECRET_KEY=<generate: openssl rand -base64 48>
DB_PASSWORD=<strong password>

# AI
DEEPSEEK_API_KEY=sk-xxxx

# Telegram (highly recommended)
TELEGRAM_BOT_TOKEN=1234567890:AAExxx...
TELEGRAM_CHAT_ID=123456789

# Bybit real trading (optional — for CEX perpetual long/short)
BYBIT_API_KEY=
BYBIT_API_SECRET=

# CORS
CORS_ORIGINS=["https://yourdomain.com"]
```

## Step 4 — Setup Ollama (optional — only if not using DeepSeek API)

```bash
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
# Downloads deepseek-r1:7b (~4GB)
# Verify: ollama list
```

## Step 5 — Start database and run migrations

```bash
cd /opt/tradingbot
docker compose up -d postgres redis
sleep 15

# Run DB migrations
docker compose run --rm backend alembic upgrade head
```

## Step 6 — Start all services

```bash
docker compose up -d
docker compose ps    # all should show "Up"
```

## Step 7 — Verify

```bash
curl http://localhost:8000/health
# → {"status":"healthy","version":"1.0.0"}

# Register first user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","username":"admin","password":"Admin1234"}'
```

## Step 8 — SSL with Let's Encrypt (if domain)

```bash
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com -m admin@yourdomain.com --agree-tos
```

## Step 9 — Configure Nginx

```bash
cp /opt/tradingbot/nginx/nginx.conf /etc/nginx/nginx.conf
# Edit: replace 'your-domain.com' with actual domain
nginx -t && systemctl reload nginx
```

## Step 10 — Auto-restart on reboot

```bash
# Docker compose auto-restart is configured via "restart: unless-stopped"
# Verify:
docker compose ps
```

---

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Register user |
| POST | /api/v1/auth/login | Login → tokens |
| POST | /api/v1/auth/refresh | Refresh access token |
| GET | /api/v1/auth/me | Current user |
| GET | /api/v1/dashboard | Full dashboard data |
| POST | /api/v1/trades | Create trade |
| GET | /api/v1/trades/open | Open trades |
| GET | /api/v1/trades/history | Trade history |
| PATCH | /api/v1/trades/{id} | Update SL/TP |
| POST | /api/v1/trades/{id}/close | Close trade |
| POST | /api/v1/ai/analyze/{symbol} | Trigger AI analysis |
| GET | /api/v1/ai/latest/{symbol} | Latest AI analysis |
| GET | /api/v1/risk/status | Risk status |
| GET | /api/v1/risk/events | Risk events |
| GET | /api/v1/bot/settings | Bot settings |
| PATCH | /api/v1/bot/settings | Update settings |
| POST | /api/v1/bot/start | Start bot |
| POST | /api/v1/bot/stop | Stop bot |
| GET | /api/v1/defi/balance | DeFi wallet balance per network |
| POST | /api/v1/defi/swap | Manual DeFi swap |

---

## Celery Background Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `scan_market_opportunities` | 5 min | Scan coins, AI analysis, execute DeFi/Bybit trades |
| `check_stop_loss_take_profit` | 30s | Auto-close paper trades on SL/TP hit |
| `check_risk_limits` | 60s | Monitor and log risk events |
| `run_auto_tuning` | Daily 02:00 UTC | Analyze performance, adjust risk_percent |
| `process_telegram_callbacks` | 30s | Poll getUpdates: commands + inline button handlers |
| `monitor_defi_positions` | 60s | Check held DeFi tokens across all networks, auto-exit on SELL signal |
| `monitor_bybit_positions` | 60s | Sync Bybit positions to DB, signal-exit, move SL to breakeven |

---

## Monitoring

```bash
# View logs
docker compose logs -f backend
docker compose logs -f celery_worker
docker compose logs -f celery_beat

# Celery worker status
docker compose exec celery_worker celery -A app.workers.celery_app inspect active

# DB connection
docker compose exec postgres psql -U tradingbot -d tradingbot_db

# Check active Celery tasks
docker compose exec celery_worker celery -A app.workers.celery_app inspect registered
```

## Update deployment

```bash
cd /opt/tradingbot
git pull
docker compose build backend celery_worker celery_beat
docker compose run --rm backend alembic upgrade head
docker compose up -d backend celery_worker celery_beat
```

---

## Security Checklist

- [ ] Change SECRET_KEY and JWT_SECRET_KEY in .env (never reuse defaults)
- [ ] Bybit API key: Derivatives trade permission ONLY — NO withdrawal permission
- [ ] DeFi wallet: use dedicated bot wallet, not main/savings wallet
- [ ] Set CORS_ORIGINS to your frontend URL only
- [ ] Set ALLOWED_HOSTS to your domain
- [ ] Firewall: only 80/443 open externally (SSH via private network or VPN)
- [ ] Regular DB backups via pg_dump
- [ ] Monitor Telegram notifications daily for unexpected trade activity
- [ ] Set `defi_trade_percent` conservatively (start at 20–30% per trade)
- [ ] Set Bybit `leverage` conservatively (3–5x for small capital)
