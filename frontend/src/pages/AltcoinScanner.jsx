import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { RefreshCw, TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react'
import { aiApi } from '../services/api'

const ACTION_CONFIG = {
  STRONG_BUY:  { label: 'STRONG BUY',  color: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30' },
  BUY:         { label: 'BUY',          color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  HOLD:        { label: 'HOLD',         color: 'text-amber-300 bg-amber-500/10 border-amber-500/25' },
  SELL:        { label: 'SELL',         color: 'text-red-400 bg-red-500/10 border-red-500/20' },
  STRONG_SELL: { label: 'STRONG SELL',  color: 'text-red-300 bg-red-500/15 border-red-500/30' },
}

const FILTERS = ['ALL', 'BUY', 'SELL', 'HOLD']

function StatCard({ label, value, valueClass = 'text-white' }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
      <p className="text-xs uppercase tracking-widest text-gray-500">{label}</p>
      <p className={clsx('mt-2 text-2xl font-semibold', valueClass)}>{value}</p>
    </div>
  )
}

export default function AltcoinScanner() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [lastRun, setLastRun] = useState(null)
  const [minVolume, setMinVolume] = useState(500000)
  const [limit, setLimit] = useState(30)
  const navigate = useNavigate()

  const fetchAltcoins = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await aiApi.getAltcoins({
        limit,
        min_volume_usd: minVolume,
        action_filter: filter === 'ALL' ? undefined : filter,
      })
      setData(res.data)
      setLastRun(new Date())
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Request failed'
      setError(msg)
      console.error('Altcoin scan failed:', e)
    } finally {
      setLoading(false)
    }
  }, [filter, minVolume, limit])

  useEffect(() => { fetchAltcoins() }, [fetchAltcoins])

  const altcoins = data?.altcoins ?? []
  const scanned = data?.scanned ?? 0
  const buyCount = data?.buy_signals ?? 0
  const sellCount = data?.sell_signals ?? 0

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Altcoin Scanner</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Top movers — excludes BTC/ETH/BNB/SOL/XRP and other large caps
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRun && (
            <span className="text-xs text-gray-600">
              Updated {lastRun.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchAltcoins}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <RefreshCw size={14} className={clsx(loading && 'animate-spin')} />
            {loading ? 'Scanning…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/25 rounded-xl px-4 py-3 text-red-400 text-sm">
          <AlertCircle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Scanned" value={scanned} />
        <StatCard label="Showing" value={altcoins.length} />
        <StatCard label="Buy Signals" value={buyCount} valueClass="text-emerald-400" />
        <StatCard label="Sell Signals" value={sellCount} valueClass="text-red-400" />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                filter === f
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              {f}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>Min vol $</span>
          <select
            value={minVolume}
            onChange={(e) => setMinVolume(Number(e.target.value))}
            className="bg-gray-900 border border-gray-800 rounded-lg px-2 py-1.5 text-white text-xs"
          >
            <option value={100000}>100K</option>
            <option value={500000}>500K</option>
            <option value={1000000}>1M</option>
            <option value={5000000}>5M</option>
            <option value={10000000}>10M</option>
          </select>
        </div>

        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>Show</span>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-gray-900 border border-gray-800 rounded-lg px-2 py-1.5 text-white text-xs"
          >
            <option value={20}>20</option>
            <option value={30}>30</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      {loading && altcoins.length === 0 ? (
        <div className="text-center text-gray-500 py-20">Scanning Bybit…</div>
      ) : altcoins.length === 0 ? (
        <div className="text-center text-gray-500 py-20">No altcoins match filter.</div>
      ) : (
        <div className="rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/60">
                <th className="px-4 py-3 text-left text-xs text-gray-500 font-medium uppercase tracking-wider">#</th>
                <th className="px-4 py-3 text-left text-xs text-gray-500 font-medium uppercase tracking-wider">Symbol</th>
                <th className="px-4 py-3 text-right text-xs text-gray-500 font-medium uppercase tracking-wider">Price</th>
                <th className="px-4 py-3 text-right text-xs text-gray-500 font-medium uppercase tracking-wider">24h %</th>
                <th className="px-4 py-3 text-right text-xs text-gray-500 font-medium uppercase tracking-wider">Volume 24h</th>
                <th className="px-4 py-3 text-center text-xs text-gray-500 font-medium uppercase tracking-wider">Signal</th>
              </tr>
            </thead>
            <tbody>
              {altcoins.map((coin, i) => {
                const cfg = ACTION_CONFIG[coin.recommended_action] ?? ACTION_CONFIG.HOLD
                const isUp = coin.change_24h > 0
                const isDown = coin.change_24h < 0
                return (
                  <tr
                    key={coin.symbol}
                    onClick={() => navigate(`/chart?symbol=${coin.symbol}`)}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3 text-gray-600 text-xs">{i + 1}</td>
                    <td className="px-4 py-3">
                      <span className="font-semibold text-white">
                        {coin.symbol.replace('USDT', '')}
                      </span>
                      <span className="text-gray-600 text-xs">/USDT</span>
                    </td>
                    <td className="px-4 py-3 text-right text-white font-mono text-xs">
                      ${Number(coin.price).toLocaleString(undefined, { maximumSignificantDigits: 5 })}
                    </td>
                    <td className={clsx(
                      'px-4 py-3 text-right font-semibold font-mono text-xs flex items-center justify-end gap-1',
                      isUp ? 'text-emerald-400' : isDown ? 'text-red-400' : 'text-gray-400'
                    )}>
                      {isUp ? <TrendingUp size={12} /> : isDown ? <TrendingDown size={12} /> : <Minus size={12} />}
                      {isUp ? '+' : ''}{coin.change_24h.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right text-gray-400 font-mono text-xs">
                      ${(coin.turnover_24h / 1_000_000).toFixed(1)}M
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={clsx(
                        'inline-block px-2 py-0.5 rounded border text-xs font-medium',
                        cfg.color
                      )}>
                        {cfg.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
