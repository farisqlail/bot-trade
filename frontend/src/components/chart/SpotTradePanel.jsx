import { useEffect, useState } from 'react'
import clsx from 'clsx'
import { Zap, ShieldAlert, Target, RefreshCw, ExternalLink } from 'lucide-react'
import { defiApi, spotApi } from '../../services/api'

const fmt = (n, d = 4) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })

const INPUT = 'w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500/60'
const LABEL = 'text-[10px] text-zinc-500 uppercase tracking-wider mb-1'

export default function SpotTradePanel({ symbol, signal, price }) {
  const [amount, setAmount] = useState('')
  const [defiSupported, setDefiSupported] = useState(null)
  const [defiNetwork, setDefiNetwork] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null) // {ok, msg, txHash}

  const entry = signal?.entry ?? price
  const sl = signal?.stop_loss
  const tp = signal?.tp1

  useEffect(() => {
    setDefiSupported(null)
    setResult(null)
    if (!symbol) return
    defiApi.checkSupport(symbol)
      .then(r => {
        setDefiSupported(r.data.supported)
        setDefiNetwork(r.data.network)
      })
      .catch(() => setDefiSupported(false))
  }, [symbol])

  const baseSymbol = symbol?.replace('USDT', '')

  const handleBuy = async (useDefi) => {
    if (!amount || Number(amount) <= 0) return
    setSubmitting(true)
    setResult(null)
    try {
      await spotApi.createTrade({
        symbol: baseSymbol,
        base_token: baseSymbol,
        quote_token: 'USDC',
        trade_type: 'BUY',
        amount_in: Number(amount),
        price_at_trade: entry ?? 0,
        price_target: tp ?? null,
        notes: signal
          ? `AI: ${signal.signal}, conf ${Math.round((signal.confidence ?? 0) * 100)}%, SL $${fmt(sl)}, TP $${fmt(tp)}`
          : null,
      })

      let txHash = null
      if (useDefi && defiSupported) {
        const res = await defiApi.swap({
          symbol,
          direction: 'buy',
          amount_usdc: Number(amount),
        })
        txHash = res.data?.tx_hash
      }

      setResult({
        ok: true,
        msg: useDefi ? `Swap submitted${defiNetwork ? ` on ${defiNetwork}` : ''}` : 'Trade recorded',
        txHash,
      })
      setAmount('')
    } catch (e) {
      setResult({ ok: false, msg: e.response?.data?.detail || e.message || 'Failed' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleSell = async () => {
    if (!defiSupported) return
    setSubmitting(true)
    setResult(null)
    try {
      const res = await defiApi.swap({ symbol, direction: 'sell' })
      const txHash = res.data?.tx_hash
      await spotApi.createTrade({
        symbol: baseSymbol,
        base_token: baseSymbol,
        quote_token: 'USDC',
        trade_type: 'SELL',
        amount_in: 0,
        price_at_trade: price ?? 0,
        notes: 'DeFi sell-all',
      })
      setResult({ ok: true, msg: `Sell submitted${defiNetwork ? ` on ${defiNetwork}` : ''}`, txHash })
    } catch (e) {
      setResult({ ok: false, msg: e.response?.data?.detail || e.message || 'Failed' })
    } finally {
      setSubmitting(false)
    }
  }

  const explorerBase = defiNetwork === 'arbitrum' ? 'https://arbiscan.io/tx/'
    : defiNetwork === 'base' ? 'https://basescan.org/tx/'
    : defiNetwork === 'bsc' ? 'https://bscscan.com/tx/'
    : defiNetwork === 'optimism' ? 'https://optimistic.etherscan.io/tx/'
    : defiNetwork === 'polygon' ? 'https://polygonscan.com/tx/'
    : 'https://etherscan.io/tx/'

  return (
    <div className="flex flex-col gap-3 p-4 border-t border-zinc-800/60">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600 font-semibold">Spot Trade</p>

      {/* AI levels */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 divide-y divide-zinc-800/60">
        <div className="flex justify-between px-3 py-1.5">
          <span className="text-[10px] text-zinc-500">Entry</span>
          <span className="text-[10px] font-mono text-blue-400">${fmt(entry)}</span>
        </div>
        <div className="flex justify-between px-3 py-1.5">
          <span className="text-[10px] text-zinc-500 flex items-center gap-1">
            <ShieldAlert size={9} className="text-red-400" /> SL
          </span>
          <span className="text-[10px] font-mono text-red-400">${fmt(sl)}</span>
        </div>
        <div className="flex justify-between px-3 py-1.5">
          <span className="text-[10px] text-zinc-500 flex items-center gap-1">
            <Target size={9} className="text-emerald-400" /> TP
          </span>
          <span className="text-[10px] font-mono text-emerald-400">${fmt(tp)}</span>
        </div>
      </div>

      {/* USDC input */}
      <div>
        <p className={LABEL}>Amount (USDC)</p>
        <input
          type="number"
          min="0"
          step="any"
          className={INPUT}
          value={amount}
          onChange={e => setAmount(e.target.value)}
          placeholder="100"
        />
      </div>

      {/* DeFi status */}
      <div className="flex items-center gap-1.5">
        {defiSupported === null
          ? <><RefreshCw size={9} className="text-zinc-600 animate-spin" /><span className="text-[10px] text-zinc-600">Checking DEX…</span></>
          : defiSupported
            ? <><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /><span className="text-[10px] text-emerald-500">DEX available · {defiNetwork}</span></>
            : <><span className="w-1.5 h-1.5 rounded-full bg-zinc-600" /><span className="text-[10px] text-zinc-600">No DEX pool</span></>
        }
      </div>

      {/* Buttons */}
      <div className="flex flex-col gap-1.5">
        {defiSupported && (
          <button
            onClick={() => handleBuy(true)}
            disabled={submitting || !amount}
            className="w-full flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-bold py-2 rounded-lg transition-colors"
          >
            <Zap size={11} />
            {submitting ? '…' : 'Buy via DeFi'}
          </button>
        )}
        <button
          onClick={() => handleBuy(false)}
          disabled={submitting || !amount}
          className="w-full flex items-center justify-center gap-1.5 bg-emerald-700/40 hover:bg-emerald-700/60 border border-emerald-700/40 disabled:opacity-40 text-emerald-300 text-xs font-semibold py-2 rounded-lg transition-colors"
        >
          {submitting ? '…' : 'Record Only'}
        </button>
        {defiSupported && (
          <button
            onClick={handleSell}
            disabled={submitting}
            className="w-full flex items-center justify-center gap-1.5 bg-red-700/30 hover:bg-red-700/50 border border-red-700/30 disabled:opacity-40 text-red-400 text-xs font-semibold py-2 rounded-lg transition-colors"
          >
            {submitting ? '…' : 'Sell All via DeFi'}
          </button>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className={clsx(
          'text-xs rounded-lg px-3 py-2 border',
          result.ok
            ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20'
            : 'text-red-400 bg-red-500/10 border-red-500/20'
        )}>
          <p>{result.msg}</p>
          {result.txHash && (
            <a
              href={`${explorerBase}${result.txHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 mt-1 text-indigo-400 hover:text-indigo-300"
            >
              {result.txHash.slice(0, 10)}… <ExternalLink size={9} />
            </a>
          )}
        </div>
      )}
    </div>
  )
}
