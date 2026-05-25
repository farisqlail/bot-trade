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
          scan_all_coins: res.data.scan_all_coins ?? false,
          max_scan_coins: res.data.max_scan_coins ?? 50,
          min_volume_filter: res.data.min_volume_filter ?? 5000000,
          polymarket_api_key: res.data.polymarket_api_key || '',
          polymarket_api_secret: '',
          polymarket_api_passphrase: '',
          defi_enabled: res.data.defi_enabled ?? false,
          defi_network: res.data.defi_network || 'arbitrum',
          defi_wallet_address: res.data.defi_wallet_address || '',
          defi_private_key: '',
          defi_trade_percent: res.data.defi_trade_percent ?? 50,
          defi_slippage: res.data.defi_slippage ?? 0.5,
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
      if (!payload.polymarket_api_passphrase) delete payload.polymarket_api_passphrase
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

  if (!settings) return <div className="animate-pulse text-gray-500">Loading settings...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Bot Settings</h2>
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
          <Toggle label="Auto Trade (simulation logic)" name="auto_trade" />
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
          <h3 className="font-semibold mb-4">Polymarket API</h3>
          <div className="space-y-3">
            <Field label="API Key" name="polymarket_api_key" />
            <Field label="API Secret (leave blank to keep existing)" name="polymarket_api_secret" type="password" />
            <Field label="API Passphrase (leave blank to keep existing)" name="polymarket_api_passphrase" type="password" />
          </div>
          <p className="text-xs text-yellow-400 mt-3">
            Public Gamma and CLOB read endpoints need no auth. Trading endpoints need Polymarket CLOB credentials.
          </p>
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
