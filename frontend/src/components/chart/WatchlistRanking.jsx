import clsx from 'clsx'

const SIGNAL_COLOR = {
  BUY: 'text-emerald-400',
  SELL: 'text-red-400',
  HOLD: 'text-amber-400',
}

function formatPrice(price) {
  if (!price) return '—'
  return price > 1
    ? price.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : price.toPrecision(4)
}

export default function WatchlistRanking({ items = [], selectedSymbol, onSelect }) {
  if (!items.length) {
    return (
      <div className="py-6 text-center">
        <p className="text-xs text-zinc-600">Run AI scan</p>
        <p className="text-[10px] text-zinc-700 mt-0.5">to populate rankings</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-0.5">
      {items.map((item, i) => (
        <button
          key={item.symbol}
          onClick={() => onSelect?.(item.symbol)}
          className={clsx(
            'w-full text-left px-3 py-2.5 rounded-xl transition-all duration-150 border group',
            selectedSymbol === item.symbol
              ? 'bg-indigo-500/10 border-indigo-500/25 shadow-sm'
              : 'border-transparent hover:bg-zinc-800/60 hover:border-zinc-700/40'
          )}
        >
          <div className="flex items-center justify-between mb-0.5">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-zinc-700 font-mono w-3 shrink-0">#{i + 1}</span>
              <span className="text-sm font-bold text-zinc-100 leading-none">
                {item.symbol.replace('USDT', '')}
              </span>
            </div>
            {item.signal && (
              <span className={clsx('text-[10px] font-bold', SIGNAL_COLOR[item.signal] || 'text-zinc-500')}>
                {item.signal}
              </span>
            )}
          </div>

          <div className="flex items-center justify-between mt-0.5">
            <span className="text-[11px] text-zinc-400 font-mono">${formatPrice(item.price)}</span>
            <span
              className={clsx(
                'text-[10px] font-mono',
                item.change_24h >= 0 ? 'text-emerald-400' : 'text-red-400'
              )}
            >
              {item.change_24h >= 0 ? '+' : ''}
              {item.change_24h.toFixed(2)}%
            </span>
          </div>

          {item.confidence != null && (
            <div className="mt-1.5 h-0.5 rounded-full bg-zinc-800/80">
              <div
                className={clsx(
                  'h-full rounded-full transition-all',
                  selectedSymbol === item.symbol ? 'bg-indigo-400' : 'bg-zinc-600 group-hover:bg-zinc-500'
                )}
                style={{ width: `${Math.round(item.confidence * 100)}%` }}
              />
            </div>
          )}
        </button>
      ))}
    </div>
  )
}
