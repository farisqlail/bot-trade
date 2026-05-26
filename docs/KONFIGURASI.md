# Konfigurasi Bot

## Bot Settings — Halaman Utama

### Market Config
| Field | Keterangan | Default |
|-------|-----------|---------|
| Primary Symbol | Symbol utama untuk analisis | BTCUSDT |
| Leverage | Leverage strategi (paper only) | 10 |
| Default Stop Loss | SL default kalau tidak dihitung otomatis | 103500 |
| Default Take Profit | TP default kalau tidak dihitung otomatis | 107000 |

---

### Scanner Config

**Scan All Listed Coins** — OFF (default)
- OFF → scan coin di Watchlist saja
- ON → scan top N coin dari Bybit berdasarkan volume

**Watchlist** (kalau Scan All = OFF)
- Isi coin yang mau discan, pisahkan dengan koma
- Contoh: `ETHUSDT, ARBUSDT, LINKUSDT, GMXUSDT`
- Default: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, BNBUSDT`

**Max Coins to Scan** (kalau Scan All = ON)
- Berapa banyak coin yang discan dari hasil filter volume
- Default: 50

**Min 24h Volume USD** (kalau Scan All = ON)
- Filter minimum volume harian
- Default: $5,000,000

**Paper Balance**
- Modal virtual untuk simulasi paper trade
- Default: $10,000

---

### Bot Options

| Toggle | Keterangan |
|--------|-----------|
| Auto Trade | Bot otomatis buka paper trade saat ada sinyal |
| AI Analysis Enabled | Aktifkan analisis DeepSeek AI |
| Use Public Data Only | Gunakan data publik Bybit (tidak perlu API key) |

**Scan Interval** — seberapa sering scanner jalan (default: 300 detik = 5 menit)

---

### DeFi Wallet — Uniswap

| Field | Keterangan |
|-------|-----------|
| Enable DeFi Trading | Toggle utama DeFi on/off |
| DeFi Only Scan | Scan hanya 22 coin yang bisa diswap di Arbitrum |
| Network | Pilih: Arbitrum (rekomendasi), Optimism, Base, Polygon |
| Wallet Address | Alamat `0x...` wallet MetaMask kamu |
| Private Key | Private key wallet (dienkripsi AES-256 di DB) |
| Trade Size % USDC | Berapa % USDC digunakan per trade (default: 50%) |
| Slippage % | Toleransi slippage swap (default: 0.5%, naikan ke 1% untuk altcoin) |

> **Keamanan:** Private key dienkripsi sebelum disimpan. Gunakan wallet khusus trading dengan dana kecil. Jangan pakai main wallet.

**Test Wallet Connection** — klik untuk verifikasi wallet terbaca dan lihat balance ETH + USDC.

---

## Risk Settings

| Field | Keterangan | Default |
|-------|-----------|---------|
| Daily Loss Limit % | Stop trading kalau loss harian melebihi % ini | 3% |
| Max Drawdown % | Stop trading kalau total drawdown melebihi % ini | 10% |
| Consecutive Loss Limit | Stop trading kalau kalah N kali berturut-turut | 3 |
| Risk Per Trade % | % balance yang dirisikkan per trade | 1% |

---

## Rekomendasi Setup untuk Modal Kecil ($1–$10 USDC)

Klik tombol **"Preset Micro Capital ($4.25)"** di Bot Settings untuk auto-isi:
- Paper Balance: $4.25
- Leverage: 1x
- Trade Size: 30% USDC
- Slippage: 1%
- Scan All Coins: OFF
- Max Scan: 10 coin

---

## Urutan Setup yang Benar

1. Isi Watchlist atau aktifkan Scan All Coins
2. Enable DeFi Trading → isi Wallet Address + Private Key
3. Enable DeFi Only Scan (opsional tapi rekomendasi)
4. Klik **Test Wallet Connection** → pastikan balance terbaca
5. Enable **Auto Trade** → bot otomatis buka trade saat sinyal muncul
6. Save All Settings
7. Klik Scan Manual di AI Analysis untuk test pertama
