import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Activity, RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import SmartChart from '../components/chart/SmartChart'
import AIAnalysisPanel from '../components/chart/AIAnalysisPanel'
import WatchlistRanking from '../components/chart/WatchlistRanking'
import ActiveTradeOverlay from '../components/chart/ActiveTradeOverlay'
import { useChartData } from '../hooks/useChartData'

const TIMEFRAMES = [
  { label: '1m', value: '1' },
  { label: '5m', value: '5' },
  { label: '15m', value: '15' },
  { label: '1H', value: '60' },
  { label: '4H', value: '240' },
  { label: '1D', value: 'D' },
]

const DEFAULT_SYMBOL = 'BTCUSDT'

export default function TradingChart() {
  const [searchParams] = useSearchParams()
  const [symbol, setSymbol] = useState(searchParams.get('symbol') || DEFAULT_SYMBOL)
  const [timeframe, setTimeframe] = useState('60')
  const { bundle, watchlist, loading, error, reload } = useChartData(symbol, timeframe)

  const latestCandle = bundle?.candles?.at(-1)
  const price = latestCandle?.close
  const prevPrice = bundle?.candles?.at(-2)?.close
  const priceUp = price != null && prevPrice != null ? price >= prevPrice : null

  return (
    <div
      className="-m-6 flex overflow-hidden bg-zinc-950"
      style={{ height: 'calc(100vh - 64px)' }}
    >
      {/* ── Left: Watchlist ───────────────────────── */}
      <aside className="w-48 shrink-0 flex flex-col border-r border-zinc-800/60">
        <div className="px-3 pt-3 pb-2 border-b border-zinc-800/60">
          <p className="text-[10px] uppercase tracking-widest text-zinc-600 font-semibold">Top Signals</p>
        </div>
        <div className="flex-1 overflow-y-auto py-1.5 px-1.5 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-zinc-800">
          <WatchlistRanking items={watchlist} selectedSymbol={symbol} onSelect={setSymbol} />
        </div>
      </aside>

      {/* ── Center: Chart ─────────────────────────── */}
      <section className="flex-1 flex flex-col min-w-0">
        {/* Chart toolbar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800/60 shrink-0">
          {/* Symbol + price */}
          <div className="flex items-baseline gap-2 min-w-0">
            <span className="text-sm font-bold text-zinc-100 shrink-0">
              {symbol.replace('USDT', '/USDT')}
            </span>
            {price != null && (
              <>
                <span
                  className={clsx(
                    'text-base font-mono font-semibold',
                    priceUp === true ? 'text-emerald-400' : priceUp === false ? 'text-red-400' : 'text-zinc-200'
                  )}
                >
                  ${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                </span>
                {bundle?.candles?.length > 1 && (
                  <span className={clsx('text-xs font-mono', priceUp ? 'text-emerald-500' : 'text-red-500')}>
                    {priceUp ? '▲' : '▼'}
                  </span>
                )}
              </>
            )}
          </div>

          {/* Timeframe selector */}
          <div className="flex gap-0.5 ml-auto bg-zinc-900 border border-zinc-800 rounded-lg p-0.5 shrink-0">
            {TIMEFRAMES.map(({ label, value }) => (
              <button
                key={value}
                onClick={() => setTimeframe(value)}
                className={clsx(
                  'px-2 py-0.5 text-xs font-medium rounded-md transition-all duration-150',
                  timeframe === value
                    ? 'bg-indigo-500 text-white shadow-sm'
                    : 'text-zinc-500 hover:text-zinc-200'
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Controls */}
          <button
            onClick={reload}
            disabled={loading}
            title="Refresh"
            className="p-1.5 rounded-lg text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-all shrink-0"
          >
            <RefreshCw size={13} className={clsx(loading && 'animate-spin')} />
          </button>

          <div className="flex items-center gap-1 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] text-zinc-600">Live</span>
          </div>

          {/* EMA legend */}
          <div className="hidden lg:flex items-center gap-3 ml-1 shrink-0">
            {[['EMA20', '#22d3ee'], ['EMA50', '#f59e0b'], ['EMA200', '#a855f7']].map(([lbl, col]) => (
              <div key={lbl} className="flex items-center gap-1">
                <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: col }} />
                <span className="text-[9px] text-zinc-600">{lbl}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Chart area */}
        <div className="flex-1 min-h-0 relative">
          {error && !bundle && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-5 py-3">
                {error}
              </div>
            </div>
          )}
          {loading && !bundle && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="flex flex-col items-center gap-2 text-zinc-600">
                <RefreshCw size={18} className="animate-spin" />
                <span className="text-sm">Loading chart…</span>
              </div>
            </div>
          )}
          {bundle && (
            <SmartChart
              candles={bundle.candles}
              signal={bundle.signal}
              activeTrade={bundle.active_trade}
              markers={bundle.signal_markers}
            />
          )}
        </div>

        {/* Active trade strip */}
        {bundle?.active_trade && (
          <div className="px-4 py-2.5 border-t border-zinc-800/60 shrink-0 bg-zinc-950/80">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={11} className="text-emerald-400" />
              <span className="text-[10px] uppercase tracking-widest text-zinc-600">Active Trade</span>
            </div>
            <ActiveTradeOverlay trade={bundle.active_trade} />
          </div>
        )}
      </section>

      {/* ── Right: AI Analysis ────────────────────── */}
      <aside className="w-60 shrink-0 flex flex-col border-l border-zinc-800/60">
        <div className="px-4 pt-3 pb-2 border-b border-zinc-800/60">
          <p className="text-[10px] uppercase tracking-widest text-zinc-600 font-semibold">AI Analysis</p>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-zinc-800">
          <AIAnalysisPanel signal={bundle?.signal} />
        </div>
      </aside>
    </div>
  )
}
