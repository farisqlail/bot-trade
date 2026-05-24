import clsx from 'clsx'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function MetricCard({ title, value, subtitle, trend, icon: Icon, className }) {
  const isPositive = trend > 0
  const isNegative = trend < 0
  const isNeutral = !isPositive && !isNegative

  return (
    <div className={clsx(
      'relative overflow-hidden rounded-2xl border bg-zinc-900/50 p-5 transition-all duration-200 hover:border-zinc-700/60',
      isPositive ? 'border-emerald-500/15' : isNegative ? 'border-red-500/15' : 'border-zinc-800/60',
      className
    )}>
      {isPositive && (
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent" />
      )}
      {isNegative && (
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-red-500/5 via-transparent to-transparent" />
      )}

      <div className="relative flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">{title}</p>
        {Icon && (
          <div className="shrink-0 rounded-lg bg-zinc-800/80 p-2">
            <Icon size={14} className="text-zinc-400" />
          </div>
        )}
      </div>

      <p className="relative mt-3 text-2xl font-bold tracking-tight text-white">{value}</p>

      {subtitle !== undefined && (
        <div className={clsx(
          'relative mt-2 flex items-center gap-1 text-sm font-medium',
          isPositive ? 'text-emerald-400' : isNegative ? 'text-red-400' : 'text-zinc-500'
        )}>
          {isPositive && <TrendingUp size={13} strokeWidth={2.5} />}
          {isNegative && <TrendingDown size={13} strokeWidth={2.5} />}
          {isNeutral && <Minus size={13} strokeWidth={2.5} />}
          <span>{isPositive ? '+' : ''}{subtitle}</span>
        </div>
      )}
    </div>
  )
}
