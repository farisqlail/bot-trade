import clsx from 'clsx'

const STATUS_STYLE = {
  OPEN: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  PENDING: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  CLOSED: 'text-zinc-400 bg-zinc-800 border-zinc-700',
  LIQUIDATED: 'text-red-400 bg-red-500/10 border-red-500/30',
}

function Stat({ label, value, cls = 'text-zinc-200' }) {
  return (
    <div className="min-w-0">
      <p className="text-[9px] uppercase tracking-wider text-zinc-600 mb-0.5 truncate">{label}</p>
      <p className={clsx('text-xs font-mono font-semibold truncate', cls)}>{value ?? '—'}</p>
    </div>
  )
}

function fmt(n, decimals = 2) {
  if (n == null) return null
  return n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export default function ActiveTradeOverlay({ trade }) {
  if (!trade) return null

  const pnlPos = (trade.pnl ?? 0) >= 0
  const dir = (trade.direction || '').toUpperCase()

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
      <div className="flex items-center gap-2 mb-2.5">
        <span
          className={clsx(
            'text-[10px] font-bold px-2 py-0.5 rounded-full border',
            dir === 'LONG'
              ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30'
              : 'text-red-300 bg-red-500/10 border-red-500/30'
          )}
        >
          {dir}
        </span>
        <span className="text-xs text-zinc-600 font-mono">Trade #{trade.id}</span>
        <span
          className={clsx(
            'text-[10px] font-semibold px-2 py-0.5 rounded-full border ml-auto',
            STATUS_STYLE[trade.status] || 'text-zinc-400'
          )}
        >
          {trade.status}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-x-3 gap-y-2">
        <Stat label="Entry" value={`$${fmt(trade.entry_price)}`} cls="text-blue-400" />
        <Stat label="Current" value={trade.current_price ? `$${fmt(trade.current_price)}` : null} />
        <Stat
          label="PnL"
          value={trade.pnl != null ? `${pnlPos ? '+' : ''}$${fmt(trade.pnl)}` : null}
          cls={trade.pnl != null ? (pnlPos ? 'text-emerald-400' : 'text-red-400') : 'text-zinc-400'}
        />
        <Stat label="Stop Loss" value={`$${fmt(trade.stop_loss)}`} cls="text-red-400" />
        <Stat label="Take Profit" value={`$${fmt(trade.take_profit)}`} cls="text-emerald-400" />
        <Stat
          label="PnL %"
          value={trade.pnl_percent != null ? `${pnlPos ? '+' : ''}${fmt(trade.pnl_percent)}%` : null}
          cls={trade.pnl_percent != null ? (pnlPos ? 'text-emerald-400' : 'text-red-400') : 'text-zinc-400'}
        />
      </div>
    </div>
  )
}
