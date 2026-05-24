import { useState, useEffect } from 'react'
import { dashboardApi } from '../services/api'
import MetricCard from '../components/MetricCard'
import clsx from 'clsx'

const STATUS_COLOR = {
  SAFE: 'text-green-400 bg-green-400/10',
  WARNING: 'text-yellow-400 bg-yellow-400/10',
  DANGER: 'text-orange-400 bg-orange-400/10',
  CRITICAL: 'text-red-400 bg-red-400/10',
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchDashboard = async () => {
    try {
      const res = await dashboardApi.get()
      setData(res.data)
      setError(null)
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboard()
    const interval = setInterval(fetchDashboard, 30000)
    return () => clearInterval(interval)
  }, [])

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
    </div>
  )
}
