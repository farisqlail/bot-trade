import { useState, useEffect } from 'react'
import { portfolioApi } from '../services/api'
import clsx from 'clsx'
import { RefreshCw, Wallet, AlertCircle } from 'lucide-react'

const fmt = (n, dec = 2) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })

const SOURCE_COLORS = {
  paper:  { bar: 'bg-indigo-500',  dot: 'bg-indigo-400',  text: 'text-indigo-400',  bg: 'bg-indigo-500/10 border-indigo-500/25' },
  bybit:  { bar: 'bg-amber-500',   dot: 'bg-amber-400',   text: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/25'   },
  defi:   { bar: 'bg-emerald-500', dot: 'bg-emerald-400', text: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/25'},
  gmx:    { bar: 'bg-blue-500',    dot: 'bg-blue-400',    text: 'text-blue-400',    bg: 'bg-blue-500/10 border-blue-500/25'     },
  gtrade: { bar: 'bg-teal-500',    dot: 'bg-teal-400',    text: 'text-teal-400',    bg: 'bg-teal-500/10 border-teal-500/25'     },
}

function PnlSpan({ value }) {
  if (value == null || value === 0) return null
  const pos = value >= 0
  return (
    <span className={clsx('text-xs', pos ? 'text-emerald-400' : 'text-red-400')}>
      {pos ? '+' : ''}${fmt(value)}
    </span>
  )
}

export default function Portfolio() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [enabled, setEnabled] = useState(null) // null = all; Set when user toggles

  const toggleSource = (key) => {
    setEnabled(prev => {
      const all = prev ?? new Set(Object.keys(data?.sources || {}))
      const next = new Set(all)
      if (next.has(key)) { next.delete(key) } else { next.add(key) }
      return next
    })
  }

  const fetchData = async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)
    setError(null)
    try {
      const res = await portfolioApi.get()
      setData(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load portfolio')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500" />
    </div>
  )

  if (error) return (
    <div className="flex items-center gap-2 text-red-400 bg-red-400/10 rounded-xl p-4">
      <AlertCircle size={16} /> {error}
    </div>
  )

  const { total_portfolio_value, sources, errors } = data
  const allEntries = Object.entries(sources || {})

  const activeKeys = enabled ?? new Set(allEntries.map(([k]) => k))
  const entries = allEntries.filter(([k]) => activeKeys.has(k))
  const filteredTotal = entries.reduce((s, [, src]) => s + (src.total || 0), 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold">Portfolio</h2>
          <p className="text-sm text-zinc-500 mt-0.5">Consolidated view across all accounts</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {/* Source filter toggles */}
          {allEntries.map(([key, src]) => {
            const colors = SOURCE_COLORS[key] || { dot: 'bg-zinc-400', text: 'text-zinc-400' }
            const on = activeKeys.has(key)
            return (
              <button
                key={key}
                onClick={() => toggleSource(key)}
                className={clsx(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all',
                  on
                    ? clsx('border-transparent bg-zinc-700 text-zinc-200')
                    : 'border-zinc-800 bg-transparent text-zinc-600 opacity-50'
                )}
              >
                <span className={clsx('w-2 h-2 rounded-full', on ? colors.dot : 'bg-zinc-600')} />
                {src.label}
              </button>
            )
          })}
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition-colors"
          >
            <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Total hero */}
      <div className="bg-gradient-to-br from-indigo-500/15 to-zinc-900 border border-indigo-500/20 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-indigo-500/20 rounded-xl flex items-center justify-center">
            <Wallet size={18} className="text-indigo-400" />
          </div>
          <span className="text-sm text-zinc-400">Total Portfolio Value</span>
        </div>
        <div className="flex items-baseline gap-3">
          <p className="text-4xl font-bold text-white">${fmt(filteredTotal)}</p>
          {filteredTotal !== total_portfolio_value && (
            <span className="text-sm text-zinc-500">of ${fmt(total_portfolio_value)} total</span>
          )}
        </div>

        {/* Allocation bar */}
        {filteredTotal > 0 && (
          <div className="mt-5">
            <div className="flex h-2.5 rounded-full overflow-hidden gap-0.5">
              {entries.map(([key, src]) => {
                const pct = filteredTotal > 0 ? (src.total / filteredTotal) * 100 : 0
                if (pct < 0.5) return null
                return (
                  <div
                    key={key}
                    className={clsx('rounded-full', SOURCE_COLORS[key]?.bar || 'bg-zinc-600')}
                    style={{ width: `${pct}%` }}
                    title={`${src.label}: $${fmt(src.total)} (${pct.toFixed(1)}%)`}
                  />
                )
              })}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2.5">
              {entries.map(([key, src]) => {
                if (src.total <= 0) return null
                const pct = filteredTotal > 0 ? (src.total / filteredTotal) * 100 : 0
                return (
                  <div key={key} className="flex items-center gap-1.5 text-xs text-zinc-500">
                    <span className={clsx('w-2 h-2 rounded-full', SOURCE_COLORS[key]?.dot || 'bg-zinc-600')} />
                    <span>{src.label}</span>
                    <span className="text-zinc-400">{pct.toFixed(1)}%</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Source cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {entries.map(([key, src]) => {
          const colors = SOURCE_COLORS[key] || { bg: 'bg-zinc-800/60 border-zinc-700/40', text: 'text-zinc-400' }
          const pct = filteredTotal > 0 ? (src.total / filteredTotal) * 100 : 0
          return (
            <div key={key} className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold border', colors.bg, colors.text)}>
                    {src.label}
                  </span>
                </div>
                <span className="text-xs text-zinc-600">{pct.toFixed(1)}% of total</span>
              </div>

              <p className="text-2xl font-bold text-white mt-1">${fmt(src.total)}</p>

              <div className="mt-3 space-y-1.5 text-xs text-zinc-500">
                <div className="flex justify-between">
                  <span>Balance</span>
                  <span className="text-zinc-300">${fmt(src.balance)}</span>
                </div>
                {src.unrealized_pnl != null && src.unrealized_pnl !== 0 && (
                  <div className="flex justify-between">
                    <span>Unrealized PnL</span>
                    <PnlSpan value={src.unrealized_pnl} />
                  </div>
                )}
                {src.held_tokens_count > 0 && (
                  <div className="flex justify-between gap-2">
                    <span>Held Tokens</span>
                    <span className="text-zinc-300 text-right">{(src.held_tokens || []).join(', ') || src.held_tokens_count}</span>
                  </div>
                )}
                {src.positions != null && (
                  <div className="flex justify-between">
                    <span>Open Positions</span>
                    <span className="text-zinc-300">{src.positions}</span>
                  </div>
                )}
                {src.currency && (
                  <div className="flex justify-between">
                    <span>Currency</span>
                    <span className="text-zinc-400">{src.currency}</span>
                  </div>
                )}
                {src.wallet && (
                  <div className="flex justify-between gap-2">
                    <span>Wallet</span>
                    <span className="text-zinc-400 truncate font-mono text-[10px]">
                      {src.wallet.slice(0, 8)}…{src.wallet.slice(-6)}
                    </span>
                  </div>
                )}
              </div>

              {/* Mini allocation bar */}
              <div className="mt-3 h-1 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={clsx('h-full rounded-full', SOURCE_COLORS[key]?.bar || 'bg-zinc-600')}
                  style={{ width: `${Math.min(pct, 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Fetch errors (non-critical) */}
      {errors && errors.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/25 rounded-xl p-4">
          <p className="text-xs font-semibold text-yellow-400 mb-1 flex items-center gap-1.5">
            <AlertCircle size={12} /> Some sources unavailable
          </p>
          {errors.map((e, i) => (
            <p key={i} className="text-xs text-zinc-500">{e}</p>
          ))}
        </div>
      )}
    </div>
  )
}
