# FAQ & Troubleshooting

---

## Trading

**Q: Balance MetaMask saya tidak berkurang setelah ada notif "Trade Dibuka"**

Notif `🟢 Trade Dibuka` = paper trade (simulasi). Wallet tidak disentuh.
Real swap hanya terjadi kalau muncul notif `🔗 DeFi Trade Executed` + TX hash.

---

**Q: PnL paper trade saya +2000%? Itu benar?**

Ya, itu normal. PnL % dihitung dari risk capital (1% dari paper balance), bukan total balance.
Contoh: paper balance $10,000 → risk $100 → profit $500 → tampil **500%**.
Angka ini bukan PnL nyata dari wallet.

---

**Q: Bot selalu trade coin yang sama (BTCUSDT/ETHUSDT)**

Kemungkinan penyebab:
1. Watchlist hanya berisi BTCUSDT — cek Bot Settings → Scanner Config → Watchlist
2. Enable **DeFi Only Scan** → scanner otomatis terbatas ke 22 coin Arbitrum
3. Aktifkan **Scan All Coins** untuk scan top 50 coin by volume

---

**Q: Kenapa ada notif paper trade untuk coin seperti DRIFT, WLD, SOL?**

Coin tersebut tidak ada di Arbitrum → DeFi skip → fallback paper trade.
Aktifkan **DeFi Only Scan** di Bot Settings untuk menghindari ini.

---

**Q: Kapan real DeFi swap terjadi?**

Syarat semua harus terpenuhi:
- DeFi Trading toggle = ON
- Wallet address + private key tersimpan
- Scanner temukan sinyal BUY/SELL kuat
- Coin yang dapat sinyal ada di daftar 22 token Arbitrum
- Cukup USDC di wallet

---

**Q: Berapa gas fee per transaksi DeFi?**

Arbitrum: sekitar $0.01–$0.50 per swap (sangat murah vs Ethereum mainnet).
Pastikan wallet punya minimal 0.005 ETH di Arbitrum untuk gas.

---

## Teknis

**Q: Scanner error "Redirect response 301 ke internet-positif.info"**

Bybit diblokir oleh ISP Indonesia (Internet Positif/Kominfo).
Bot sudah dikonfigurasi pakai `api.bytick.com` sebagai alternatif domain.
Kalau masih error → hubungi developer untuk update konfigurasi.

---

**Q: Chart SmartChart blank/hitam**

Penyebab: data candle kosong karena API Bybit gagal.
Solusi: pastikan backend berjalan dengan benar, cek error di log Docker.
```bash
docker-compose logs backend --tail=50
```

---

**Q: AI Analysis tidak muncul data / hanya BTCUSDT**

1. Klik **Scan Manual** di halaman AI Analysis
2. Kalau scan error → cek apakah backend container jalan
3. Kalau "Scanner error" → biasanya koneksi Bybit bermasalah

---

**Q: Notifikasi Telegram tidak masuk**

1. Cek `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` di file `.env`
2. Bot Settings → klik **"Test Kirim Notifikasi"**
3. Pastikan sudah `/start` bot Telegram kamu dulu

---

**Q: Trade otomatis tidak jalan padahal Auto Trade = ON**

Cek urutan ini:
1. Bot Settings → **Auto Trade** = ON ✓
2. **AI Analysis Enabled** = ON ✓
3. Save Settings ✓
4. Scanner jalan setiap 5 menit (`AI_ANALYSIS_INTERVAL=300` di .env)
5. Bot butuh sinyal BUY/SELL dulu (score tidak nol) sebelum buka trade

---

## Keamanan

**Q: Apakah private key saya aman?**

Private key dienkripsi dengan AES-256 (Fernet) sebelum disimpan di database.
Kunci enkripsi berasal dari `SECRET_KEY` di file `.env`.
Pastikan `.env` tidak pernah di-commit ke Git atau dibagikan ke siapapun.

**Rekomendasi:**
- Gunakan wallet khusus trading, bukan main wallet
- Isi USDC secukupnya saja (tidak perlu deposit besar)
- Pantau wallet di MetaMask secara berkala

---

**Q: Apakah bot bisa akses lebih dari yang diizinkan di wallet?**

Bot hanya bisa lakukan:
- Transfer USDC untuk approve ke Uniswap router
- Swap USDC ↔ token via Uniswap V3
- Tidak bisa transfer ke address lain
- Tidak bisa drain wallet ke address hacker

Transaksi selalu ke alamat smart contract Uniswap yang sudah terverifikasi:
`SwapRouter02: 0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45`
