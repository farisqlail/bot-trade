import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { gtradeApi, aiApi, bybitFuturesApi } from '../services/api'
import {
  Triangle, AlertCircle, RefreshCw, TrendingUp, TrendingDown,
  DollarSign, Activity, Wallet, ChevronDown, X, CheckCircle, Brain, Sparkles,
} from 'lucide-react'
import clsx from 'clsx'

function SignalBadge({ action }) {
  if (!action) return <span className="text-zinc-600 text-xs">—</span>
  const map = {
    STRONG_BUY: { label: 'STRONG BUY', cls: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
    BUY: { label: 'BUY', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
    HOLD: { label: 'HOLD', cls: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
    SELL: { label: 'SELL', cls: 'bg-red-500/10 text-red-400 border-red-500/20' },
    STRONG_SELL: { label: 'STRONG SELL', cls: 'bg-red-500/20 text-red-300 border-red-500/30' },
  }
  const cfg = map[action] || { label: action, cls: 'bg-zinc-800 text-zinc-400 border-zinc-700' }
  return (
    <span className={clsx('px-2 py-0.5 rounded-md text-[10px] font-bold border', cfg.cls)}>
      {cfg.label}
    </span>
  )
}

function DirectionBadge({ direction }) {
  return (
    <span className={clsx(
      'px-2 py-0.5 rounded-md text-[10px] font-bold border',
      direction === 'LONG'
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
        : 'bg-red-500/10 text-red-400 border-red-500/20'
    )}>
      {direction}
    </span>
  )
}

function PnlBadge({ pnl, pct }) {
  if (pnl == null) return <span className="text-zinc-500 text-xs">—</span>
  const pos = pnl >= 0
  return (
    <div className={clsx('text-right', pos ? 'text-emerald-400' : 'text-red-400')}>
      <div className="text-sm font-semibold">{pos ? '+' : ''}{pnl?.toFixed(2)} USDC</div>
      <div className="text-[10px] opacity-70">{pos ? '+' : ''}{pct?.toFixed(2)}%</div>
    </div>
  )
}

function StatCard({ label, value, sub, icon: Icon, color }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-zinc-500">{label}</span>
        <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', color)}>
          <Icon size={14} className="text-white" />
        </div>
      </div>
      <div className="text-xl font-bold text-white">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  )
}

const PAIRS_LIST = [
  'BTC/USDT', 'ETH/USDT', 'LINK/USDT', 'DOGE/USDT',
  'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'AVAX/USDT', 'ARB/USDT', 'MATIC/USDT',
]

export default function GTradeFutures() {
  const navigate = useNavigate()
  const [status, setStatus] = useState(null)
  const [positions, setPositions] = useState([])
  const [pairs, setPairs] = useState([])
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [toast, setToast] = useState(null)

  // Trade form state
  const [selectedSymbol, setSelectedSymbol] = useState('ETH/USDT')
  const [collateral, setCollateral] = useState('')
  const [leverage, setLeverage] = useState(2)
  const [tpPercent, setTpPercent] = useState('')
  const [slPercent, setSlPercent] = useState('3')
  const [pairsTab, setPairsTab] = useState('gtrade')
  const [altcoins, setAltcoins] = useState([])
  const [altcoinLoading, setAltcoinLoading] = useState(false)
  const [altcoinError, setAltcoinError] = useState(null)

  // Altcoin trade modal
  const [altcoinModal, setAltcoinModal] = useState(null) // { coin, signal, signalLoading }
  const [modalTradeLoading, setModalTradeLoading] = useState(false)
  const [bybitBalance, setBybitBalance] = useState(null) // { usdt, usdc, total }
  const [bybitDepositAddr, setBybitDepositAddr] = useState(null) // { address, network_name }
  const [depositLoading, setDepositLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const fetchAll = useCallback(async () => {
    try {
      const [statusRes, posRes, pairsRes, logsRes] = await Promise.all([
        gtradeApi.getStatus(),
        gtradeApi.getPositions(),
        gtradeApi.getPairs(),
        gtradeApi.getLogs(),
      ])
      setStatus(statusRes.data)
      setPositions(posRes.data.positions || [])
      const fetchedPairs = pairsRes.data.pairs || []
      setPairs(fetchedPairs)
      setSelectedSymbol(prev => {
        const symbols = fetchedPairs.map(p => p.symbol)
        return symbols.includes(prev) ? prev : (symbols[0] || prev)
      })
      setLogs(logsRes.data.logs || [])
      setError(null)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load gTrade data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const timer = setInterval(fetchAll, 15000)
    return () => clearInterval(timer)
  }, [fetchAll])

  const handleTrade = async (direction, overrideSymbol = null) => {
    if (!status?.gtrade_enabled) {
      showToast('gTrade not enabled. Enable in Bot Settings.', 'error')
      return
    }
    if (!status?.wallet_configured) {
      showToast('Wallet not configured. Set wallet in Bot Settings.', 'error')
      return
    }
    const sym = overrideSymbol || selectedSymbol
    if (overrideSymbol) setSelectedSymbol(overrideSymbol)
    setActionLoading(true)
    try {
      const payload = {
        symbol: sym,
        direction,
        leverage: Number(leverage),
      }
      if (collateral) payload.collateral_usdc = Number(collateral)
      const res = await gtradeApi.openTrade(payload)
      showToast(
        `${direction.toUpperCase()} ${sym} @ $${res.data.entry_price?.toFixed(2)} — close manually`,
        'success'
      )
      await fetchAll()
    } catch (e) {
      showToast(e.response?.data?.detail || 'Trade failed', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleApplyAiTpsl = async (symbol = null) => {
    setActionLoading(true)
    try {
      const res = await gtradeApi.applyAiTpsl(symbol)
      const updated = res.data.updated || []
      const errors = res.data.errors || []
      if (updated.length > 0) {
        showToast(`AI TP/SL applied to ${updated.map(u => u.symbol).join(', ')}`, 'success')
      } else if (errors.length > 0) {
        showToast(errors[0].error || 'No AI signal available', 'error')
      }
      await fetchAll()
    } catch (e) {
      showToast(e.response?.data?.detail || 'Apply AI TP/SL failed', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleForceCloseAll = async () => {
    if (!confirm('Force close ALL positions from gTrade API? This submits close requests — USDC arrives after keeper settles (few minutes).')) return
    setActionLoading(true)
    try {
      const res = await gtradeApi.forceCloseAll()
      const results = res.data.results || []
      const ok = results.filter(r => r.tx_hash).length
      const fail = results.filter(r => r.error).length
      showToast(`${ok} close request(s) submitted${fail ? `, ${fail} failed` : ''}. USDC arrives within minutes.`, ok > 0 ? 'success' : 'error')
      await fetchAll()
    } catch (e) {
      showToast(e.response?.data?.detail || 'Force close failed', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleClose = async (symbol) => {
    if (!confirm(`Close ${symbol} position?`)) return
    setActionLoading(true)
    try {
      const res = await gtradeApi.closePosition(symbol)
      const pnl = res.data.pnl_usd
      const txShort = res.data.tx_hash ? ` | Tx: ${res.data.tx_hash.slice(0, 10)}…` : ''
      showToast(
        `Close request submitted${txShort} — USDC tiba setelah keeper (~1-5 menit). Est PnL: ${pnl >= 0 ? '+' : ''}${pnl?.toFixed(2)} USDC`,
        'success'
      )
      await fetchAll()
    } catch (e) {
      showToast(e.response?.data?.detail || 'Close failed', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const fetchAltcoins = useCallback(async () => {
    setAltcoinLoading(true)
    setAltcoinError(null)
    try {
      const res = await aiApi.getAltcoins({ limit: 30, min_volume_usd: 500000 })
      setAltcoins(res.data.altcoins || [])
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Request failed'
      setAltcoinError(msg)
      setAltcoins([])
    } finally {
      setAltcoinLoading(false)
    }
  }, [])

  useEffect(() => {
    if (pairsTab === 'altcoins' && altcoins.length === 0) fetchAltcoins()
  }, [pairsTab, altcoins.length, fetchAltcoins])

  const toGtradePair = (bybitSymbol) => `${bybitSymbol.replace('USDT', '')}/USDT`

  const handleAltcoinClick = useCallback(async (coin) => {
    const gPair = toGtradePair(coin.symbol)
    const isGtrade = pairs.some(p => p.symbol === gPair)
    setBybitBalance(null)
    setBybitDepositAddr(null)
    setAltcoinModal({ coin, signal: null, signalLoading: true, isGtrade, gPair })

    const [sigRes] = await Promise.allSettled([
      aiApi.getLatest(coin.symbol),
      !isGtrade ? bybitFuturesApi.getBalance().then(r => setBybitBalance(r.data)) : Promise.resolve(),
    ])
    setAltcoinModal(prev => prev ? {
      ...prev,
      signal: sigRes.status === 'fulfilled' ? sigRes.value.data : null,
      signalLoading: false,
    } : null)
  }, [pairs])

  const handleGetDepositAddress = async () => {
    setDepositLoading(true)
    try {
      const res = await bybitFuturesApi.getDepositAddress('USDC')
      setBybitDepositAddr(res.data)
    } catch (e) {
      showToast(e.response?.data?.detail || 'Cannot get deposit address', 'error')
    } finally {
      setDepositLoading(false)
    }
  }

  const handleCopyAddress = (addr) => {
    navigator.clipboard.writeText(addr)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleModalTrade = async (direction) => {
    if (!altcoinModal) return
    const { coin, signal, isGtrade, gPair } = altcoinModal
    setModalTradeLoading(true)

    const currentPrice = parseFloat(coin.price)
    let slPct = slPercent ? Number(slPercent) : 3
    let tpPct = tpPercent ? Number(tpPercent) : null
    if (signal?.suggested_sl && currentPrice > 0) {
      const computed = Math.abs((currentPrice - signal.suggested_sl) / currentPrice) * 100
      if (computed > 0.5 && computed < 20) slPct = parseFloat(computed.toFixed(2))
    }
    if (signal?.suggested_tp && currentPrice > 0) {
      const computed = Math.abs((signal.suggested_tp - currentPrice) / currentPrice) * 100
      if (computed > 0.5 && computed < 200) tpPct = parseFloat(computed.toFixed(2))
    }

    try {
      if (isGtrade) {
        const payload = {
          symbol: gPair,
          direction,
          leverage: Number(leverage),
        }
        if (collateral) payload.collateral_usdc = Number(collateral)
        const res = await gtradeApi.openTrade(payload)
        showToast(`${direction.toUpperCase()} ${gPair} @ $${res.data.entry_price?.toFixed(2)} — close manually`, 'success')
      } else {
        const payload = {
          symbol: coin.symbol,
          direction,
          leverage: Number(leverage),
          sl_percent: slPct,
          tp_percent: tpPct,
        }
        if (collateral) payload.usdt_amount = Number(collateral)
        const res = await bybitFuturesApi.openTrade(payload)
        showToast(`${direction.toUpperCase()} ${coin.symbol} @ $${res.data.entry_price?.toFixed?.(4) ?? res.data.entry_price} | SL ${slPct}% [Bybit]`, 'success')
      }
      setAltcoinModal(null)
      await fetchAll()
    } catch (e) {
      showToast(e.response?.data?.detail || 'Trade failed', 'error')
    } finally {
      setModalTradeLoading(false)
    }
  }

  const selectedPair = pairs.find(p => p.symbol === selectedSymbol)
  const totalPnl = positions.reduce((s, p) => s + (p.pnl_usd || 0), 0)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw size={20} className="text-teal-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      {/* Altcoin Trade Modal */}
      {altcoinModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setAltcoinModal(null)}>
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-lg font-bold text-white font-mono">{altcoinModal.coin.symbol.replace('USDT', '')}/USDT</h3>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-sm text-zinc-300">${Number(altcoinModal.coin.price).toLocaleString(undefined, { maximumSignificantDigits: 5 })}</span>
                  <span className={clsx('text-xs font-medium', altcoinModal.coin.change_24h > 0 ? 'text-emerald-400' : 'text-red-400')}>
                    {altcoinModal.coin.change_24h > 0 ? '+' : ''}{altcoinModal.coin.change_24h.toFixed(2)}%
                  </span>
                </div>
              </div>
              <button onClick={() => setAltcoinModal(null)} className="text-zinc-500 hover:text-white transition-colors">
                <X size={20} />
              </button>
            </div>

            {/* AI Signal */}
            <div className="bg-zinc-800/50 rounded-xl p-4 mb-5 space-y-2">
              {altcoinModal.signalLoading ? (
                <div className="flex items-center gap-2 text-zinc-500 text-xs"><RefreshCw size={12} className="animate-spin" /> Fetching AI signal…</div>
              ) : altcoinModal.signal ? (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">AI Signal</span>
                    <SignalBadge action={altcoinModal.signal.recommended_action} />
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="text-center">
                      <p className="text-zinc-500">Entry</p>
                      <p className="text-white font-mono">${altcoinModal.signal.suggested_entry ? Number(altcoinModal.signal.suggested_entry).toLocaleString(undefined, {maximumSignificantDigits: 5}) : '—'}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-zinc-500">Stop Loss</p>
                      <p className="text-red-400 font-mono">${altcoinModal.signal.suggested_sl ? Number(altcoinModal.signal.suggested_sl).toLocaleString(undefined, {maximumSignificantDigits: 5}) : '—'}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-zinc-500">Take Profit</p>
                      <p className="text-emerald-400 font-mono">${altcoinModal.signal.suggested_tp ? Number(altcoinModal.signal.suggested_tp).toLocaleString(undefined, {maximumSignificantDigits: 5}) : '—'}</p>
                    </div>
                  </div>
                  {altcoinModal.signal.confidence != null && (
                    <p className="text-[10px] text-zinc-600 text-center">Confidence: {(altcoinModal.signal.confidence * 100).toFixed(0)}%</p>
                  )}
                </>
              ) : (
                <p className="text-xs text-zinc-600">No AI signal cached. Run a scan first.</p>
              )}
            </div>

            {/* Venue tag */}
            <div className="flex items-center justify-center mb-3">
              {altcoinModal.isGtrade ? (
                <span className="px-2 py-0.5 rounded bg-teal-500/15 border border-teal-500/25 text-teal-400 text-[10px] font-bold">Via gTrade · Arbitrum DeFi · MetaMask USDC</span>
              ) : (
                <span className="px-2 py-0.5 rounded bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-[10px] font-bold">Via Bybit Futures · {leverage}x · CEX USDT/USDC</span>
              )}
            </div>

            {/* Bybit balance + deposit section (non-gTrade only) */}
            {!altcoinModal.isGtrade && (
              <div className="mb-3 space-y-2">
                {/* Balance indicator */}
                <div className="flex items-center justify-between bg-zinc-800/60 rounded-lg px-3 py-2 text-xs">
                  <span className="text-zinc-500">Bybit Balance</span>
                  {bybitBalance === null ? (
                    <span className="text-zinc-600 flex items-center gap-1"><RefreshCw size={10} className="animate-spin" /> loading…</span>
                  ) : (
                    <span className={clsx('font-semibold', bybitBalance.total > 0 ? 'text-emerald-400' : 'text-red-400')}>
                      ${bybitBalance.total.toFixed(2)} {bybitBalance.usdc > bybitBalance.usdt ? 'USDC' : 'USDT'}
                    </span>
                  )}
                </div>

                {/* Deposit section — show when balance empty */}
                {bybitBalance !== null && bybitBalance.total < 1 && (
                  <div className="bg-amber-500/10 border border-amber-500/25 rounded-xl p-3 space-y-2">
                    <p className="text-xs text-amber-300 font-semibold">Bybit balance $0 — deposit USDC dulu</p>
                    <ol className="text-[10px] text-zinc-400 space-y-0.5 list-decimal list-inside">
                      <li>Copy deposit address Bybit (Arbitrum One)</li>
                      <li>MetaMask → kirim USDC ke address itu</li>
                      <li>Tunggu 5–30 menit, cek Bybit → Assets</li>
                      <li>Bybit: Transfer ke Unified Trading</li>
                    </ol>

                    {!bybitDepositAddr ? (
                      <button
                        onClick={handleGetDepositAddress}
                        disabled={depositLoading}
                        className="w-full py-1.5 text-[10px] font-semibold bg-amber-500/20 border border-amber-500/30 rounded-lg text-amber-300 hover:bg-amber-500/30 disabled:opacity-50 transition-colors"
                      >
                        {depositLoading ? 'Fetching…' : 'Lihat Deposit Address USDC (Arbitrum)'}
                      </button>
                    ) : (
                      <div className="space-y-1">
                        <p className="text-[10px] text-zinc-500">Deposit Address · {bybitDepositAddr.network_name}</p>
                        <div className="flex items-center gap-2 bg-zinc-900 rounded-lg px-2 py-1.5 border border-zinc-700">
                          <span className="text-[10px] font-mono text-white flex-1 truncate">
                            {bybitDepositAddr.address || 'Address not available'}
                          </span>
                          {bybitDepositAddr.address && (
                            <button
                              onClick={() => handleCopyAddress(bybitDepositAddr.address)}
                              className="text-[10px] px-2 py-0.5 bg-zinc-700 rounded text-zinc-300 hover:bg-zinc-600 shrink-0"
                            >
                              {copied ? '✓' : 'Copy'}
                            </button>
                          )}
                        </div>
                        <p className="text-[9px] text-red-400">⚠️ Pastikan pilih network Arbitrum One saat kirim!</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <p className="text-[10px] text-zinc-500 mb-3 text-center">SL/TP dari AI signal. Leverage & collateral dari form settings.</p>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleModalTrade('long')}
                disabled={modalTradeLoading || (altcoinModal.isGtrade && !status?.gtrade_enabled) || (!altcoinModal.isGtrade && bybitBalance !== null && bybitBalance.total < 1)}
                className="flex items-center justify-center gap-2 py-3 bg-emerald-500/10 border border-emerald-500/25 rounded-xl text-emerald-400 text-sm font-semibold hover:bg-emerald-500/20 transition-all disabled:opacity-50"
              >
                <TrendingUp size={15} /> LONG
              </button>
              <button
                onClick={() => handleModalTrade('short')}
                disabled={modalTradeLoading || (altcoinModal.isGtrade && !status?.gtrade_enabled) || (!altcoinModal.isGtrade && bybitBalance !== null && bybitBalance.total < 1)}
                className="flex items-center justify-center gap-2 py-3 bg-red-500/10 border border-red-500/25 rounded-xl text-red-400 text-sm font-semibold hover:bg-red-500/20 transition-all disabled:opacity-50"
              >
                <TrendingDown size={15} /> SHORT
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={clsx(
          'fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border text-sm shadow-xl',
          toast.type === 'success'
            ? 'bg-emerald-950 border-emerald-500/30 text-emerald-300'
            : 'bg-red-950 border-red-500/30 text-red-300'
        )}>
          {toast.type === 'success'
            ? <CheckCircle size={16} className="text-emerald-400 shrink-0" />
            : <AlertCircle size={16} className="text-red-400 shrink-0" />}
          <span className="max-w-xs">{toast.msg}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-teal-500/15 border border-teal-500/25 rounded-xl flex items-center justify-center">
            <Triangle size={18} className="text-teal-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">gTrade Futures</h1>
            <p className="text-xs text-zinc-500">Gains Network · Arbitrum · Low fees</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {status && (
            <div className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium',
              status.gtrade_enabled
                ? 'bg-teal-500/10 border-teal-500/25 text-teal-300'
                : 'bg-zinc-800 border-zinc-700 text-zinc-500'
            )}>
              <span className={clsx('w-1.5 h-1.5 rounded-full', status.gtrade_enabled ? 'bg-teal-400' : 'bg-zinc-600')} />
              {status.gtrade_enabled ? 'Active' : 'Disabled'}
            </div>
          )}
          <button
            onClick={fetchAll}
            className="p-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* Wallet info */}
      {status?.wallet_address && (
        <div className="flex items-center gap-2 text-xs text-zinc-500 bg-zinc-900 border border-zinc-800/60 rounded-lg px-3 py-2 w-fit">
          <Wallet size={12} className="text-teal-400" />
          <span className="font-mono">{status.wallet_address.slice(0, 6)}...{status.wallet_address.slice(-4)}</span>
        </div>
      )}

      {/* gTrade 2-step close warning — always visible */}
      <div className="bg-amber-500/10 border border-amber-500/25 rounded-xl px-4 py-3 flex items-start gap-3 text-amber-300 text-xs">
        <AlertCircle size={14} className="shrink-0 mt-0.5" />
        <span>
          <strong>gTrade 2-step close:</strong> Klik "Close" hanya submit permintaan ke smart contract.
          USDC masuk ke wallet MetaMask kamu setelah <strong>keeper gTrade execute</strong> (~1–5 menit).
          Jangan panik jika belum masuk — cek Arbiscan untuk konfirmasi.
        </span>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-center gap-3 text-red-400 text-sm">
          <AlertCircle size={16} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Open Positions"
          value={positions.length}
          sub="active trades"
          icon={Activity}
          color="bg-teal-500/20"
        />
        <StatCard
          label="Total PnL"
          value={`${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)} USDC`}
          sub="unrealized"
          icon={DollarSign}
          color={totalPnl >= 0 ? 'bg-emerald-500/20' : 'bg-red-500/20'}
        />
        <StatCard
          label="Default Leverage"
          value={`${status?.leverage || 2}x`}
          sub="bot setting"
          icon={TrendingUp}
          color="bg-blue-500/20"
        />
        <StatCard
          label="Execution Fee"
          value="~$0.01–0.05"
          sub="Arbitrum gas only"
          icon={Activity}
          color="bg-emerald-500/20"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left: positions + pairs */}
        <div className="xl:col-span-2 space-y-6">
          {/* Open positions */}
          <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-zinc-800/60 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Open Positions</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-zinc-500">{positions.length} active</span>
                <button
                  onClick={handleForceCloseAll}
                  disabled={actionLoading}
                  title="Fetch real positions from gTrade API and close all"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 border border-red-500/25 rounded-lg text-red-400 text-[11px] font-semibold hover:bg-red-500/20 transition-all disabled:opacity-50"
                >
                  <X size={12} />
                  Force Close All
                </button>
              </div>
            </div>
            {positions.length === 0 ? (
              <div className="px-5 py-8 text-center text-zinc-600 text-sm">No open positions</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800/60">
                      {['Symbol', 'Dir', 'Entry', 'Current', 'TP', 'SL', 'Size', 'PnL', 'Action'].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-zinc-500 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos) => (
                      <tr key={pos.symbol} className="border-b border-zinc-800/40 hover:bg-zinc-800/20 transition-colors">
                        <td className="px-4 py-3 font-mono font-semibold text-white">{pos.symbol}</td>
                        <td className="px-4 py-3"><DirectionBadge direction={pos.direction} /></td>
                        <td className="px-4 py-3 text-zinc-300">${pos.entry_price?.toFixed(2)}</td>
                        <td className="px-4 py-3 text-zinc-300">
                          {pos.current_price ? `$${pos.current_price?.toFixed(2)}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-emerald-500 text-xs">
                          {pos.tp_price ? `$${Number(pos.tp_price).toFixed(2)}` : <span className="text-zinc-600">—</span>}
                        </td>
                        <td className="px-4 py-3 text-red-500 text-xs">
                          {pos.sl_price ? `$${Number(pos.sl_price).toFixed(2)}` : <span className="text-zinc-600">—</span>}
                        </td>
                        <td className="px-4 py-3 text-zinc-400">${pos.size_usd?.toFixed(2)}</td>
                        <td className="px-4 py-3">
                          <PnlBadge pnl={pos.pnl_usd} pct={pos.pnl_percent} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={() => handleApplyAiTpsl(pos.symbol)}
                              disabled={actionLoading}
                              title="Update TP/SL from AI analysis"
                              className="p-1.5 bg-violet-500/10 border border-violet-500/25 rounded-lg text-violet-400 hover:bg-violet-500/20 transition-all disabled:opacity-50"
                            >
                              <Sparkles size={12} />
                            </button>
                            <button
                              onClick={() => handleClose(pos.symbol)}
                              disabled={actionLoading}
                              className={clsx(
                                'px-3 py-1.5 rounded-lg text-[11px] font-semibold border transition-all',
                                pos.pnl_usd >= 0
                                  ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/20'
                                  : 'bg-red-500/10 border-red-500/25 text-red-400 hover:bg-red-500/20',
                                'disabled:opacity-50 disabled:cursor-not-allowed'
                              )}
                            >
                              TP/Close
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Pairs table */}
          <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-zinc-800/60 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Available Pairs</h2>
              <div className="flex gap-1 bg-zinc-800 rounded-lg p-1">
                <button
                  onClick={() => setPairsTab('gtrade')}
                  className={clsx(
                    'px-3 py-1 text-xs font-medium rounded-md transition-colors',
                    pairsTab === 'gtrade' ? 'bg-teal-600 text-white' : 'text-zinc-400 hover:text-white'
                  )}
                >
                  gTrade Pairs
                </button>
                <button
                  onClick={() => setPairsTab('altcoins')}
                  className={clsx(
                    'px-3 py-1 text-xs font-medium rounded-md transition-colors',
                    pairsTab === 'altcoins' ? 'bg-indigo-600 text-white' : 'text-zinc-400 hover:text-white'
                  )}
                >
                  Altcoin Scanner
                </button>
              </div>
            </div>

            {pairsTab === 'gtrade' && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800/60">
                      {['Pair', 'Price', '24h %', 'AI Signal', 'Conf', 'Max Lev', ''].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-zinc-500 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pairs.map((pair) => (
                      <tr
                        key={pair.symbol}
                        onClick={() => setSelectedSymbol(pair.symbol)}
                        className={clsx(
                          'border-b border-zinc-800/40 cursor-pointer transition-colors',
                          selectedSymbol === pair.symbol
                            ? 'bg-teal-500/5 border-l-2 border-l-teal-500'
                            : 'hover:bg-zinc-800/20'
                        )}
                      >
                        <td className="px-4 py-3 font-mono font-semibold text-white">{pair.symbol}</td>
                        <td className="px-4 py-3 text-zinc-300">
                          {pair.price ? `$${Number(pair.price).toLocaleString()}` : '—'}
                        </td>
                        <td className={clsx(
                          'px-4 py-3 font-medium',
                          pair.change_24h > 0 ? 'text-emerald-400' : pair.change_24h < 0 ? 'text-red-400' : 'text-zinc-500'
                        )}>
                          {pair.change_24h != null ? `${pair.change_24h > 0 ? '+' : ''}${pair.change_24h?.toFixed(2)}%` : '—'}
                        </td>
                        <td className="px-4 py-3"><SignalBadge action={pair.signal?.action} /></td>
                        <td className="px-4 py-3 text-zinc-400">
                          {pair.signal?.confidence != null
                            ? `${(pair.signal.confidence * 100).toFixed(0)}%`
                            : '—'}
                        </td>
                        <td className="px-4 py-3 text-zinc-400">{pair.max_leverage}x</td>
                        <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleTrade('long', pair.symbol)}
                              disabled={actionLoading}
                              className="px-2 py-1 bg-emerald-500/10 border border-emerald-500/25 rounded text-emerald-400 text-[10px] font-bold hover:bg-emerald-500/20 transition-all disabled:opacity-40"
                            >
                              L
                            </button>
                            <button
                              onClick={() => handleTrade('short', pair.symbol)}
                              disabled={actionLoading}
                              className="px-2 py-1 bg-red-500/10 border border-red-500/25 rounded text-red-400 text-[10px] font-bold hover:bg-red-500/20 transition-all disabled:opacity-40"
                            >
                              S
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {pairsTab === 'altcoins' && (
              <div className="overflow-x-auto">
                {altcoinLoading ? (
                  <div className="py-10 text-center text-zinc-500 text-xs flex items-center justify-center gap-2">
                    <RefreshCw size={14} className="animate-spin" /> Scanning altcoins…
                  </div>
                ) : altcoinError ? (
                  <div className="py-6 px-4 flex items-center gap-2 text-red-400 text-xs">
                    <AlertCircle size={14} className="shrink-0" />
                    <span>{altcoinError}</span>
                  </div>
                ) : altcoins.length === 0 ? (
                  <div className="py-10 text-center text-zinc-600 text-xs">No data. Try refreshing.</div>
                ) : (
                  <>
                    <div className="px-4 py-2 bg-zinc-800/40 border-b border-zinc-800/60">
                      <p className="text-[10px] text-zinc-500">
                        Top {altcoins.length} altcoin movers · Excludes BTC/ETH/BNB/SOL/XRP · Read-only info
                      </p>
                    </div>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-zinc-800/60">
                          {['#', 'Symbol', 'Price', '24h %', 'Volume', 'Signal'].map(h => (
                            <th key={h} className="px-4 py-3 text-left text-zinc-500 font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {altcoins.map((coin, i) => (
                          <tr
                            key={coin.symbol}
                            onClick={() => handleAltcoinClick(coin)}
                            className="border-b border-zinc-800/40 hover:bg-indigo-500/5 cursor-pointer transition-colors"
                          >
                            <td className="px-4 py-3 text-zinc-600">{i + 1}</td>
                            <td className="px-4 py-3 font-mono font-semibold text-white">
                              {coin.symbol.replace('USDT', '')}
                              <span className="text-zinc-600">/USDT</span>
                            </td>
                            <td className="px-4 py-3 text-zinc-300">
                              ${Number(coin.price).toLocaleString(undefined, { maximumSignificantDigits: 5 })}
                            </td>
                            <td className={clsx(
                              'px-4 py-3 font-medium',
                              coin.change_24h > 0 ? 'text-emerald-400' : coin.change_24h < 0 ? 'text-red-400' : 'text-zinc-500'
                            )}>
                              {coin.change_24h > 0 ? '+' : ''}{coin.change_24h.toFixed(2)}%
                            </td>
                            <td className="px-4 py-3 text-zinc-500">
                              ${(coin.turnover_24h / 1_000_000).toFixed(1)}M
                            </td>
                            <td className="px-4 py-3">
                              <SignalBadge action={coin.recommended_action} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="px-4 py-2 border-t border-zinc-800/60 flex justify-end">
                      <button
                        onClick={fetchAltcoins}
                        disabled={altcoinLoading}
                        className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                      >
                        <RefreshCw size={11} className={clsx(altcoinLoading && 'animate-spin')} />
                        Refresh
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: trade panel + logs */}
        <div className="space-y-4">
          {/* Trade panel */}
          <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-white">Open Trade</h2>

            {/* Symbol selector */}
            <div className="space-y-1">
              <label className="text-xs text-zinc-500">Pair</label>
              <div className="relative">
                <select
                  value={selectedSymbol}
                  onChange={e => setSelectedSymbol(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-white appearance-none pr-8 focus:outline-none focus:border-teal-500"
                >
                  {(pairs.length > 0 ? pairs.map(p => p.symbol) : PAIRS_LIST).map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-3 text-zinc-500 pointer-events-none" />
              </div>
            </div>

            {/* Current price */}
            {selectedPair?.price && (
              <div className="flex items-center justify-between bg-zinc-800/50 rounded-lg px-3 py-2">
                <span className="text-xs text-zinc-500">Current price</span>
                <span className="text-sm font-semibold text-teal-400">
                  ${Number(selectedPair.price).toLocaleString()}
                </span>
              </div>
            )}

            {/* Signal info */}
            {selectedPair?.signal?.action && selectedPair.signal.action !== 'HOLD' && (
              <div className="bg-zinc-800/30 rounded-lg px-3 py-2 flex items-center justify-between">
                <span className="text-xs text-zinc-500">AI Signal</span>
                <SignalBadge action={selectedPair.signal.action} />
              </div>
            )}

            {/* Collateral input */}
            <div className="space-y-1">
              <label className="text-xs text-zinc-500">Collateral USDC (optional)</label>
              <div className="relative">
                <span className="absolute left-3 top-2.5 text-zinc-500 text-xs">$</span>
                <input
                  type="number"
                  placeholder="Auto from settings"
                  value={collateral}
                  onChange={e => setCollateral(e.target.value)}
                  min="1.5"
                  step="1"
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 pl-6 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-teal-500"
                />
              </div>
              <p className="text-[10px] text-zinc-600">Min $1.50 · No ETH fee needed</p>
            </div>

            {/* Leverage slider */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="text-xs text-zinc-500">Leverage</label>
                <span className="text-sm font-bold text-teal-400">{leverage}x</span>
              </div>
              <input
                type="range"
                min="2"
                max="150"
                step="1"
                value={leverage}
                onChange={e => setLeverage(Number(e.target.value))}
                className="w-full accent-teal-500"
              />
              <div className="flex justify-between text-[10px] text-zinc-600">
                <span>2x</span><span>50x</span><span>100x</span><span>150x</span>
              </div>
            </div>

            {/* TP / SL */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-zinc-500">Take Profit %</label>
                <div className="relative">
                  <input
                    type="number"
                    placeholder="e.g. 10"
                    value={tpPercent}
                    onChange={e => setTpPercent(e.target.value)}
                    min="0.5"
                    step="0.5"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                {tpPercent && selectedPair?.price && (
                  <p className="text-[10px] text-emerald-500">
                    @ ${(Number(selectedPair.price) * (1 + Number(tpPercent) / 100)).toFixed(2)}
                  </p>
                )}
              </div>
              <div className="space-y-1">
                <label className="text-xs text-zinc-500">Stop Loss %</label>
                <div className="relative">
                  <input
                    type="number"
                    placeholder="e.g. 3"
                    value={slPercent}
                    onChange={e => setSlPercent(e.target.value)}
                    min="0.5"
                    step="0.5"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-red-500"
                  />
                </div>
                {slPercent && selectedPair?.price && (
                  <p className="text-[10px] text-red-500">
                    @ ${(Number(selectedPair.price) * (1 - Number(slPercent) / 100)).toFixed(2)}
                  </p>
                )}
              </div>
            </div>
            <p className="text-[10px] text-amber-600">TP/SL tidak dipakai — close manual saja. USDC tiba 1-5 menit setelah kamu klik close (keeper gTrade).</p>

            {/* Size preview */}
            {collateral && (
              <div className="bg-teal-500/5 border border-teal-500/15 rounded-lg px-3 py-2">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Position size</span>
                  <span className="text-teal-400 font-semibold">
                    ${(Number(collateral) * leverage).toFixed(2)} USDC
                  </span>
                </div>
              </div>
            )}

            {/* Long / Short buttons */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <button
                onClick={() => handleTrade('long')}
                disabled={actionLoading}
                className="flex items-center justify-center gap-2 py-3 bg-emerald-500/10 border border-emerald-500/25 rounded-xl text-emerald-400 text-sm font-semibold hover:bg-emerald-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <TrendingUp size={15} />
                LONG
              </button>
              <button
                onClick={() => handleTrade('short')}
                disabled={actionLoading}
                className="flex items-center justify-center gap-2 py-3 bg-red-500/10 border border-red-500/25 rounded-xl text-red-400 text-sm font-semibold hover:bg-red-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <TrendingDown size={15} />
                SHORT
              </button>
            </div>

            {!status?.gtrade_enabled && (
              <div className="flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2 text-yellow-400 text-xs">
                <AlertCircle size={13} />
                Enable gTrade in Bot Settings first
              </div>
            )}
          </div>

          {/* Activity log */}
          <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-zinc-800/60">
              <h2 className="text-sm font-semibold text-white">Activity Log</h2>
            </div>
            <div className="max-h-80 overflow-y-auto">
              {logs.length === 0 ? (
                <div className="px-5 py-6 text-center text-zinc-600 text-xs">No activity yet</div>
              ) : (
                <div className="divide-y divide-zinc-800/40">
                  {logs.map((log, i) => (
                    <div key={i} className="px-4 py-3 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={clsx(
                            'px-1.5 py-0.5 rounded text-[10px] font-bold',
                            log.event === 'OPENED' ? 'bg-teal-500/20 text-teal-300' : 'bg-zinc-700 text-zinc-300'
                          )}>
                            {log.event}
                          </span>
                          <span className="font-mono font-semibold text-white">{log.symbol}</span>
                          {log.direction && (
                            <span className={log.direction === 'LONG' ? 'text-emerald-400' : 'text-red-400'}>
                              {log.direction}
                            </span>
                          )}
                        </div>
                        <span className="text-zinc-600">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="flex gap-4 text-zinc-500">
                        {log.entry_price && <span>Entry: ${log.entry_price?.toFixed(2)}</span>}
                        {log.exit_price && <span>Exit: ${log.exit_price?.toFixed(2)}</span>}
                        {log.size_usd != null && <span>Size: ${log.size_usd?.toFixed(2)}</span>}
                        {log.pnl_usd != null && (
                          <span className={log.pnl_usd >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                            PnL: {log.pnl_usd >= 0 ? '+' : ''}{log.pnl_usd?.toFixed(2)}
                          </span>
                        )}
                      </div>
                      {log.tx_hash && (
                        <a
                          href={`https://arbiscan.io/tx/${log.tx_hash}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-500 hover:text-indigo-300 font-mono text-[10px] underline"
                        >
                          Tx: {log.tx_hash.slice(0, 16)}… ↗
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
