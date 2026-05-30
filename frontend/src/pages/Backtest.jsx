import { useState } from 'react'
import { backtestApi } from '../services/api'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { Play, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'
import clsx from 'clsx'

const fmt = (n, dec = 2) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })

const INTERVALS = [
  { value: '15', label: '15m' },
  { value: '60', label: '1h' },
  { value: '240', label: '4h' },
]

function StatCard({ label, value, sub, positive, negative }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-4">
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className={clsx(
        'text-xl font-bold',
        positive ? 'text-emerald-400' : negative ? 'text-red-400' : 'text-white'
      )}>{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-0.5">{sub}</p>}
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-zinc-400">{new Date(label).toLocaleDateString()}</p>
      <p className="text-white font-semibold">${fmt(d.balance)}</p>
      {d.signal !== 'HOLD' && (
        <p className={d.signal === 'BUY' ? 'text-emerald-400' : 'text-red-400'}>{d.signal}</p>
      )}
    </div>
  )
}

export default function Backtest() {
  const [params, setParams] = useState({
    symbol: 'BTCUSDT',
    days: 30,
    interval: '60',
    sl_percent: 1.5,
    tp_percent: 3.0,
    initial_balance: 10000,
    risk_percent: 1.0,
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await backtestApi.run(params)
      if (res.data.error) throw new Error(res.data.error)
      setResult(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  const set = (k, v) => setParams(p => ({ ...p, [k]: v }))

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Backtest</h2>

      {/* Param form */}
      <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-5">
        <h3 className="text-sm text-zinc-500 uppercase tracking-wider mb-4">Parameters</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Symbol</label>
            <input
              value={params.symbol}
              onChange={e => set('symbol', e.target.value.toUpperCase())}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Days</label>
            <input
              type="number" min={7} max={90}
              value={params.days}
              onChange={e => set('days', Number(e.target.value))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Interval</label>
            <select
              value={params.interval}
              onChange={e => set('interval', e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            >
              {INTERVALS.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Initial Balance ($)</label>
            <input
              type="number" min={100}
              value={params.initial_balance}
              onChange={e => set('initial_balance', Number(e.target.value))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">SL %</label>
            <input
              type="number" min={0.1} max={20} step={0.1}
              value={params.sl_percent}
              onChange={e => set('sl_percent', Number(e.target.value))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">TP %</label>
            <input
              type="number" min={0.1} max={50} step={0.1}
              value={params.tp_percent}
              onChange={e => set('tp_percent', Number(e.target.value))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Risk %</label>
            <input
              type="number" min={0.1} max={10} step={0.1}
              value={params.risk_percent}
              onChange={e => set('risk_percent', Number(e.target.value))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={run}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {loading ? (
                <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              ) : (
                <Play size={14} />
              )}
              {loading ? 'Running…' : 'Run Backtest'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 bg-red-400/10 border border-red-400/20 rounded-xl p-4 text-sm">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {result && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label="Final Balance"
              value={`$${fmt(result.final_balance)}`}
              sub={`Started $${fmt(result.initial_balance)}`}
              positive={result.final_balance > result.initial_balance}
              negative={result.final_balance < result.initial_balance}
            />
            <StatCard
              label="Total PnL"
              value={`${result.total_pnl >= 0 ? '+' : ''}$${fmt(result.total_pnl)}`}
              sub={`${result.total_pnl_percent >= 0 ? '+' : ''}${fmt(result.total_pnl_percent)}%`}
              positive={result.total_pnl > 0}
              negative={result.total_pnl < 0}
            />
            <StatCard
              label="Win Rate"
              value={`${fmt(result.win_rate)}%`}
              sub={`${result.winning_trades}W / ${result.losing_trades}L of ${result.total_trades}`}
              positive={result.win_rate >= 50}
            />
            <StatCard
              label="Profit Factor"
              value={fmt(result.profit_factor)}
              sub={`Avg W: $${fmt(result.avg_win)} / L: $${fmt(result.avg_loss)}`}
              positive={result.profit_factor > 1}
              negative={result.profit_factor < 1}
            />
            <StatCard
              label="Max Drawdown"
              value={`${fmt(result.max_drawdown)}%`}
              negative={result.max_drawdown > 10}
            />
            <StatCard label="Trades" value={result.total_trades} sub={`${result.days}d · ${result.interval}m · ${result.candles_used} candles`} />
            <StatCard label="SL / TP" value={`${result.sl_percent}% / ${result.tp_percent}%`} sub={`Risk ${result.risk_percent}% per trade`} />
            <StatCard
              label="R:R Ratio"
              value={fmt(result.tp_percent / result.sl_percent)}
              positive={result.tp_percent / result.sl_percent >= 2}
            />
          </div>

          {/* Equity curve */}
          {result.equity_curve?.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-5">
              <h3 className="text-sm text-zinc-500 uppercase tracking-wider mb-4">Equity Curve</h3>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={result.equity_curve} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={result.total_pnl >= 0 ? '#6366f1' : '#ef4444'} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={result.total_pnl >= 0 ? '#6366f1' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 10, fill: '#52525b' }}
                    tickFormatter={v => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#52525b' }}
                    tickFormatter={v => `$${(v / 1000).toFixed(1)}k`}
                    width={50}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine y={result.initial_balance} stroke="#52525b" strokeDasharray="4 2" />
                  <Area
                    type="monotone"
                    dataKey="balance"
                    stroke={result.total_pnl >= 0 ? '#6366f1' : '#ef4444'}
                    strokeWidth={2}
                    fill="url(#eqGrad)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trade log */}
          {result.trades?.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800/60 rounded-xl p-5">
              <h3 className="text-sm text-zinc-500 uppercase tracking-wider mb-4">
                Trade Log <span className="text-zinc-600 font-normal normal-case">({result.trades.length})</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-zinc-500 border-b border-zinc-800">
                      <th className="text-left pb-2 font-medium">#</th>
                      <th className="text-left pb-2 font-medium">Dir</th>
                      <th className="text-right pb-2 font-medium">Entry</th>
                      <th className="text-right pb-2 font-medium">Exit</th>
                      <th className="text-right pb-2 font-medium">PnL</th>
                      <th className="text-right pb-2 font-medium">PnL%</th>
                      <th className="text-center pb-2 font-medium">Exit</th>
                      <th className="text-right pb-2 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {result.trades.map((t, i) => (
                      <tr key={i} className="hover:bg-zinc-800/30 transition-colors">
                        <td className="py-1.5 text-zinc-600">{i + 1}</td>
                        <td className="py-1.5">
                          <span className={clsx(
                            'flex items-center gap-1 font-semibold',
                            t.direction === 'LONG' ? 'text-emerald-400' : 'text-red-400'
                          )}>
                            {t.direction === 'LONG' ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                            {t.direction}
                          </span>
                        </td>
                        <td className="py-1.5 text-right text-zinc-300">${fmt(t.entry_price, 4)}</td>
                        <td className="py-1.5 text-right text-zinc-300">${fmt(t.exit_price, 4)}</td>
                        <td className={clsx('py-1.5 text-right font-semibold', t.pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {t.pnl >= 0 ? '+' : ''}${fmt(t.pnl)}
                        </td>
                        <td className={clsx('py-1.5 text-right', t.pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {t.pnl_pct >= 0 ? '+' : ''}{fmt(t.pnl_pct)}%
                        </td>
                        <td className="py-1.5 text-center">
                          <span className={clsx(
                            'px-1.5 py-0.5 rounded text-[10px] font-bold',
                            t.exit_reason === 'TP' ? 'bg-emerald-500/15 text-emerald-400' :
                            t.exit_reason === 'SL' ? 'bg-red-500/15 text-red-400' :
                            'bg-zinc-700 text-zinc-400'
                          )}>
                            {t.exit_reason}
                          </span>
                        </td>
                        <td className="py-1.5 text-right text-zinc-500">
                          {t.exit_time ? new Date(t.exit_time).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
