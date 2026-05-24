import { useState, useEffect } from 'react'
import { tradesApi } from '../services/api'
import clsx from 'clsx'

export default function TradeHistory() {
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 20

  useEffect(() => {
    const fetch = async () => {
      setLoading(true)
      try {
        const res = await tradesApi.getHistory({ limit: PAGE_SIZE, offset: page * PAGE_SIZE })
        setTrades(res.data)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [page])

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Trade History</h2>

      {loading ? (
        <div className="animate-pulse text-gray-500">Loading history...</div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-left">Dir</th>
                <th className="px-4 py-3 text-right">Entry</th>
                <th className="px-4 py-3 text-right">Exit</th>
                <th className="px-4 py-3 text-right">PnL</th>
                <th className="px-4 py-3 text-right">PnL%</th>
                <th className="px-4 py-3 text-right">Closed</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-500">
                    No trade history
                  </td>
                </tr>
              ) : (
                trades.map((t) => (
                  <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-3 font-medium">{t.symbol}</td>
                    <td className="px-4 py-3">
                      <span className={clsx(
                        'text-xs font-bold',
                        t.direction === 'LONG' ? 'text-green-400' : 'text-red-400'
                      )}>
                        {t.direction}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">${t.entry_price.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">${t.exit_price?.toLocaleString() || '-'}</td>
                    <td className={clsx(
                      'px-4 py-3 text-right font-medium',
                      (t.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    )}>
                      {t.pnl !== null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '-'}
                    </td>
                    <td className={clsx(
                      'px-4 py-3 text-right text-xs',
                      (t.pnl_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    )}>
                      {t.pnl_percent !== null ? `${t.pnl_percent >= 0 ? '+' : ''}${t.pnl_percent.toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-500 text-xs">
                      {t.closed_at ? new Date(t.closed_at).toLocaleDateString() : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-40 rounded"
            >
              Previous
            </button>
            <span className="text-xs text-gray-500">Page {page + 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={trades.length < PAGE_SIZE}
              className="px-3 py-1 text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-40 rounded"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
