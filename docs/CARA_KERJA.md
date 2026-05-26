# Cara Kerja Bot

## Alur Otomatis (Setiap 5 Menit)

```
Bybit API (harga, volume, candles)
        ↓
Scanner ambil data semua coin di watchlist
        ↓
Hitung score: momentum + 24h change + sentimen Polymarket
        ↓
Sort by score → pilih top candidates
        ↓
AI DeepSeek analisis top 3–5 coin (opsional)
        ↓
┌─────────────────────────────────────┐
│  Apakah coin ada di Arbitrum?       │
│  ↓ YA           ↓ TIDAK             │
│  DeFi swap      Paper trade saja    │
│  (wallet nyata) (simulasi DB)       │
└─────────────────────────────────────┘
        ↓
Kirim notifikasi Telegram
```

## Komponen Sistem

### Scanner
- Baca harga real-time dari Bybit (USDT perpetuals)
- Baca sentimen pasar dari Polymarket (prediction market)
- Hitung score gabungan → rank coin terbaik

### AI Analysis
- DeepSeek Cloud API menganalisis data teknikal + sentimen
- Hasil: trend, recommended action, entry/SL/TP, confidence
- Kalau AI gagal → fallback ke heuristic (tetap jalan)

### DeFi Execution
- Swap USDC → token target via Uniswap V3 di Arbitrum
- Pakai private key wallet kamu untuk sign transaksi
- Tidak perlu MetaMask browser terbuka

### Paper Trading
- Simulasi trade di database
- Track PnL virtual, tidak sentuh wallet
- Berguna untuk evaluasi performa sebelum DeFi real

### Auto Close (Setiap 30 Detik)
- Cek semua open trades
- Kalau harga hit SL atau TP → tutup trade otomatis
- Kirim notifikasi hasil trade ke Telegram

## Score Formula

```
score = (momentum × 0.45) + (24h_change × 0.25) + (polymarket_bias × 0.30)
```

- `momentum` = pergerakan harga dari candle pertama ke terakhir
- `24h_change` = perubahan harga 24 jam (dari Bybit)
- `polymarket_bias` = sentimen pasar prediksi (dari Polymarket)

Score positif → **BUY signal**
Score negatif → **SELL signal**
Score mendekati 0 → **HOLD**
