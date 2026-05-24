import clsx from 'clsx'

const SIGNAL_STYLES = {
  BUY: { badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', dot: 'bg-emerald-400' },
  SELL: { badge: 'bg-red-500/20 text-red-300 border-red-500/40', dot: 'bg-red-400' },
  HOLD: { badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40', dot: 'bg-amber-400' },
}

function ConfBar({ value }) {
  const pct = Math.round(value * 100)
  const color = value >= 0.75 ? 'bg-emerald-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div>
      <div className="flex justify-between text-xs text-zinc-500 mb-1">
        <span>Confidence</span>
        <span className="font-mono text-zinc-300">{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-zinc-800">
        <div className={clsx('h-full rounded-full transition-all duration-500', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function LevelRow({ label, value, colorClass }) {
  if (value == null || value === 0) return null
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-zinc-800/60 last:border-0">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={clsx('text-xs font-mono font-semibold', colorClass)}>
        ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
      </span>
    </div>
  )
}

export default function AIAnalysisPanel({ signal }) {
  if (!signal) {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-2 text-zinc-600">
        <span className="text-2xl">🤖</span>
        <p className="text-xs">No signal yet</p>
        <p className="text-[10px] text-zinc-700">Run AI scan to generate</p>
      </div>
    )
  }

  const styles = SIGNAL_STYLES[signal.signal] || SIGNAL_STYLES.HOLD
  const rr =
    signal.entry && signal.stop_loss && signal.tp1
      ? Math.abs(signal.tp1 - signal.entry) / Math.abs(signal.entry - signal.stop_loss)
      : null

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Signal + R/R */}
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold border',
            styles.badge
          )}
        >
          <span className={clsx('w-1.5 h-1.5 rounded-full', styles.dot)} />
          {signal.signal}
        </span>
        {rr != null && (
          <span className="ml-auto text-xs text-zinc-500">
            R/R <span className="text-zinc-300 font-mono">{rr.toFixed(2)}x</span>
          </span>
        )}
      </div>

      {signal.confidence != null && <ConfBar value={signal.confidence} />}

      {signal.trend && (
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Trend</span>
          <span className="text-zinc-200 font-semibold">{signal.trend}</span>
        </div>
      )}

      {/* Price levels */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 px-3 py-1">
        <LevelRow label="Entry" value={signal.entry} colorClass="text-blue-400" />
        <LevelRow label="Stop Loss" value={signal.stop_loss} colorClass="text-red-400" />
        <LevelRow label="TP 1" value={signal.tp1} colorClass="text-emerald-400" />
        <LevelRow label="TP 2" value={signal.tp2} colorClass="text-emerald-500" />
        <LevelRow label="TP 3" value={signal.tp3} colorClass="text-emerald-600" />
      </div>

      {/* Risk/Reward visual */}
      {signal.entry && signal.stop_loss && signal.tp1 && (
        <div className="space-y-1">
          <p className="text-[10px] text-zinc-600 uppercase tracking-wider">Risk / Reward</p>
          <div className="flex gap-0.5 h-2 rounded-full overflow-hidden">
            <div
              className="bg-red-500/60 rounded-l-full"
              style={{
                width: `${(Math.abs(signal.entry - signal.stop_loss) / (Math.abs(signal.entry - signal.stop_loss) + Math.abs(signal.tp1 - signal.entry))) * 100}%`,
              }}
            />
            <div className="flex-1 bg-emerald-500/60 rounded-r-full" />
          </div>
          <div className="flex justify-between text-[9px] text-zinc-600">
            <span>Risk ${Math.abs(signal.entry - signal.stop_loss).toFixed(2)}</span>
            <span>Reward ${Math.abs(signal.tp1 - signal.entry).toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* AI Reasoning */}
      {signal.analysis_text && (
        <div>
          <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1.5">AI Reasoning</p>
          <p className="text-xs text-zinc-400 leading-relaxed line-clamp-8">{signal.analysis_text}</p>
        </div>
      )}

      {signal.created_at && (
        <p className="text-[10px] text-zinc-700">
          Updated {new Date(signal.created_at).toLocaleString()}
        </p>
      )}
    </div>
  )
}
