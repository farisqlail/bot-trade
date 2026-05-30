import { useEffect, useState, useRef } from 'react'
import { backtestApi } from '../services/api'
import clsx from 'clsx'

const fmt = (n, dec = 2) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })

export default function QuickBacktest({ symbol, delay = 0, slPercent = 1.5, tpPercent = 3.0, days = 30 }) {
  const [state, setState] = useState('idle') // idle | loading | done | error
  const [result, setResult] = useState(null)
  const timerRef = useRef(null)

  useEffect(() => {
    timerRef.current = setTimeout(async () => {
      setState('loading')
      try {
        const res = await backtestApi.run({
          symbol,
          days,
          interval: '60',
          sl_percent: slPercent,
          tp_percent: tpPercent,
          initial_balance: 10000,
          risk_percent: 1.0,
        })
        if (res.data.error) throw new Error(res.data.error)
        setResult(res.data)
        setState('done')
      } catch {
        setState('error')
      }
    }, delay)
    return () => clearTimeout(timerRef.current)
  }, [symbol, delay, slPercent, tpPercent, days])

  if (state === 'idle') return null

  if (state === 'loading') return (
    <div className="mt-3 pt-3 border-t border-gray-800/60 flex items-center gap-2 text-xs text-gray-600">
      <span className="animate-spin rounded-full h-3 w-3 border-b border-indigo-400" />
      Running backtest (30d)…
    </div>
  )

  if (state === 'error') return (
    <div className="mt-3 pt-3 border-t border-gray-800/60 text-xs text-gray-600">
      Backtest unavailable
    </div>
  )

  const pnlPos = result.total_pnl_percent >= 0
  const pfGood = result.profit_factor >= 1
  const ddHigh = result.max_drawdown > 10

  return (
    <div className="mt-3 pt-3 border-t border-gray-800/60">
      <p className="text-[10px] uppercase tracking-wider text-gray-600 mb-2">
        Backtest · 30d · 1h · SL {result.sl_percent}% TP {result.tp_percent}%
      </p>
      <div className="grid grid-cols-4 gap-2">
        <div className="rounded-lg bg-gray-800/50 px-2.5 py-2 text-center">
          <p className="text-[10px] text-gray-500">Win Rate</p>
          <p className={clsx('text-sm font-bold', result.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400')}>
            {fmt(result.win_rate)}%
          </p>
          <p className="text-[10px] text-gray-600">{result.winning_trades}W/{result.losing_trades}L</p>
        </div>
        <div className="rounded-lg bg-gray-800/50 px-2.5 py-2 text-center">
          <p className="text-[10px] text-gray-500">PnL</p>
          <p className={clsx('text-sm font-bold', pnlPos ? 'text-emerald-400' : 'text-red-400')}>
            {pnlPos ? '+' : ''}{fmt(result.total_pnl_percent)}%
          </p>
          <p className="text-[10px] text-gray-600">{result.total_trades} trades</p>
        </div>
        <div className="rounded-lg bg-gray-800/50 px-2.5 py-2 text-center">
          <p className="text-[10px] text-gray-500">Profit Factor</p>
          <p className={clsx('text-sm font-bold', pfGood ? 'text-emerald-400' : 'text-red-400')}>
            {fmt(result.profit_factor)}
          </p>
          <p className="text-[10px] text-gray-600">R:R {fmt(result.tp_percent / result.sl_percent, 1)}</p>
        </div>
        <div className="rounded-lg bg-gray-800/50 px-2.5 py-2 text-center">
          <p className="text-[10px] text-gray-500">Max DD</p>
          <p className={clsx('text-sm font-bold', ddHigh ? 'text-red-400' : 'text-amber-400')}>
            {fmt(result.max_drawdown)}%
          </p>
          <p className="text-[10px] text-gray-600">${fmt(result.final_balance, 0)}</p>
        </div>
      </div>
    </div>
  )
}
