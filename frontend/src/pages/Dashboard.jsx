import { useState, useEffect, useMemo } from 'react'
import { dashboardApi, sentimentApi, portfolioApi } from '../services/api'
import MetricCard from '../components/MetricCard'
import { useWsChannel } from '../hooks/useWsChannel'
import clsx from 'clsx'

const SOURCE_COLORS = {
  paper:  { bar: 'bg-indigo-500',  dot: 'bg-indigo-400',  text: 'text-indigo-400' },
  bybit:  { bar: 'bg-amber-500',   dot: 'bg-amber-400',   text: 'text-amber-400'  },
  defi:   { bar: 'bg-emerald-500', dot: 'bg-emerald-400', text: 'text-emerald-400'},
  gmx:    { bar: 'bg-blue-500',    dot: 'bg-blue-400',    text: 'text-blue-400'   },
  gtrade: { bar: 'bg-teal-500',    dot: 'bg-teal-400',    text: 'text-teal-400'   },
}

const fmtUsd = (n) => n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const STATUS_COLOR = {
  SAFE: 'text-green-400 bg-green-400/10',
  WARNING: 'text-yellow-400 bg-yellow-400/10',
  DANGER: 'text-orange-400 bg-orange-400/10',
  CRITICAL: 'text-red-400 bg-red-400/10',
}

