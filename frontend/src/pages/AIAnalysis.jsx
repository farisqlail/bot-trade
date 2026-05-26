import { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import { aiApi } from '../services/api'

const ACTION_STYLES = {
  BUY: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30',
  SELL: 'text-red-300 bg-red-500/10 border-red-500/30',
  HOLD: 'text-amber-300 bg-amber-500/10 border-amber-500/30',
}

const POLL_INTERVAL = 60

function StatCard({ label, value, hint, valueClassName = 'text-white' }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-gray-500">{label}</p>
      <p className={clsx('mt-2 text-2xl font-semibold', valueClassName)}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-gray-500">{hint}</p> : null}
    </div>
  )
}

export default function AIAnalysis() {
  const [opportunities, setOpportunities] = useState([])
  const [loading, setLoading] = useState(true)
  const [runningScan, setRunningScan] = useState(false)
  const [autoPaper, setAutoPaper] = useState(false)
  const [lastRun, setLastRun] = useState(null)
  const [countdown, setCountdown] = useState(POLL_INTERVAL)
  const prevOpportunities = useRef([])
  const countdownRef = useRef(POLL_INTERVAL)

  const pushNotifications = (newData) => {
    if (Notification.permission !== 'granted' || !prevOpportunities.current.length) return
    newData.forEach((item) => {
      const prev = prevOpportunities.current.find((o) => o.symbol === item.symbol)
      if (
        item.recommended_action !== 'HOLD' &&
        (!prev || prev.recommended_action !== item.recommended_action)
      ) {
        new Notification(`${item.symbol}: ${item.recommended_action}`, {
          body: `Entry $${Number(item.suggested_entry).toLocaleString()} · Confidence ${(item.confidence * 100).toFixed(0)}%`,
        })
      }
    })
  }

  const applyOpportunities = (data, notify = false) => {
    if (notify) pushNotifications(data)
    prevOpportunities.current = data
    setOpportunities(data)
    setLastRun(new Date())
  }

  const loadCached = useCallback(async (notify = false) => {
    try {
      const res = await aiApi.getCachedOpportunities()
      applyOpportunities(res.data, notify)
      return res.data.length
    } catch {
      return 0
    }
  }, [])

  const runScan = useCallback(async (executePaper = false) => {
    setRunningScan(true)
    try {
      const res = await aiApi.scanOpportunities({ deep_analysis: true, execute_paper: executePaper })
      applyOpportunities(res.data, false)
    } catch (e) {
      alert(e.response?.data?.detail || e.response?.data?.error || 'Scan failed')
    } finally {
      setRunningScan(false)
      setLoading(false)
    }
  }, [])

  // Initial load: try cache first, fall back to full scan if empty
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
    loadCached(false).then((count) => {
      if (count === 0) runScan(false)
      else setLoading(false)
    })
  }, [loadCached, runScan])

  // Auto-poll cached endpoint every 60s + countdown tick
  useEffect(() => {
    const pollId = setInterval(() => {
      loadCached(true)
      countdownRef.current = POLL_INTERVAL
      setCountdown(POLL_INTERVAL)
    }, POLL_INTERVAL * 1000)

    const tickId = setInterval(() => {
      countdownRef.current = Math.max(0, countdownRef.current - 1)
      setCountdown(countdownRef.current)
    }, 1000)

    return () => {
      clearInterval(pollId)
      clearInterval(tickId)
    }
  }, [loadCached])

  const buyCount = opportunities.filter((i) => i.recommended_action === 'BUY').length
  const sellCount = opportunities.filter((i) => i.recommended_action === 'SELL').length
  const avgConfidence = opportunities.length
    ? `${Math.round(
        (opportunities.reduce((s, i) => s + (i.confidence || 0), 0) / opportunities.length) * 100,
      )}%`
    : '0%'

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-cyan-400">Scanner</p>
          <h2 className="mt-2 text-3xl font-bold text-white">
            Polymarket sentiment + Bybit paper trading
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-gray-400">
            Bot scan coin dari watchlist, baca momentum harga Bybit, gabung sentimen Polymarket,
            lalu bisa buka trade dummy pakai harga real.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="text-right text-xs text-gray-500">
            <span className="block">Scan otomatis tiap 5 menit</span>
            <span className="text-cyan-400">Refresh data dalam {countdown}s</span>
          </div>

          <label className="flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-300">
            <input
              type="checkbox"
              checked={autoPaper}
              onChange={(e) => setAutoPaper(e.target.checked)}
              className="h-4 w-4 rounded border-gray-600 bg-gray-800 text-cyan-500"
            />
            Auto buka dummy trade
          </label>

          <button
            onClick={() => runScan(autoPaper)}
            disabled={runningScan}
            className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-gray-950 transition-colors hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runningScan ? 'Scanning...' : 'Scan Manual'}
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Coins Scanned"
          value={String(opportunities.length)}
          hint="Watchlist dari bot settings"
        />
        <StatCard
          label="Buy / Sell"
          value={`${buyCount} / ${sellCount}`}
          hint="Signal terkuat saat scan terakhir"
        />
        <StatCard
          label="Avg Confidence"
          value={avgConfidence}
          hint={lastRun ? `Last scan ${lastRun.toLocaleString()}` : 'Belum ada scan'}
          valueClassName="text-cyan-300"
        />
      </div>

      {loading ? (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-8 text-center text-gray-500">
          Loading scanner...
        </div>
      ) : opportunities.length ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {[...new Map(opportunities.map((o) => [o.symbol, o])).values()].map((item) => (
            <div key={item.symbol} className="rounded-2xl border border-gray-800 bg-gray-900 p-5">
              <div className="flex flex-col gap-3 border-b border-gray-800 pb-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-gray-500">Coin</p>
                  <h3 className="mt-1 text-2xl font-semibold text-white">{item.symbol}</h3>
                  <p className="mt-1 text-sm text-gray-400">
                    Confidence {(item.confidence * 100).toFixed(0)}% · Polymarket bias{' '}
                    {item.polymarket_bias_score}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={clsx(
                      'rounded-full border px-3 py-1 text-xs font-semibold',
                      ACTION_STYLES[item.recommended_action] ||
                        'border-gray-700 bg-gray-800 text-gray-300',
                    )}
                  >
                    {item.recommended_action}
                  </span>
                  <span className="rounded-full border border-gray-700 bg-gray-800 px-3 py-1 text-xs text-gray-300">
                    {item.trend}
                  </span>
                  <span className={clsx(
                    'rounded-full border px-3 py-1 text-xs font-medium',
                    item.model_name === 'heuristic'
                      ? 'border-gray-700 bg-gray-800/50 text-gray-500'
                      : 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
                  )}>
                    {item.model_name === 'heuristic' ? 'Heuristic' : 'AI'}
                  </span>
                  {item.paper_trade_id ? (
                    <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-300">
                      Paper Trade #{item.paper_trade_id}
                    </span>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl bg-gray-800/70 p-3">
                  <p className="text-xs text-gray-500">Price</p>
                  <p className="mt-1 text-lg font-semibold text-white">
                    ${Number(item.price_at_analysis || 0).toLocaleString()}
                  </p>
                </div>
                <div className="rounded-xl bg-gray-800/70 p-3">
                  <p className="text-xs text-gray-500">24H Change</p>
                  <p
                    className={clsx(
                      'mt-1 text-lg font-semibold',
                      item.change_24h >= 0 ? 'text-emerald-300' : 'text-red-300',
                    )}
                  >
                    {item.change_24h >= 0 ? '+' : ''}
                    {item.change_24h}%
                  </p>
                </div>
                <div className="rounded-xl bg-gray-800/70 p-3">
                  <p className="text-xs text-gray-500">Entry</p>
                  <p className="mt-1 text-lg font-semibold text-white">
                    ${Number(item.suggested_entry || 0).toLocaleString()}
                  </p>
                </div>
                <div className="rounded-xl bg-gray-800/70 p-3">
                  <p className="text-xs text-gray-500">Polymarket Matches</p>
                  <p className="mt-1 text-lg font-semibold text-cyan-300">
                    {item.polymarket_market_count}
                  </p>
                </div>
              </div>

              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3">
                  <p className="text-xs text-red-300">Stop Loss</p>
                  <p className="mt-1 text-base font-semibold text-white">
                    ${Number(item.suggested_sl || 0).toLocaleString()}
                  </p>
                </div>
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
                  <p className="text-xs text-emerald-300">Take Profit</p>
                  <p className="mt-1 text-base font-semibold text-white">
                    ${Number(item.suggested_tp || 0).toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-gray-800 bg-gray-950/60 p-4">
                <p className="text-xs uppercase tracking-[0.25em] text-gray-500">
                  {item.model_name === 'heuristic' ? 'Heuristic Analysis' : 'AI Analysis'}
                </p>
                <p className="mt-2 text-sm leading-6 text-gray-300">{item.analysis_text}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-8 text-center text-gray-500">
          Belum ada data scan. Klik "Scan Manual" atau tunggu scan otomatis tiap 5 menit.
        </div>
      )}
    </div>
  )
}
