#!/bin/bash
# VPS Ubuntu Deployment Script
# Usage: ./scripts/deploy.sh [domain.com]
set -e

DOMAIN=${1:-""}
APP_DIR="/opt/tradingbot"
DB_PASSWORD=$(openssl rand -base64 32)

echo "=== TradingBot VPS Deployment ==="

# [1] System dependencies
echo "[1/8] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 git curl nginx certbot python3-certbot-nginx

systemctl enable docker && systemctl start docker

# [2] Clone / update repo
echo "[2/8] Setting up app directory..."
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR" && git pull
else
    git clone . "$APP_DIR" 2>/dev/null || cp -r . "$APP_DIR"
fi
cd "$APP_DIR"

# [3] Create .env
echo "[3/8] Creating environment file..."
if [ ! -f .env ]; then
    cp .env.example .env
    SECRET_KEY=$(openssl rand -base64 48)
    JWT_SECRET=$(openssl rand -base64 48)
    sed -i "s/your-super-secret-key-change-in-production-min-32-chars/$SECRET_KEY/g" .env
    sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" .env
    sed -i "s/DB_PASSWORD:-changeme/DB_PASSWORD:-$DB_PASSWORD/g" .env
    echo "DB_PASSWORD=$DB_PASSWORD" >> .env
    echo ".env created. Edit Binance API keys before starting."
fi

# [4] Build containers
echo "[4/8] Building Docker containers..."
docker compose build --no-cache

# [5] Setup Ollama
echo "[5/8] Setting up Ollama..."
bash scripts/setup_ollama.sh

# [6] Start services
echo "[6/8] Starting services..."
docker compose up -d postgres redis
sleep 15

# Run migrations
docker compose run --rm backend alembic upgrade head

docker compose up -d

# [7] SSL (optional)
if [ -n "$DOMAIN" ]; then
    echo "[7/8] Setting up SSL for $DOMAIN..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN"
else
    echo "[7/8] Skipping SSL (no domain provided)"
fi

# [8] Health check
echo "[8/8] Health check..."
sleep 10
curl -f http://localhost:8000/health && echo " Backend OK" || echo " Backend not ready"

echo ""
echo "=== Deployment Complete ==="
echo "Backend API: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "API Docs: http://localhost:8000/api/docs (debug mode only)"
echo ""
echo "IMPORTANT: Edit /opt/tradingbot/.env with your Binance API keys"
echo "DB Password: $DB_PASSWORD (save this securely!)"