const WS_CHANNELS = ['dashboard']

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sentiment, setSentiment] = useState(null)
  const [portfolio, setPortfolio] = useState(null)

  // Initial load via REST
  useEffect(() => {
    dashboardApi.get()
      .then((res) => { setData(res.data); setError(null) })
      .catch((e) => setError(e.response?.data?.error || 'Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  // Sentiment — fetch once, refresh every 5 min
  useEffect(() => {
    const load = () => sentimentApi.get().then((r) => setSentiment(r.data)).catch(() => {})
    load()
    const id = setInterval(load, 300_000)
    return () => clearInterval(id)
  }, [])

  // Portfolio summary — fetch once, refresh every 2 min
  useEffect(() => {
    const load = () => portfolioApi.get().then((r) => setPortfolio(r.data)).catch(() => {})
    load()
    const id = setInterval(load, 120_000)
    return () => clearInterval(id)
  }, [])

  // Real-time updates via WebSocket — merges into REST data
  const { data: wsData, status: wsStatus } = useWsChannel(WS_CHANNELS)

  useEffect(() => {
    const ws = wsData?.dashboard
    if (!ws || !data) return
    setData((prev) => ({
      ...prev,
      account: { ...prev.account, balance: ws.balance },
      pnl: {
        ...prev.pnl,
        daily_pnl: ws.daily_pnl,
        daily_pnl_percent: ws.balance ? ws.daily_pnl / ws.balance * 100 : 0,
        weekly_pnl: ws.weekly_pnl,
        weekly_pnl_percent: ws.balance ? ws.weekly_pnl / ws.balance * 100 : 0,
        total_pnl: ws.total_pnl,
      },
      trades: { ...prev.trades, win_rate: ws.win_rate },
      risk: {
        ...prev.risk,
        open_positions: ws.open_positions,
        status: ws.risk_status,
        daily_loss_percent: ws.daily_loss_percent,
        current_drawdown_percent: ws.current_drawdown_percent,
        consecutive_losses: ws.consecutive_losses,
      },
    }))
  }, [wsData?.dashboard])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500" />
    </div>
  )

  if (error) return (
    <div className="text-red-400 bg-red-400/10 rounded-xl p-4">{error}</div>
  )

  const { account, pnl, trades, risk, bot } = data

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <div className="flex items-center gap-3">
          <span className={clsx(
            'flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-semibold',
            wsStatus === 'connected' ? 'text-green-400 bg-green-400/10' : 'text-gray-500 bg-gray-800'
          )}>
            <span className={clsx(
              'inline-block w-1.5 h-1.5 rounded-full',
              wsStatus === 'connected' ? 'bg-green-400 animate-pulse' : 'bg-gray-600'
            )} />
            {wsStatus === 'connected' ? 'Live' : 'Offline'}
          </span>
          <span className={clsx(
            'px-3 py-1 rounded-full text-xs font-semibold',
            STATUS_COLOR[risk.status] || 'text-gray-400 bg-gray-700'
          )}>
            Risk: {risk.status}
          </span>
          <span className={clsx(
            'px-3 py-1 rounded-full text-xs font-semibold',
            bot.is_running ? 'text-green-400 bg-green-400/10' : 'text-gray-400 bg-gray-700'
          )}>
            Bot: {bot.is_running ? 'Running' : 'Stopped'}
          </span>
        </div>
      </div>

      {/* Account Section */}
      <div>
        <h3 className="text-sm text-gray-500 uppercase tracking-wider mb-3">Account</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard title="Balance" value={`$${account.balance.toLocaleString()}`} />
          <MetricCard title="Equity" value={`$${account.equity.toLocaleString()}`} />
          <MetricCard
            title="Unrealized PnL"
            value={`$${account.unrealized_pnl.toFixed(2)}`}
            trend={account.unrealized_pnl}
            subtitle={`${account.unrealized_pnl >= 0 ? '+' : ''}${account.unrealized_pnl.toFixed(2)}`}
          />
          <MetricCard title="Free Margin" value={`$${account.free_margin.toLocaleString()}`} />
        </div>
      </div>

      {/* PnL Section */}
      <div>
        <h3 className="text-sm text-gray-500 uppercase tracking-wider mb-3">PnL</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <MetricCard
            title="Daily PnL"
            value={`$${pnl.daily_pnl.toFixed(2)}`}
            subtitle={`${pnl.daily_pnl_percent.toFixed(2)}%`}
            trend={pnl.daily_pnl}
          />
          <MetricCard
            title="Weekly PnL"
            value={`$${pnl.weekly_pnl.toFixed(2)}`}
            subtitle={`${pnl.weekly_pnl_percent.toFixed(2)}%`}
            trend={pnl.weekly_pnl}
          />
          <MetricCard
            title="Total PnL"
            value={`$${pnl.total_pnl.toFixed(2)}`}
            trend={pnl.total_pnl}
          />
        </div>
      </div>

      {/* Trade Stats */}
      <div>
        <h3 className="text-sm text-gray-500 uppercase tracking-wider mb-3">Performance</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard title="Total Trades" value={trades.total_trades} />
          <MetricCard
            title="Win Rate"
            value={`${trades.win_rate.toFixed(1)}%`}
            subtitle={`${trades.winning_trades}W / ${trades.losing_trades}L`}
          />
          <MetricCard
            title="Profit Factor"
            value={trades.profit_factor.toFixed(2)}
          />
          <MetricCard
            title="Open Positions"
            value={risk.open_positions}
            subtitle={`Max: ${risk.max_open_trades}`}
          />
        </div>
      </div>

      {/* Risk Status */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="text-sm text-gray-500 uppercase tracking-wider mb-4">Risk Monitor</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
          <div>
            <p className="text-xs text-gray-500">Daily Loss</p>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-500 rounded-full transition-all"
                  style={{ width: `${Math.min((risk.daily_loss_percent / risk.daily_loss_limit_percent) * 100, 100)}%` }}
                />
              </div>
              <span className="text-xs text-gray-400">
                {risk.daily_loss_percent.toFixed(1)}% / {risk.daily_loss_limit_percent}%
              </span>
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500">Drawdown</p>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-orange-500 rounded-full transition-all"
                  style={{ width: `${Math.min((risk.current_drawdown_percent / risk.max_drawdown_percent) * 100, 100)}%` }}
                />
              </div>
              <span className="text-xs text-gray-400">
                {risk.current_drawdown_percent.toFixed(1)}% / {risk.max_drawdown_percent}%
              </span>
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500">Consecutive Losses</p>
            <p className="text-lg font-semibold mt-1 text-white">
              {risk.consecutive_losses}
              <span className="text-xs text-gray-500"> / {risk.consecutive_loss_limit}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Portfolio Summary */}
      {portfolio && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm text-gray-500 uppercase tracking-wider">Portfolio</h3>
            <span className="text-xl font-bold text-white">${fmtUsd(portfolio.total_portfolio_value)}</span>
          </div>

          {/* Allocation bar */}
          {portfolio.total_portfolio_value > 0 && (
            <div className="flex h-2 rounded-full overflow-hidden gap-0.5 mb-3">
              {Object.entries(portfolio.sources || {}).map(([key, src]) => {
                const pct = (src.total / portfolio.total_portfolio_value) * 100
                if (pct < 0.5) return null
                return (
                  <div
                    key={key}
                    className={clsx('rounded-full', SOURCE_COLORS[key]?.bar || 'bg-gray-600')}
                    style={{ width: `${pct}%` }}
                    title={`${src.label}: $${fmtUsd(src.total)} (${pct.toFixed(1)}%)`}
                  />
                )
              })}
            </div>
          )}

          {/* Source rows */}
          <div className="space-y-2">
            {Object.entries(portfolio.sources || {}).map(([key, src]) => {
              const pct = portfolio.total_portfolio_value > 0
                ? (src.total / portfolio.total_portfolio_value) * 100
                : 0
              return (
                <div key={key} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className={clsx('w-2 h-2 rounded-full', SOURCE_COLORS[key]?.dot || 'bg-gray-600')} />
                    <span className={clsx('font-medium', SOURCE_COLORS[key]?.text || 'text-gray-400')}>{src.label}</span>
                    {src.unrealized_pnl != null && src.unrealized_pnl !== 0 && (
                      <span className={src.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {src.unrealized_pnl >= 0 ? '+' : ''}${fmtUsd(src.unrealized_pnl)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-500">{pct.toFixed(1)}%</span>
                    <span className="text-white font-semibold">${fmtUsd(src.total)}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {portfolio.errors && portfolio.errors.length > 0 && (
            <p className="text-[10px] text-yellow-500/70 mt-3">
              {portfolio.errors.length} source{portfolio.errors.length > 1 ? 's' : ''} unavailable
            </p>
          )}
        </div>
      )}

      {/* Market Sentiment */}
      {sentiment && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h3 className="text-sm text-gray-500 uppercase tracking-wider mb-4">Market Sentiment</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            {/* Fear & Greed Gauge */}
            <div className="col-span-2 md:col-span-1">
              <p className="text-xs text-gray-500">Fear & Greed Index</p>
              <div className="mt-2">
                <div className="flex items-end gap-2">
                  <span className={clsx(
                    'text-3xl font-bold',
                    sentiment.fear_greed_value >= 70 ? 'text-green-400' :
                    sentiment.fear_greed_value >= 55 ? 'text-emerald-400' :
                    sentiment.fear_greed_value >= 45 ? 'text-yellow-400' :
                    sentiment.fear_greed_value >= 30 ? 'text-orange-400' : 'text-red-400'
                  )}>
                    {sentiment.fear_greed_value}
                  </span>
                  <span className="text-sm text-gray-400 pb-0.5">{sentiment.fear_greed_classification}</span>
                </div>
                <div className="mt-2 h-2 bg-gradient-to-r from-red-500 via-yellow-400 to-green-500 rounded-full relative">
                  <div
                    className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full border-2 border-gray-900 shadow"
                    style={{ left: `calc(${sentiment.fear_greed_value}% - 6px)` }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                  <span>Fear</span><span>Greed</span>
                </div>
              </div>
            </div>

            {/* Trending */}
            <div className="col-span-2">
              <p className="text-xs text-gray-500">CoinGecko Trending</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(sentiment.trending_symbols || []).length > 0 ? (
                  sentiment.trending_symbols.map((sym) => (
                    <span key={sym} className="px-2 py-0.5 bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-xs rounded-md font-mono">
                      {sym}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-gray-600">No data</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
