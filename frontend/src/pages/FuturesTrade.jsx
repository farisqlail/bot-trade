import { useState, useEffect, useCallback } from 'react'
import { gmxApi } from '../services/api'
import {
  TrendingUp, TrendingDown, RefreshCw, AlertCircle, CheckCircle,
  Activity, DollarSign, Layers, ArrowUpRight, ArrowDownRight, Clock, X
} from 'lucide-react'
import clsx from 'clsx'

const MARKETS = ['ETHUSDT', 'ARBUSDT', 'LINKUSDT', 'SOLUSDT', 'AVAXUSDT', 'GMXUSDT', 'OPUSDT']

function fmt(n, dec = 2) {
  if (n == null) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' })
}

function PnlBadge({ value }) {
  if (value == null) return <span className="text-zinc-500">—</span>
  const pos = value >= 0
  return (
    <span className={clsx('font-semibold tabular-nums', pos ? 'text-emerald-400' : 'text-red-400')}>
      {pos ? '+' : ''}{fmt(value)}%
    </span>
  )
}

function DirectionBadge({ dir }) {
  const long = dir === 'LONG'
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold',
      long ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'
    )}>
      {long ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
      {dir}
    </span>
  )
}

function SignalBadge({ action, confidence }) {
  if (!action) return <span className="text-zinc-600 text-xs">—</span>
  const cfg = {
    STRONG_BUY:  { label: 'STRONG BUY',  cls: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
    BUY:         { label: 'BUY',          cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
    HOLD:        { label: 'HOLD',         cls: 'bg-zinc-700/40 text-zinc-400 border-zinc-600/30' },
    SELL:        { label: 'SELL',         cls: 'bg-red-500/10 text-red-400 border-red-500/20' },
    STRONG_SELL: { label: 'STRONG SELL',  cls: 'bg-red-500/20 text-red-300 border-red-500/30' },
  }
  const { label, cls } = cfg[action] || { label: action, cls: 'bg-zinc-700/40 text-zinc-400 border-zinc-600/30' }
  return (
    <span className={clsx('inline-flex flex-col items-start gap-0.5')}>
      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold border', cls)}>{label}</span>
      {confidence != null && (
        <span className="text-[10px] text-zinc-600">{Math.round(confidence * 100)}%</span>
      )}
    </span>
  )
}

function StatCard({ icon: Icon, label, value, sub, color = 'indigo' }) {
  const colors = {
    indigo: 'text-indigo-400 bg-indigo-500/10',
    emerald: 'text-emerald-400 bg-emerald-500/10',
    amber: 'text-amber-400 bg-amber-500/10',
    red: 'text-red-400 bg-red-500/10',
  }
  return (
    <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-4 flex items-start gap-3">
      <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', colors[color])}>
        <Icon size={16} />
      </div>
      <div>
        <p className="text-zinc-500 text-xs font-medium">{label}</p>
        <p className="text-white text-lg font-bold leading-tight mt-0.5">{value}</p>
        {sub && <p className="text-zinc-600 text-xs mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function FuturesTrade() {
  const [markets, setMarkets] = useState([])
  const [positions, setPositions] = useState([])
  const [logs, setLogs] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const [selectedSymbol, setSelectedSymbol] = useState('ETHUSDT')
  const [collateral, setCollateral] = useState('')
  const [leverage, setLeverage] = useState('')
  const [tradeLoading, setTradeLoading] = useState(false)
  const [tradeMsg, setTradeMsg] = useState(null)
  const [closingSymbol, setClosingSymbol] = useState(null) // which position is being closed

  const fetchAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)
    setError(null)
    try {
      const [mRes, pRes, lRes, sRes] = await Promise.all([
        gmxApi.getMarkets(),
        gmxApi.getPositions(),
        gmxApi.getLogs(),
        gmxApi.getStatus(),
      ])
      setMarkets(mRes.data.markets || [])
      setPositions(pRes.data.positions || [])
      setLogs(lRes.data.logs || [])
      setStatus(sRes.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load GMX data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(() => fetchAll(true), 15000)
    return () => clearInterval(id)
  }, [fetchAll])

  const selectedMarket = markets.find(m => m.symbol === selectedSymbol)

  async function handleTrade(direction) {
    setTradeMsg(null)
    setTradeLoading(true)
    try {
      const body = { symbol: selectedSymbol, direction }
      if (collateral) body.collateral_usdc = parseFloat(collateral)
      if (leverage) body.leverage = parseFloat(leverage)
      const res = await gmxApi.openTrade(body)
      setTradeMsg({
        ok: true,
        text: `✅ ${res.data.direction} ${res.data.symbol} opened — $${fmt(res.data.size_usd)} @ $${fmt(res.data.entry_price, 4)}`,
      })
      fetchAll(true)
    } catch (e) {
      setTradeMsg({ ok: false, text: e?.response?.data?.detail || 'Trade failed' })
    } finally {
      setTradeLoading(false)
    }
  }

  async function handleClose(symbol) {
    if (!window.confirm(`Close ${symbol} position? This submits a market close order on GMX.`)) return
    setClosingSymbol(symbol)
    try {
      const res = await gmxApi.closePosition(symbol)
      const d = res.data
      const pnl = d.pnl_usd != null
        ? ` | PnL: ${d.pnl_usd >= 0 ? '+' : ''}$${fmt(d.pnl_usd)} (${d.pnl_percent >= 0 ? '+' : ''}${fmt(d.pnl_percent)}%)`
        : ''
      alert(`✅ Closed ${symbol} @ $${fmt(d.exit_price, 4)}${pnl}`)
      fetchAll(true)
    } catch (e) {
      alert(`⚠️ Close failed: ${e?.response?.data?.detail || e.message}`)
    } finally {
      setClosingSymbol(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500">
        <RefreshCw size={18} className="animate-spin mr-2" /> Loading GMX data...
      </div>
    )
  }

  const totalCollateral = positions.reduce((s, p) => s + (p.collateral_usdc || 0), 0)
  const totalPnl = positions.reduce((s, p) => s + (p.pnl_usd || 0), 0)

  return (
    <div className="flex flex-col gap-5 p-6 min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Layers size={20} className="text-indigo-400" />
            Futures Trading <span className="text-zinc-500 text-sm font-normal ml-1">— GMX V2 Arbitrum</span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {status && (
            <span className={clsx(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium',
              status.gmx_enabled
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-red-500/10 text-red-400 border border-red-500/20'
            )}>
              {status.gmx_enabled ? <CheckCircle size={11} /> : <AlertCircle size={11} />}
              GMX {status.gmx_enabled ? 'Enabled' : 'Disabled'}
            </span>
          )}
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition-colors"
          >
            <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Layers} label="Open Positions" value={positions.length} color="indigo" />
        <StatCard icon={DollarSign} label="Total Collateral" value={`$${fmt(totalCollateral)}`} color="amber" />
        <StatCard
          icon={totalPnl >= 0 ? TrendingUp : TrendingDown}
          label="Unrealized PnL"
          value={`${totalPnl >= 0 ? '+' : ''}$${fmt(totalPnl)}`}
          color={totalPnl >= 0 ? 'emerald' : 'red'}
        />
        <StatCard
          icon={Activity}
          label="Leverage"
          value={status ? `${status.leverage}x` : '—'}
          sub={status ? `Collateral ${status.collateral_percent}%` : ''}
          color="indigo"
        />
      </div>

      {/* Main: positions + trade panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Positions table */}
        <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800/60 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-zinc-800/60 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
              <Activity size={14} className="text-indigo-400" /> Open Positions
            </h2>
            <span className="text-xs text-zinc-600">Auto-refreshes every 15s</span>
          </div>
          {positions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-zinc-600">
              <Layers size={28} className="mb-2" />
              <p className="text-sm">No open GMX positions</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800/40">
                    {['Symbol', 'Dir', 'Entry', 'Current', 'PnL', 'Size', 'Collateral', 'Lev', 'Opened', ''].map(h => (
                      <th key={h} className="text-left text-xs text-zinc-500 font-medium px-4 py-2.5">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos, i) => (
                    <tr key={i} className="border-b border-zinc-800/30 hover:bg-zinc-800/30 transition-colors">
                      <td className="px-4 py-3 font-semibold text-white">{pos.symbol}</td>
                      <td className="px-4 py-3"><DirectionBadge dir={pos.direction} /></td>
                      <td className="px-4 py-3 text-zinc-300 tabular-nums">${fmt(pos.entry_price, 4)}</td>
                      <td className="px-4 py-3 text-zinc-200 tabular-nums font-medium">
                        {pos.current_price != null ? `$${fmt(pos.current_price, 4)}` : <span className="text-zinc-600">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col">
                          <PnlBadge value={pos.pnl_percent} />
                          {pos.pnl_usd != null && (
                            <span className={clsx('text-xs tabular-nums', pos.pnl_usd >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                              {pos.pnl_usd >= 0 ? '+' : ''}${fmt(pos.pnl_usd)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-zinc-300 tabular-nums">${fmt(pos.size_usd)}</td>
                      <td className="px-4 py-3 text-zinc-400 tabular-nums">${fmt(pos.collateral_usdc)}</td>
                      <td className="px-4 py-3 text-zinc-400">{pos.leverage != null ? `${pos.leverage}x` : '—'}</td>
                      <td className="px-4 py-3 text-zinc-600 text-xs whitespace-nowrap">{fmtTime(pos.opened_at)}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleClose(pos.symbol)}
                          disabled={closingSymbol === pos.symbol}
                          className={clsx(
                            'flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-all',
                            pos.pnl_usd != null && pos.pnl_usd > 0
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20'
                              : 'bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/20',
                            'disabled:opacity-40 disabled:cursor-not-allowed'
                          )}
                          title="Close position (Take Profit / Stop Loss)"
                        >
                          {closingSymbol === pos.symbol
                            ? <RefreshCw size={10} className="animate-spin" />
                            : <X size={10} />
                          }
                          {pos.pnl_usd != null && pos.pnl_usd > 0 ? 'TP' : 'Close'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Trade panel */}
        <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-4 flex flex-col gap-4">
          <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
            <TrendingUp size={14} className="text-indigo-400" /> Open Position
          </h2>

          <div>
            <label className="text-xs text-zinc-500 font-medium mb-1.5 block">Market</label>
            <select
              value={selectedSymbol}
              onChange={e => setSelectedSymbol(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            >
              {MARKETS.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            {selectedMarket && (
              <div className="mt-2 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-500">Price</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-bold text-white tabular-nums">
                      ${selectedMarket.price != null ? fmt(selectedMarket.price, 4) : '—'}
                    </span>
                    {selectedMarket.change_24h != null && (
                      <span className={clsx('text-xs font-medium', selectedMarket.change_24h >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        {selectedMarket.change_24h >= 0 ? '+' : ''}{fmt(selectedMarket.change_24h)}%
                      </span>
                    )}
                  </div>
                </div>
                {selectedMarket.signal?.action && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">AI Signal</span>
                    <SignalBadge action={selectedMarket.signal.action} confidence={selectedMarket.signal.confidence} />
                  </div>
                )}
                {selectedMarket.signal?.suggested_tp && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">AI TP</span>
                    <span className="text-xs text-emerald-400 tabular-nums">${fmt(selectedMarket.signal.suggested_tp, 4)}</span>
                  </div>
                )}
                {selectedMarket.signal?.suggested_sl && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">AI SL</span>
                    <span className="text-xs text-red-400 tabular-nums">${fmt(selectedMarket.signal.suggested_sl, 4)}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          <div>
            <label className="text-xs text-zinc-500 font-medium mb-1.5 block">
              Collateral USDC <span className="text-zinc-600">(kosong = pakai settings %)</span>
            </label>
            <input
              type="number"
              value={collateral}
              onChange={e => setCollateral(e.target.value)}
              placeholder="e.g. 50"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="text-xs text-zinc-500 font-medium mb-1.5 block">
              Leverage <span className="text-zinc-600">(kosong = {status?.leverage ?? '—'}x dari settings)</span>
            </label>
            <input
              type="number"
              value={leverage}
              onChange={e => setLeverage(e.target.value)}
              placeholder={`default ${status?.leverage ?? 2}x`}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {status && !status.gmx_enabled && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2.5 text-xs text-amber-400 flex items-start gap-1.5">
              <AlertCircle size={13} className="mt-0.5 shrink-0" />
              GMX belum enabled. Aktifkan di Bot Settings.
            </div>
          )}
          {status && !status.wallet_configured && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 text-xs text-red-400 flex items-start gap-1.5">
              <AlertCircle size={13} className="mt-0.5 shrink-0" />
              Wallet belum dikonfigurasi.
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 mt-auto">
            <button
              onClick={() => handleTrade('long')}
              disabled={tradeLoading || !status?.gmx_enabled || !status?.wallet_configured}
              className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 font-bold text-sm border border-emerald-500/25 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ArrowUpRight size={15} /> LONG
            </button>
            <button
              onClick={() => handleTrade('short')}
              disabled={tradeLoading || !status?.gmx_enabled || !status?.wallet_configured}
              className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-red-500/15 hover:bg-red-500/25 text-red-400 font-bold text-sm border border-red-500/25 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ArrowDownRight size={15} /> SHORT
            </button>
          </div>

          {tradeLoading && (
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <RefreshCw size={11} className="animate-spin" /> Submitting to GMX...
            </div>
          )}

          {tradeMsg && (
            <div className={clsx(
              'rounded-lg p-2.5 text-xs border',
              tradeMsg.ok
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : 'bg-red-500/10 border-red-500/20 text-red-400'
            )}>
              {tradeMsg.text}
            </div>
          )}
        </div>
      </div>

      {/* Markets table with signal */}
      <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-zinc-800/60">
          <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
            <DollarSign size={14} className="text-indigo-400" /> GMX Markets
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800/40">
                {['Symbol', 'Price', '24h %', 'AI Signal', 'Confidence', 'AI TP', 'AI SL', '24h High', '24h Low', 'Volume'].map(h => (
                  <th key={h} className="text-left text-xs text-zinc-500 font-medium px-4 py-2.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {markets.map(m => (
                <tr
                  key={m.symbol}
                  onClick={() => setSelectedSymbol(m.symbol)}
                  className={clsx(
                    'border-b border-zinc-800/30 cursor-pointer transition-colors',
                    m.symbol === selectedSymbol ? 'bg-indigo-500/5' : 'hover:bg-zinc-800/30'
                  )}
                >
                  <td className="px-4 py-3 font-semibold text-white">
                    <div className="flex items-center gap-2">
                      {m.symbol === selectedSymbol && <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />}
                      {m.symbol}
                    </div>
                  </td>
                  <td className="px-4 py-3 tabular-nums font-medium text-zinc-200">
                    {m.price != null ? `$${fmt(m.price, 4)}` : '—'}
                  </td>
                  <td className="px-4 py-3 tabular-nums">
                    {m.change_24h != null ? (
                      <span className={m.change_24h >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {m.change_24h >= 0 ? '+' : ''}{fmt(m.change_24h)}%
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <SignalBadge action={m.signal?.action} confidence={null} />
                  </td>
                  <td className="px-4 py-3 text-zinc-400 text-xs tabular-nums">
                    {m.signal?.confidence != null ? `${Math.round(m.signal.confidence * 100)}%` : '—'}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-emerald-600 text-xs">
                    {m.signal?.suggested_tp ? `$${fmt(m.signal.suggested_tp, 4)}` : '—'}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-red-600 text-xs">
                    {m.signal?.suggested_sl ? `$${fmt(m.signal.suggested_sl, 4)}` : '—'}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-zinc-400">{m.high_24h != null ? `$${fmt(m.high_24h, 4)}` : '—'}</td>
                  <td className="px-4 py-3 tabular-nums text-zinc-400">{m.low_24h != null ? `$${fmt(m.low_24h, 4)}` : '—'}</td>
                  <td className="px-4 py-3 tabular-nums text-zinc-500">{m.volume_24h != null ? `$${(m.volume_24h / 1e6).toFixed(1)}M` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Activity Log */}
      <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-zinc-800/60 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
            <Clock size={14} className="text-indigo-400" /> Activity Log
          </h2>
          <span className="text-xs text-zinc-600">{logs.length} entries</span>
        </div>
        {logs.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-zinc-600 text-sm">
            No activity recorded yet
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/40 max-h-72 overflow-y-auto">
            {logs.map((log, i) => (
              <div key={i} className="px-4 py-3 flex items-start gap-3 hover:bg-zinc-800/20 transition-colors">
                <span className={clsx(
                  'mt-0.5 w-2 h-2 rounded-full shrink-0',
                  log.event === 'OPENED' ? 'bg-emerald-400' : log.event === 'CLOSED' ? 'bg-red-400' : 'bg-indigo-400'
                )} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-zinc-300">{log.event} {log.symbol}</span>
                    {log.direction && <DirectionBadge dir={log.direction} />}
                    {log.source && (
                      <span className="text-xs text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">via {log.source}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                    {log.entry_price != null && (
                      <span className="text-xs text-zinc-500">Entry <span className="text-zinc-300">${fmt(log.entry_price, 4)}</span></span>
                    )}
                    {log.exit_price != null && (
                      <span className="text-xs text-zinc-500">Exit <span className="text-zinc-300">${fmt(log.exit_price, 4)}</span></span>
                    )}
                    {log.size_usd != null && (
                      <span className="text-xs text-zinc-500">Size <span className="text-zinc-300">${fmt(log.size_usd)}</span></span>
                    )}
                    {log.pnl_usd != null && (
                      <span className={clsx('text-xs font-semibold tabular-nums', log.pnl_usd >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        PnL {log.pnl_usd >= 0 ? '+' : ''}${fmt(log.pnl_usd)} ({log.pnl_percent >= 0 ? '+' : ''}{fmt(log.pnl_percent)}%)
                      </span>
                    )}
                    {log.tx_hash && (
                      <span className="text-xs text-zinc-600 font-mono truncate max-w-[120px]">{log.tx_hash.slice(0, 12)}…</span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-zinc-600 whitespace-nowrap shrink-0">{fmtTime(log.timestamp)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
