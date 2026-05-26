# Notifikasi Telegram

Bot kirim notifikasi otomatis ke Telegram kamu. Setup token di file `.env` server.

---

## Jenis Notifikasi

### 🟢 Trade Dibuka (Paper Trade)
```
🟢 Trade Dibuka — ETHUSDT
━━━━━━━━━━━━━━━━
Arah: LONG
Entry: $3,450.00
SL: $3,382.50   TP: $3,553.50
📊 Score: 0.0234  Conf: 72%
🧠 Sentiment: BUY
📈 24h Change: +3.21%
📦 Volume 24h: $12,543,000,000
```
**Artinya:** Sinyal terdeteksi, paper trade dibuat di database. Wallet tidak bergerak.

---

### 🔗 DeFi Trade Executed (Real Swap)
```
🔗 DeFi Trade Executed

Pair: ETHUSDT
Direction: 🟢 BUY
Network: arbitrum
TX: 0xabc123def456...
Gas used: 158423
```
**Artinya:** USDC di wallet kamu di-swap ke token target via Uniswap V3. Cek TX di Arbiscan.

---

### ✅ Trade Ditutup
```
✅ Trade Ditutup — ETHUSDT
━━━━━━━━━━━━━━━━
PnL: $+45.23 (+45.23%)
Exit: $3,553.50
Alasan: TP hit
💰 Saldo Baru: $10,045.23
```
**Artinya:** Trade paper ditutup karena Take Profit tercapai.
- `Saldo Baru` = paper balance virtual, bukan wallet nyata
- `PnL %` = return on risk capital (bukan return on total balance)

---

### ❌ Trade Ditutup (Loss)
```
❌ Trade Ditutup — ETHUSDT
━━━━━━━━━━━━━━━━
PnL: $-100.00 (-100.00%)
Exit: $3,382.50
Alasan: SL hit
💰 Saldo Baru: $9,900.00
```
**Artinya:** Stop Loss kena. Paper balance berkurang sesuai risk per trade.

---

### 📊 Scan Results
Dikirim setelah setiap scan otomatis (tiap 5 menit kalau bot aktif).
Berisi ringkasan sinyal yang ditemukan.

---

## Interpretasi Notifikasi

| Field | Keterangan |
|-------|-----------|
| Score | Kekuatan sinyal gabungan (-1 sampai +1). Semakin jauh dari 0, semakin kuat |
| Conf | Confidence AI (0–100%). >70% = sinyal kuat |
| Sentiment | STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL |
| 24h Change | Perubahan harga 24 jam dari Bybit |
| Volume 24h | Volume trading 24 jam (USD) |
| PnL % | Return on risk capital. $100 profit dari $100 risk = 100% |
| Saldo Baru | Paper balance virtual — BUKAN saldo wallet MetaMask |

---

## Test Koneksi Telegram

Bot Settings → klik **"Test Kirim Notifikasi"**

Kalau berhasil: `✅ Trading Bot Connected!` muncul di Telegram kamu.
Kalau gagal: cek `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` di file `.env` server.
