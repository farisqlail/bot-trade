import { useState, useEffect } from 'react'
import { tradesApi } from '../services/api'
import { useWsChannel } from '../hooks/useWsChannel'
import clsx from 'clsx'

const WS_CHANNELS = ['trades']

export default function ActiveTrades() {
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(true)
  const [closingId, setClosingId] = useState(null)
  const [closePrice, setClosePrice] = useState('')

  // Initial load via REST
  useEffect(() => {
    tradesApi.getOpen()
      .then((res) => setTrades(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // Real-time updates via WebSocket
  const { data: wsData, status: wsStatus } = useWsChannel(WS_CHANNELS)

  useEffect(() => {
    if (wsData?.trades?.trades) {
      setTrades(wsData.trades.trades)
    }
  }, [wsData?.trades])

  const fetchTrades = async () => {
    try {
      const res = await tradesApi.getOpen()
      setTrades(res.data)
    } catch (e) {
      console.error(e)
    }
  }

  const handleClose = async (tradeId) => {
    if (!closePrice || isNaN(parseFloat(closePrice))) return
    try {
      await tradesApi.close(tradeId, { exit_price: parseFloat(closePrice) })
      setClosingId(null)
      setClosePrice('')
      fetchTrades()
    } catch (e) {
      alert(e.response?.data?.error || 'Failed to close trade')
    }
  }

  if (loading) return <div className="animate-pulse text-gray-500">Loading trades...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Active Trades</h2>
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
          <span className="text-sm text-gray-400">{trades.length} open</span>
        </div>
      </div>

      {trades.length === 0 ? (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
          <p className="text-gray-500">No open trades</p>
        </div>
      ) : (
        <div className="space-y-3">
          {trades.map((trade) => (
            <div key={trade.id} className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <span className={clsx(
                    'px-2 py-1 rounded text-xs font-bold',
                    trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                  )}>
                    {trade.direction}
                  </span>
                  <div>
                    <p className="font-semibold">{trade.symbol}</p>
                    <p className="text-xs text-gray-500">
                      Entry: ${trade.entry_price.toLocaleString()} · Qty: {trade.quantity}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-500">SL / TP</p>
                  <p className="text-sm">
                    <span className="text-red-400">${trade.stop_loss.toLocaleString()}</span>
                    {' / '}
                    <span className="text-green-400">${trade.take_profit.toLocaleString()}</span>
                  </p>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-3">
                {closingId === trade.id ? (
                  <>
                    <input
                      type="number"
                      placeholder="Exit price"
                      value={closePrice}
                      onChange={(e) => setClosePrice(e.target.value)}
                      className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm"
                    />
                    <button
                      onClick={() => handleClose(trade.id)}
                      className="px-4 py-1.5 bg-red-500 hover:bg-red-600 text-white text-sm rounded-lg"
                    >
                      Confirm Close
                    </button>
                    <button
                      onClick={() => setClosingId(null)}
                      className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-sm rounded-lg"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setClosingId(trade.id)}
                    className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg border border-gray-700"
                  >
                    Close Trade
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
