import { useState, useEffect } from 'react'
import clsx from 'clsx'
import { botApi, defiApi } from '../services/api'

export default function BotSettings() {
  const [settings, setSettings] = useState(null)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [testingTelegram, setTestingTelegram] = useState(false)
  const [telegramResult, setTelegramResult] = useState(null)
  const [testingWallet, setTestingWallet] = useState(false)
  const [walletBalance, setWalletBalance] = useState(null)

  useEffect(() => {
    botApi.getSettings()
      .then((res) => {
        setSettings(res.data)
        setForm({
          symbol: res.data.symbol,
          leverage: res.data.leverage,
          default_stop_loss: res.data.default_stop_loss,
          default_take_profit: res.data.default_take_profit,
          auto_trade: res.data.auto_trade,
          ai_analysis_enabled: res.data.ai_analysis_enabled,
          ai_analysis_interval: res.data.ai_analysis_interval,
          use_public_data_only: res.data.use_public_data_only,
          scanner_watchlist: (res.data.scanner_watchlist || []).join(', '),
          paper_balance: res.data.paper_balance,
          paper_trade_enabled: res.data.paper_trade_enabled ?? false,
          scan_all_coins: res.data.scan_all_coins ?? false,
          max_scan_coins: res.data.max_scan_coins ?? 50,
          min_volume_filter: res.data.min_volume_filter ?? 5000000,
          polymarket_api_key: res.data.polymarket_api_key || '',
          polymarket_api_secret: '',
          bybit_leverage: res.data.bybit_leverage ?? 5,
          bybit_collateral_percent: res.data.bybit_collateral_percent ?? 10,
          bybit_sl_percent: res.data.bybit_sl_percent ?? 3,
          defi_enabled: res.data.defi_enabled ?? false,
          defi_network: res.data.defi_network || 'arbitrum',
          defi_wallet_address: res.data.defi_wallet_address || '',
          defi_private_key: '',
          defi_trade_percent: res.data.defi_trade_percent ?? 50,
          defi_slippage: res.data.defi_slippage ?? 0.5,
          defi_only_scan: res.data.defi_only_scan ?? false,
          gmx_enabled: res.data.gmx_enabled ?? false,
          gmx_leverage: res.data.gmx_leverage ?? 2,
          gmx_collateral_percent: res.data.gmx_collateral_percent ?? 10,
          gmx_sl_percent: res.data.gmx_sl_percent ?? 3,
          gtrade_enabled: res.data.gtrade_enabled ?? false,
          gtrade_leverage: res.data.gtrade_leverage ?? 2,
          gtrade_collateral_percent: res.data.gtrade_collateral_percent ?? 10,
          gtrade_sl_percent: res.data.gtrade_sl_percent ?? 3,
          continuous_scan_enabled: res.data.continuous_scan_enabled ?? true,
          position_sizing_method: res.data.position_sizing_method || 'fixed',
          kelly_fraction: res.data.kelly_fraction ?? 0.25,
        })
      })
      .catch(console.error)
  }, [])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form }
      if (typeof payload.scanner_watchlist === 'string') {
        payload.scanner_watchlist = payload.scanner_watchlist
          .split(',')
          .map((item) => item.trim().toUpperCase())
          .filter(Boolean)
          .join(',')
      }
      if (!payload.polymarket_api_secret) delete payload.polymarket_api_secret
      if (!payload.defi_private_key) delete payload.defi_private_key
      await botApi.updateSettings(payload)
      alert('Settings saved')
      const res = await botApi.getSettings()
      setSettings(res.data)
    } catch (e) {
      alert(e.response?.data?.error || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const testTelegram = async () => {
    setTestingTelegram(true)
    setTelegramResult(null)
    try {
      const res = await botApi.testTelegram()
      setTelegramResult({ ok: true, message: res.data.message })
    } catch (e) {
      setTelegramResult({ ok: false, message: e.response?.data?.detail || 'Gagal koneksi ke Telegram' })
    } finally {
      setTestingTelegram(false)
    }
  }

  const testWalletConnection = async () => {
    if (!form.defi_wallet_address) return alert('Masukkan wallet address dulu')
    setTestingWallet(true)
    setWalletBalance(null)
    try {
      const res = await defiApi.testConnection({
        wallet_address: form.defi_wallet_address,
        network: form.defi_network || 'arbitrum',
      })
      setWalletBalance(res.data)
    } catch (e) {
      alert(e.response?.data?.detail || 'Koneksi wallet gagal')
    } finally {
      setTestingWallet(false)
    }
  }

  const toggleBot = async () => {
    setToggling(true)
    try {
      if (settings?.bot_enabled) {
        await botApi.stop()
      } else {
        await botApi.start()
      }
      const res = await botApi.getSettings()
      setSettings(res.data)
    } catch (e) {
      alert(e.response?.data?.error || 'Toggle failed')
    } finally {
      setToggling(false)
    }
  }

  const Toggle = ({ label, name }) => (
    <div className="flex items-center justify-between py-3 border-b border-gray-800">
      <span className="text-sm">{label}</span>
      <button
        type="button"
        onClick={() => setForm((f) => ({ ...f, [name]: !f[name] }))}
        className={`relative w-10 h-5 rounded-full transition-colors p-0 overflow-hidden ${form[name] ? 'bg-indigo-600' : 'bg-gray-700'}`}
      >
        <span className={`absolute left-0 top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${form[name] ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </button>
    </div>
  )

  const Field = ({ label, name, type = 'text', step, placeholder }) => (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input
        type={type}
        step={step}
        placeholder={placeholder}
        value={form[name] ?? ''}
        onChange={(e) => setForm((f) => ({
          ...f,
          [name]: type === 'number'
            ? (e.target.value === '' ? '' : parseFloat(e.target.value))
            : e.target.value,
        }))}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
      />
    </div>
  )

  const applyMicroCapitalPreset = () => {
    setForm((f) => ({
      ...f,
      paper_balance: 4.25,
      leverage: 1,
      scan_all_coins: false,
      max_scan_coins: 10,
      min_volume_filter: 1000000,
      defi_trade_percent: 30,
      defi_slippage: 1.0,
    }))
  }

  if (!settings) return <div className="animate-pulse text-gray-500">Loading settings...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Bot Settings</h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={applyMicroCapitalPreset}
            className="px-4 py-2 text-xs rounded-lg font-semibold border border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 transition-colors"
            title="Isi form dengan preset optimal untuk modal $1–$10 USDC"
          >
            💰 Preset Micro Capital ($4.25)
          </button>
          <button
            onClick={toggleBot}
            disabled={toggling}
            className={`px-6 py-2 text-sm rounded-lg font-semibold transition-colors disabled:opacity-50 ${
              settings.bot_enabled
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30'
                : 'bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/30'
            }`}
          >
            {toggling ? 'Working...' : settings.bot_enabled ? 'Stop Bot' : 'Start Bot'}
          </button>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-5">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-4">Market Config</h3>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Primary Symbol" name="symbol" placeholder="BTCUSDT" />
            <Field label="Leverage (strategy only)" name="leverage" type="number" step="1" />
            <Field label="Default Stop Loss" name="default_stop_loss" type="number" step="0.01" />
            <Field label="Default Take Profit" name="default_take_profit" type="number" step="0.01" />
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-4">Scanner Config</h3>
          <Toggle label="Scan All Listed Coins (override watchlist)" name="scan_all_coins" />
          {form.scan_all_coins ? (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Field label="Max Coins to Scan" name="max_scan_coins" type="number" step="5" placeholder="50" />
                <Field label="Min 24h Volume USD" name="min_volume_filter" type="number" step="1000000" placeholder="5000000" />
              </div>
              <p className="text-xs text-emerald-400">
                Scanner ambil semua USDT perpetuals dari Bybit (1 API call), filter volume ≥ min, sort by |%change 24h| terbesar, lalu scan top N coin.
              </p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <Field
                label="Watchlist"
                name="scanner_watchlist"
                placeholder="BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT"
              />
              <p className="text-xs text-gray-500">
                Scanner baca data real Bybit untuk coin di watchlist. Pisahkan coin dengan koma.
              </p>
            </div>
          )}
          <div className="mt-4">
            <Field label="Paper Balance" name="paper_balance" type="number" step="100" />
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-2">Bot Options</h3>
          <Toggle label="Auto Scan — Bot scan terus dan kirim notifikasi Telegram otomatis" name="continuous_scan_enabled" />
          <Toggle label="Auto Trade Real — Execute nyata (DeFi/GMX/Bybit) saat ada signal" name="auto_trade" />
          <Toggle label="Paper Trading (Simulasi) — Catat trade simulasi tanpa uang nyata" name="paper_trade_enabled" />
          <Toggle label="AI Analysis Enabled" name="ai_analysis_enabled" />
          <Toggle label="Use Public Data Only" name="use_public_data_only" />
          <div className="mt-3">
            <Field label="Scan Interval (seconds)" name="ai_analysis_interval" type="number" step="60" />
          </div>
          <p className="mt-3 text-xs text-cyan-400">
            Rekomendasi start: 300 detik atau 5 menit. Cukup cepat buat scanner, tidak terlalu berisik.
          </p>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-1">Position Sizing</h3>
          <p className="text-xs text-gray-500 mb-4">
            <strong>Fixed</strong>: risk_amount = balance × risk_percent (simple, predictable).<br />
            <strong>Kelly Criterion</strong>: risk_amount derived from historical win rate + R ratio — adapts to edge.
            Requires ≥10 closed trades.
          </p>

          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-2">Sizing Method</label>
            <div className="flex gap-3">
              {['fixed', 'kelly'].map((method) => (
                <button
                  key={method}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, position_sizing_method: method }))}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                    form.position_sizing_method === method
                      ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                      : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-600'
                  }`}
                >
                  {method === 'fixed' ? 'Fixed %' : 'Kelly Criterion'}
                </button>
              ))}
            </div>
          </div>

          {form.position_sizing_method === 'kelly' && (
            <div className="space-y-3">
              <Field label="Kelly Fraction (0.1 = 10%, 0.25 = quarter-Kelly, 1.0 = full-Kelly)" name="kelly_fraction" type="number" step="0.05" placeholder="0.25" />
              <p className="text-xs text-amber-400">
                ⚠️ Quarter-Kelly (0.25) recommended. Full Kelly (1.0) can cause large drawdowns.
                Falls back to fixed risk_percent if &lt;10 trades or negative edge detected.
              </p>
            </div>
          )}
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-4">Bybit Futures API</h3>

          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mb-4 text-xs text-blue-300">
            ⚡ <strong>Bybit CEX Futures.</strong> API Key & Secret dari <strong>Bybit.com → API Management → Create API</strong>. Pilih permission: Read + Trade. CEX: dana USDT ada di akun Bybit, bukan MetaMask/Arbitrum.
          </div>

          <div className="space-y-3">
            <Field label="Bybit API Key" name="polymarket_api_key" />
            <Field label="Bybit API Secret (leave blank to keep existing)" name="polymarket_api_secret" type="password" />
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-3">Bybit Futures Settings</h3>

          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mb-4 text-xs text-yellow-300">
            ⚠️ <strong>Default settings untuk Bybit Futures.</strong> Digunakan saat trade altcoin via Bybit dari Altcoin Scanner. USDT balance di Bybit = modal trading CEX.
          </div>

          <div className="mt-4 grid grid-cols-3 gap-4">
            <Field label="Leverage (x)" name="bybit_leverage" type="number" step="1" placeholder="5" />
            <Field label="Collateral per Trade (% USDT)" name="bybit_collateral_percent" type="number" step="5" placeholder="10" />
            <Field label="Stop-Loss %" name="bybit_sl_percent" type="number" step="0.5" placeholder="3" />
          </div>

          <div className="mt-3 text-xs text-gray-500 space-y-1">
            <div>• Collateral 10% + Leverage 5x = Position size 50% USDT balance per signal</div>
            <div>• Stop-loss otomatis close jika harga bergerak melebihi SL%</div>
            <div>• Minimal USDT di Bybit: $1.00 per trade</div>
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-1">Telegram Notifications</h3>
          <p className="text-xs text-gray-500 mb-4">
            Token dan Chat ID diset di file <code className="text-cyan-400">.env</code> server.
            Klik tombol di bawah untuk test koneksi.
          </p>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={testTelegram}
              disabled={testingTelegram}
              className="px-5 py-2 rounded-lg bg-sky-500/20 border border-sky-500/30 text-sky-300 text-sm font-semibold hover:bg-sky-500/30 disabled:opacity-50 transition-colors"
            >
              {testingTelegram ? 'Mengirim...' : '📨 Test Kirim Notifikasi'}
            </button>
            {telegramResult && (
              <span className={clsx(
                'text-sm font-medium',
                telegramResult.ok ? 'text-emerald-400' : 'text-red-400'
              )}>
                {telegramResult.ok ? '✅' : '❌'} {telegramResult.message}
              </span>
            )}
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-3">DeFi Wallet — Uniswap</h3>

          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mb-4 text-xs text-yellow-300">
            ⚠️ <strong>Gunakan wallet KHUSUS trading</strong> dengan dana kecil. Jangan pernah input private key main wallet. Private key dienkripsi AES-256 sebelum disimpan.
          </div>

          <Toggle label="Enable DeFi Trading (Uniswap)" name="defi_enabled" />
          <Toggle label="DeFi Only Scan (hanya coin yang ada di Arbitrum)" name="defi_only_scan" />

          <div className="mt-4 space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Network</label>
              <select
                value={form.defi_network || 'arbitrum'}
                onChange={(e) => setForm((f) => ({ ...f, defi_network: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
              >
                <option value="arbitrum">Arbitrum One (recommended — gas termurah)</option>
                <option value="optimism">Optimism</option>
                <option value="base">Base</option>
                <option value="polygon">Polygon</option>
              </select>
            </div>

            <Field label="Wallet Address (0x...)" name="defi_wallet_address" placeholder="0xabc123..." />

            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Private Key {settings?.defi_has_private_key && <span className="text-emerald-400 ml-1">✓ sudah tersimpan</span>}
              </label>
              <input
                type="password"
                placeholder={settings?.defi_has_private_key ? '(leave blank to keep existing)' : '0x... atau tanpa 0x'}
                value={form.defi_private_key ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, defi_private_key: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Trade Size (% USDC per signal)" name="defi_trade_percent" type="number" step="5" placeholder="50" />
              <Field label="Slippage %" name="defi_slippage" type="number" step="0.1" placeholder="0.5" />
            </div>

            <div className="flex items-center gap-3 mt-2">
              <button
                type="button"
                onClick={testWalletConnection}
                disabled={testingWallet}
                className="px-5 py-2 rounded-lg bg-violet-500/20 border border-violet-500/30 text-violet-300 text-sm font-semibold hover:bg-violet-500/30 disabled:opacity-50 transition-colors"
              >
                {testingWallet ? 'Connecting...' : '🔗 Test Wallet Connection'}
              </button>
              {walletBalance && (
                <div className="text-sm text-emerald-400">
                  ✅ ETH: {walletBalance.eth_balance} | USDC: ${walletBalance.usdc_balance}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-3">GMX Futures — Arbitrum Perpetuals</h3>

          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mb-4 text-xs text-blue-300">
            ⚡ <strong>GMX V2 on-chain futures.</strong> BUY signal = LONG, SELL signal = SHORT. Butuh ETH untuk execution fee (~0.001 ETH/order). Pakai wallet yang sama dengan DeFi Uniswap.
          </div>

          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mb-4 text-xs text-yellow-300">
            ⚠️ <strong>Markets tersedia:</strong> ETHUSDT, ARBUSDT, LINKUSDT, SOLUSDT, AVAXUSDT, GMXUSDT, OPUSDT
          </div>

          <Toggle label="Enable GMX Futures Trading" name="gmx_enabled" />

          <div className="mt-4 grid grid-cols-3 gap-4">
            <Field label="Leverage (x)" name="gmx_leverage" type="number" step="0.5" placeholder="2" />
            <Field label="Collateral per Trade (% USDC)" name="gmx_collateral_percent" type="number" step="5" placeholder="10" />
            <Field label="Stop-Loss %" name="gmx_sl_percent" type="number" step="0.5" placeholder="3" />
          </div>

          <div className="mt-3 text-xs text-gray-500 space-y-1">
            <div>• Collateral 10% + Leverage 2x = Position size 20% USDC per signal</div>
            <div>• Stop-loss otomatis close position jika harga turun (LONG) atau naik (SHORT) melebihi SL%</div>
            <div>• Order dieksekusi keeper GMX ~1-10 detik setelah submit</div>
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-3">gTrade Futures — Gains Network Arbitrum</h3>

          <div className="bg-teal-500/10 border border-teal-500/30 rounded-lg p-3 mb-4 text-xs text-teal-300">
            ⚡ <strong>gTrade on-chain futures.</strong> Biaya sangat rendah (~$0.01–0.05 per order, hanya gas Arbitrum). Tidak perlu ETH execution fee seperti GMX. Collateral USDC langsung.
          </div>

          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mb-4 text-xs text-yellow-300">
            ⚠️ <strong>Pairs tersedia:</strong> BTC, ETH, LINK, DOGE, SOL, BNB, XRP, AVAX, ARB, MATIC — max leverage hingga 150x
          </div>

          <Toggle label="Enable gTrade Futures Trading" name="gtrade_enabled" />

          <div className="mt-4 grid grid-cols-3 gap-4">
            <Field label="Leverage (x)" name="gtrade_leverage" type="number" step="0.5" placeholder="2" />
            <Field label="Collateral per Trade (% USDC)" name="gtrade_collateral_percent" type="number" step="5" placeholder="10" />
            <Field label="Stop-Loss %" name="gtrade_sl_percent" type="number" step="0.5" placeholder="3" />
          </div>

          <div className="mt-3 text-xs text-gray-500 space-y-1">
            <div>• Collateral 10% + Leverage 2x = Position size 20% USDC per signal</div>
            <div>• Tidak perlu ETH — hanya gas Arbitrum ~$0.01–0.05</div>
            <div>• Order dieksekusi langsung via Diamond contract Gains Network</div>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors"
        >
          {saving ? 'Saving...' : 'Save All Settings'}
        </button>
      </form>
    </div>
  )
}
