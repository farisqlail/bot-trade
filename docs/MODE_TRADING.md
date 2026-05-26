# Mode Trading

Bot punya **2 mode** yang berjalan **bersamaan**, bukan pilihan:

---

## 1. Paper Trading (Simulasi)

- **Selalu aktif** untuk semua sinyal
- Trade dibuat di database saja — wallet tidak disentuh
- PnL dihitung virtual berdasarkan pergerakan harga nyata
- `Saldo Baru` di notifikasi = saldo virtual, bukan uang nyata

### Notifikasi Paper Trade
```
🟢 Trade Dibuka — DRIFTUSDT
Arah: LONG
Entry: $0.04293
SL: $0.042286   TP: $0.044218
```
```
✅ Trade Ditutup — WLDUSDT
PnL: $+2149.18 (+2149.18%)
Exit: $0.381
Alasan: TP hit
💰 Saldo Baru: $12,149.18
```

### Catatan PnL %
PnL % dihitung dari **risk capital** (1% dari paper balance), bukan dari total balance.
Contoh: paper balance $10,000 → risk $100 → PnL $200 → tampil **200%**, bukan 2%.

---

## 2. DeFi Trading (Real — Uniswap Arbitrum)

- Jalan **hanya** untuk coin yang punya token ERC-20 di jaringan yang dipilih
- Menggunakan USDC di wallet kamu sebagai modal
- Sign transaksi pakai private key yang kamu input di Bot Settings
- Hasil kelihatan di MetaMask: USDC berkurang, token target bertambah

### Coin yang Bisa DeFi (Arbitrum)

| Bybit Symbol | Token | Fee Tier |
|-------------|-------|----------|
| ETHUSDT | WETH | 0.05% |
| BTCUSDT | WBTC | 0.05% |
| ARBUSDT | ARB | 0.05% |
| GMXUSDT | GMX | 0.3% |
| LINKUSDT | LINK | 0.3% |
| AAVEUSDT | AAVE | 0.3% |
| PENDLEUSDT | PENDLE | 0.3% |
| UNIUSDT | UNI | 0.3% |
| SUSHIUSDT | SUSHI | 0.3% |
| CRVUSDT | CRV | 0.3% |
| COMPUSDT | COMP | 0.3% |
| SNXUSDT | SNX | 0.3% |
| LDOUSDT | LDO | 0.3% |
| BALUSDT | BAL | 0.3% |
| RDNTUSDT | RDNT | 0.3% |
| STGUSDT | STG | 0.3% |
| GNSUSDT | GNS | 0.3% |
| OPUSDT | OP | 0.3% |
| 1INCHUSDT | 1INCH | 0.3% |
| MAGICUSDT | MAGIC | 0.3% |
| DPXUSDT | DPX | 1% |
| YFIUSDT | YFI | 1% |

Coin di luar tabel ini → paper trade saja (tidak ada DeFi execution).

### Notifikasi DeFi Trade
```
🔗 DeFi Trade Executed

Pair: ETHUSDT
Direction: 🟢 BUY
Network: arbitrum
TX: 0xabc123...
Gas used: 150000
```

---

## Perbandingan

| | Paper Trade | DeFi Trade |
|--|-------------|------------|
| Wallet berubah | ❌ Tidak | ✅ Ya |
| Notifikasi | 🟢 Trade Dibuka | 🔗 DeFi Trade Executed |
| TX Hash | ❌ Tidak ada | ✅ Ada |
| Semua coin | ✅ Ya | ❌ Hanya 22 coin Arbitrum |
| Risiko | Nol | Real (USDC berkurang) |
