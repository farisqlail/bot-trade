import { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import {
  Plus, RefreshCw, ExternalLink, Pencil, Trash2, X, TrendingUp,
  Brain, ShieldAlert, Target, Zap, ToggleLeft, ToggleRight,
} from 'lucide-react'
import { spotApi, spotWatchlistApi, aiApi, defiApi } from '../services/api'

// ── helpers ──────────────────────────────────────────────────────────────────

const fmt = (n, dec = 2) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })

const SIGNAL_CFG = {
  STRONG_BUY:  { label: 'STRONG BUY',  cls: 'text-emerald-200 bg-emerald-500/25 border-emerald-500/40' },
  BUY:         { label: 'BUY',         cls: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30' },
  HOLD:        { label: 'HOLD',        cls: 'text-zinc-400   bg-zinc-500/10   border-zinc-500/20'   },
  SELL:        { label: 'SELL',        cls: 'text-red-300    bg-red-500/15    border-red-500/30'    },
  STRONG_SELL: { label: 'STRONG SELL', cls: 'text-red-200    bg-red-500/25    border-red-500/40'    },
  WATCH:       { label: 'WATCH',       cls: 'text-amber-300  bg-amber-500/10  border-amber-500/25'  },
  NEUTRAL:     { label: 'NEUTRAL',     cls: 'text-zinc-500   bg-zinc-700/20   border-zinc-700/30'   },
  UNKNOWN:     { label: '—',           cls: 'text-zinc-600   bg-zinc-800/20   border-zinc-800/30'   },
}

const TYPE_CFG = {
  BUY:  { label: 'BUY',  cls: 'text-sky-300 bg-sky-500/15 border-sky-500/30'   },
  SELL: { label: 'SELL', cls: 'text-red-300  bg-red-500/15 border-red-500/30'   },
}

const STATUS_CFG = {
  COMPLETED: { label: 'COMPLETED', cls: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30' },
  PENDING:   { label: 'PENDING',   cls: 'text-amber-300  bg-amber-500/10  border-amber-500/25'  },
  FAILED:    { label: 'FAILED',    cls: 'text-red-400    bg-red-500/10    border-red-500/20'    },
}

function Badge({ cfg }) {
  if (!cfg) return null
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border', cfg.cls)}>
      {cfg.label}
    </span>
  )
}

function SummaryCard({ label, value, valueClass = 'text-white', sub }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <p className="text-xs uppercase tracking-widest text-zinc-500">{label}</p>
      <p className={clsx('mt-2 text-2xl font-semibold', valueClass)}>{value}</p>
      {sub && <p className="text-xs text-zinc-600 mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Watchlist Modal ───────────────────────────────────────────────────────────

function WatchlistModal({ initial, watchlistSymbols, onSave, onClose }) {
  const isEdit = !!initial
  const [form, setForm] = useState({
    symbol: initial?.symbol ?? '',
    target_buy_price: initial?.target_buy_price ?? '',
    target_sell_price: initial?.target_sell_price ?? '',
    notes: initial?.notes ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    try {
      const payload = {
        symbol: form.symbol.toUpperCase().trim(),
        target_buy_price: form.target_buy_price ? Number(form.target_buy_price) : null,
        target_sell_price: form.target_sell_price ? Number(form.target_sell_price) : null,
        notes: form.notes || null,
      }
      if (isEdit) {
        await spotApi.updateWatchlist(initial.id, payload)
      } else {
        await spotApi.addWatchlist(payload)
      }
      onSave()
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || 'Gagal menyimpan')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalBackdrop onClose={onClose}>
      <h2 className="text-base font-bold text-white mb-4">
        {isEdit ? 'Edit Target Harga' : 'Tambah Token ke Watchlist'}
      </h2>
      {err && <p className="mb-3 text-sm text-red-400">{err}</p>}
      <form onSubmit={handleSubmit} className="space-y-3">
        <Field label="Symbol">
          <input
            className={INPUT}
            value={form.symbol}
            onChange={e => set('symbol', e.target.value)}
            placeholder="ARB, UNI, GMX …"
            required
            disabled={isEdit}
          />
        </Field>
        <Field label="Target Beli ($)">
          <input
            type="number" step="any" min="0"
            className={INPUT}
            value={form.target_buy_price}
            onChange={e => set('target_buy_price', e.target.value)}
            placeholder="Opsional"
          />
        </Field>
        <Field label="Target Jual ($)">
          <input
            type="number" step="any" min="0"
            className={INPUT}
            value={form.target_sell_price}
            onChange={e => set('target_sell_price', e.target.value)}
            placeholder="Opsional"
          />
        </Field>
        <Field label="Notes">
          <input
            className={INPUT}
            value={form.notes}
            onChange={e => set('notes', e.target.value)}
            placeholder="Opsional"
          />
        </Field>
        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={saving} className={BTN_PRIMARY}>
            {saving ? 'Menyimpan…' : 'Simpan'}
          </button>
          <button type="button" onClick={onClose} className={BTN_GHOST}>Batal</button>
        </div>
      </form>
    </ModalBackdrop>
  )
}

// ── Trade Modal ───────────────────────────────────────────────────────────────

function TradeModal({ preSymbol, watchlistSymbols, onSave, onClose }) {
  const [form, setForm] = useState({
    symbol: preSymbol ?? '',
    trade_type: 'BUY',
    amount_in: '',
    price_at_trade: '',
    price_target: '',
    tx_hash: '',
    notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    try {
      const sym = form.symbol.toUpperCase().trim()
      const payload = {
        symbol: sym,
        base_token: sym,
        quote_token: 'USDC',
        trade_type: form.trade_type,
        amount_in: Number(form.amount_in),
        price_at_trade: Number(form.price_at_trade),
        price_target: form.price_target ? Number(form.price_target) : null,
        tx_hash: form.tx_hash || null,
        notes: form.notes || null,
      }
      await spotApi.createTrade(payload)
      onSave()
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || 'Gagal menyimpan')
    } finally {
      setSaving(false)
    }
  }

  const isBuy = form.trade_type === 'BUY'

  return (
    <ModalBackdrop onClose={onClose}>
      <h2 className="text-base font-bold text-white mb-4">Catat Trade Baru</h2>
      {err && <p className="mb-3 text-sm text-red-400">{err}</p>}
      <form onSubmit={handleSubmit} className="space-y-3">
        <Field label="Symbol">
          {watchlistSymbols.length > 0 ? (
            <div className="flex gap-2">
              <select
                className={INPUT}
                value={watchlistSymbols.includes(form.symbol) ? form.symbol : '__manual__'}
                onChange={e => {
                  if (e.target.value !== '__manual__') set('symbol', e.target.value)
                  else set('symbol', '')
                }}
              >
                {watchlistSymbols.map(s => <option key={s} value={s}>{s}</option>)}
                <option value="__manual__">— input manual —</option>
              </select>
              {(!watchlistSymbols.includes(form.symbol) || form.symbol === '') && (
                <input
                  className={INPUT}
                  value={form.symbol}
                  onChange={e => set('symbol', e.target.value)}
                  placeholder="Contoh: ARB"
                  required
                />
              )}
            </div>
          ) : (
            <input
              className={INPUT}
              value={form.symbol}
              onChange={e => set('symbol', e.target.value)}
              placeholder="Contoh: ARB"
              required
            />
          )}
        </Field>

        <Field label="Tipe">
          <div className="flex gap-2">
            {['BUY', 'SELL'].map(t => (
              <button
                key={t}
                type="button"
                onClick={() => set('trade_type', t)}
                className={clsx(
                  'flex-1 py-1.5 rounded-lg text-sm font-semibold border transition-colors',
                  form.trade_type === t
                    ? t === 'BUY'
                      ? 'bg-sky-500/20 border-sky-500/40 text-sky-300'
                      : 'bg-red-500/20 border-red-500/40 text-red-300'
                    : 'border-zinc-700 text-zinc-500 hover:border-zinc-600'
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </Field>

        <Field label={`Amount In (${isBuy ? 'USDC' : 'Token'})`}>
          <input
            type="number" step="any" min="0"
            className={INPUT}
            value={form.amount_in}
            onChange={e => set('amount_in', e.target.value)}
            required
          />
        </Field>

        <Field label="Harga saat Trade ($)">
          <input
            type="number" step="any" min="0"
            className={INPUT}
            value={form.price_at_trade}
            onChange={e => set('price_at_trade', e.target.value)}
            required
          />
        </Field>

        {isBuy && (
          <Field label="Target Jual ($) — opsional">
            <input
              type="number" step="any" min="0"
              className={INPUT}
              value={form.price_target}
              onChange={e => set('price_target', e.target.value)}
            />
          </Field>
        )}

        <Field label="TX Hash — opsional">
          <input
            className={INPUT}
            value={form.tx_hash}
            onChange={e => set('tx_hash', e.target.value)}
            placeholder="0x…"
          />
        </Field>

        <Field label="Notes — opsional">
          <input
            className={INPUT}
            value={form.notes}
            onChange={e => set('notes', e.target.value)}
          />
        </Field>

        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={saving} className={BTN_PRIMARY}>
            {saving ? 'Menyimpan…' : 'Submit'}
          </button>
          <button type="button" onClick={onClose} className={BTN_GHOST}>Batal</button>
        </div>
      </form>
    </ModalBackdrop>
  )
}

// ── Shared primitives ─────────────────────────────────────────────────────────

function ModalBackdrop({ children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md bg-zinc-900 border border-zinc-700 rounded-2xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-200 transition-colors"
        >
          <X size={16} />
        </button>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-zinc-500 mb-1">{label}</label>
      {children}
    </div>
  )
}

const INPUT = 'w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500 transition-colors'
const BTN_PRIMARY = 'flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold py-2 rounded-lg transition-colors'
const BTN_GHOST = 'flex-1 border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm font-semibold py-2 rounded-lg transition-colors'

// ── Token Detail / Buy Panel ──────────────────────────────────────────────────

function TokenDetailModal({ item, onClose, onDone }) {
  const [analysis, setAnalysis] = useState(null)
  const [loadingAI, setLoadingAI] = useState(true)
  const [defiSupported, setDefiSupported] = useState(null) // null=checking, true, false

  const [amount, setAmount] = useState('')
  const [entryPrice, setEntryPrice] = useState(item.price ? String(item.price) : '')
  const [slPrice, setSlPrice] = useState('')
  const [tpPrice, setTpPrice] = useState(item.target_sell_price ? String(item.target_sell_price) : '')
  const [autoTp, setAutoTp] = useState(!!item.target_sell_price)
  const [execMode, setExecMode] = useState('record') // 'record' | 'defi'
  const [submitting, setSubmitting] = useState(false)
  const [submitErr, setSubmitErr] = useState(null)
  const [submitOk, setSubmitOk] = useState(false)

  useEffect(() => {
    defiApi.checkSupport(`${item.symbol}USDT`)
      .then(res => setDefiSupported(res.data.supported))
      .catch(() => setDefiSupported(false))
  }, [item.symbol])

  useEffect(() => {
    aiApi.getLatest(`${item.symbol}USDT`)
      .then(res => {
        const a = res.data
        setAnalysis(a)
        if (a.suggested_entry) setEntryPrice(String(a.suggested_entry))
        if (a.suggested_sl)    setSlPrice(String(a.suggested_sl))
        if (!tpPrice && a.suggested_tp) setTpPrice(String(a.suggested_tp))
      })
      .catch(() => {
        const p = item.price || 0
        if (!entryPrice) setEntryPrice(String(p))
        setSlPrice(String(Math.round(p * 0.97 * 1e8) / 1e8))
        if (!tpPrice) setTpPrice(String(Math.round(p * 1.05 * 1e8) / 1e8))
      })
      .finally(() => setLoadingAI(false))
  }, [item.symbol]) // eslint-disable-line

  const handleBuy = async () => {
    if (!amount || !entryPrice) { setSubmitErr('Amount dan Entry Price wajib diisi'); return }
    setSubmitting(true)
    setSubmitErr(null)
    try {
      // 1. Record spot trade
      await spotApi.createTrade({
        symbol: item.symbol,
        base_token: item.symbol,
        quote_token: 'USDC',
        trade_type: 'BUY',
        amount_in: Number(amount),
        price_at_trade: Number(entryPrice),
        price_target: autoTp && tpPrice ? Number(tpPrice) : null,
        notes: analysis
          ? `AI: ${analysis.recommended_action}, conf ${Math.round((analysis.confidence||0)*100)}%`
          : null,
      })

      // 2. Auto TP → update watchlist target_sell_price so Celery monitors it
      if (autoTp && tpPrice) {
        await spotWatchlistApi.update(item.id, { target_sell_price: Number(tpPrice) })
      }

      // 3. DeFi execute (optional)
      if (execMode === 'defi') {
        await defiApi.swap({
          symbol: `${item.symbol}USDT`,
          direction: 'buy',
          amount_usdc: Number(amount),
        })
      }

      setSubmitOk(true)
      setTimeout(() => { onDone(); onClose() }, 1500)
    } catch (e) {
      setSubmitErr(e.response?.data?.detail || e.message || 'Gagal submit')
    } finally {
      setSubmitting(false)
    }
  }

  const actionStyle = analysis
    ? (analysis.recommended_action === 'BUY'
        ? 'text-emerald-400' : analysis.recommended_action === 'SELL'
        ? 'text-red-400' : 'text-amber-300')
    : 'text-zinc-400'

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-0 sm:p-4">
      <div className="relative w-full sm:max-w-2xl bg-zinc-900 border border-zinc-700 rounded-t-2xl sm:rounded-2xl shadow-2xl max-h-[92vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-zinc-900 border-b border-zinc-800 px-5 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-base font-bold text-white">{item.symbol}</h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              ${fmt(item.price, 6)} · {item.change_24h != null ? `${item.change_24h >= 0 ? '+' : ''}${fmt(item.change_24h)}%` : '—'}
            </p>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200 transition-colors p-1">
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* AI Analysis */}
          <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Brain size={14} className="text-indigo-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">AI Analysis</span>
            </div>
            {loadingAI ? (
              <p className="text-xs text-zinc-500">Mengambil analisis AI…</p>
            ) : analysis ? (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-3">
                  <span className={clsx('text-sm font-bold', actionStyle)}>
                    {analysis.recommended_action}
                  </span>
                  <span className="text-xs text-zinc-400">
                    Confidence {Math.round((analysis.confidence||0)*100)}%
                  </span>
                  <span className="text-xs text-zinc-400">Trend: {analysis.trend}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  <div className="bg-zinc-800/60 rounded-lg p-2">
                    <p className="text-[10px] text-zinc-500">AI Entry</p>
                    <p className="text-xs font-semibold text-white">${fmt(analysis.suggested_entry, 6)}</p>
                  </div>
                  <div className="bg-red-500/10 rounded-lg p-2">
                    <p className="text-[10px] text-red-400">Stop Loss</p>
                    <p className="text-xs font-semibold text-white">${fmt(analysis.suggested_sl, 6)}</p>
                  </div>
                  <div className="bg-emerald-500/10 rounded-lg p-2">
                    <p className="text-[10px] text-emerald-400">Take Profit</p>
                    <p className="text-xs font-semibold text-white">${fmt(analysis.suggested_tp, 6)}</p>
                  </div>
                </div>
                {analysis.analysis_text && (
                  <p className="text-xs text-zinc-400 mt-2 leading-relaxed line-clamp-3">
                    {analysis.analysis_text}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-xs text-zinc-500">
                Belum ada analisis AI. Entry/SL/TP dihitung dari harga saat ini.
              </p>
            )}
          </div>

          {/* Buy Form */}
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Form Beli</p>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Amount USDC">
                <input type="number" step="any" min="0" className={INPUT}
                  value={amount} onChange={e => setAmount(e.target.value)} placeholder="100" />
              </Field>
              <Field label="Harga Entry ($)">
                <input type="number" step="any" min="0" className={INPUT}
                  value={entryPrice} onChange={e => setEntryPrice(e.target.value)} />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Stop Loss ($)">
                <div className="relative">
                  <ShieldAlert size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-red-400" />
                  <input type="number" step="any" min="0"
                    className={INPUT + ' pl-8'}
                    value={slPrice} onChange={e => setSlPrice(e.target.value)} />
                </div>
              </Field>
              <Field label="Take Profit ($)">
                <div className="relative">
                  <Target size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-400" />
                  <input type="number" step="any" min="0"
                    className={INPUT + ' pl-8'}
                    value={tpPrice} onChange={e => setTpPrice(e.target.value)} />
                </div>
              </Field>
            </div>

            {/* Auto TP toggle */}
            <button
              type="button"
              onClick={() => setAutoTp(v => !v)}
              className={clsx(
                'w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-colors',
                autoTp
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                  : 'border-zinc-700 bg-zinc-800/40 text-zinc-400'
              )}
            >
              <div className="flex items-center gap-2">
                {autoTp ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                <div className="text-left">
                  <p className="text-sm font-semibold">Auto Take Profit</p>
                  <p className="text-xs opacity-70 mt-0.5">
                    {autoTp
                      ? 'Bot kirim alert Telegram saat harga menyentuh TP'
                      : 'TP hanya dicatat, tidak dimonitor otomatis'}
                  </p>
                </div>
              </div>
            </button>

            {/* Execute mode */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setExecMode('record')}
                className={clsx(
                  'flex-1 flex flex-col items-center py-2.5 px-3 rounded-xl border text-xs transition-colors',
                  execMode === 'record'
                    ? 'border-indigo-500/50 bg-indigo-500/15 text-indigo-300'
                    : 'border-zinc-700 text-zinc-500 hover:border-zinc-600'
                )}
              >
                <span className="font-semibold">Catat Saja</span>
                <span className="opacity-60 mt-0.5">Tidak eksekusi onchain</span>
              </button>
              <button
                type="button"
                disabled={defiSupported === false}
                onClick={() => defiSupported !== false && setExecMode('defi')}
                title={defiSupported === false ? 'Token ini tidak tersedia di DEX manapun' : undefined}
                className={clsx(
                  'flex-1 flex flex-col items-center py-2.5 px-3 rounded-xl border text-xs transition-colors',
                  defiSupported === false
                    ? 'border-zinc-800 bg-zinc-800/20 text-zinc-700 cursor-not-allowed'
                    : execMode === 'defi'
                      ? 'border-indigo-500/50 bg-indigo-500/15 text-indigo-300'
                      : 'border-zinc-700 text-zinc-500 hover:border-zinc-600'
                )}
              >
                <span className="font-semibold">
                  DeFi Swap
                  {defiSupported === null && ' …'}
                  {defiSupported === false && ' (N/A)'}
                </span>
                <span className="opacity-60 mt-0.5">
                  {defiSupported === false ? 'Tidak ada DEX pool' : 'Beli langsung via DEX'}
                </span>
              </button>
            </div>
          </div>

          {submitErr && (
            <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">
              {submitErr}
            </p>
          )}

          {submitOk && (
            <p className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-4 py-2">
              ✓ Trade tercatat{execMode === 'defi' ? ' & DeFi swap dikirim' : ''}{autoTp ? ' · Auto TP aktif' : ''}
            </p>
          )}

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleBuy}
              disabled={submitting || submitOk}
              className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-bold py-3 rounded-xl transition-colors"
            >
              <Zap size={15} />
              {submitting ? 'Memproses…' : 'Beli Sekarang'}
            </button>
            <button onClick={onClose} className="px-6 border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm font-semibold rounded-xl transition-colors">
              Batal
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SpotTrading() {
  const [summary, setSummary] = useState(null)
  const [signals, setSignals] = useState([])
  const [trades, setTrades] = useState([])

  const [loadingSummary, setLoadingSummary] = useState(true)
  const [loadingSignals, setLoadingSignals] = useState(true)
  const [loadingTrades, setLoadingTrades] = useState(true)

  const [watchlistModal, setWatchlistModal] = useState(null) // null | 'add' | item
  const [tradeModal, setTradeModal] = useState(null)         // null | '' | symbol string
  const [deleteId, setDeleteId] = useState(null)
  const [tokenDetail, setTokenDetail] = useState(null)       // null | signal item

  const signalTimerRef = useRef(null)

  const fetchSummary = useCallback(async () => {
    try {
      const res = await spotApi.getSummary()
      setSummary(res.data)
    } catch { /* ignore */ }
    finally { setLoadingSummary(false) }
  }, [])

  const fetchSignals = useCallback(async () => {
    setLoadingSignals(true)
    try {
      const res = await spotApi.getSignals()
      setSignals(res.data.signals ?? [])
    } catch { /* ignore */ }
    finally { setLoadingSignals(false) }
  }, [])

  const fetchTrades = useCallback(async () => {
    try {
      const res = await spotApi.listTrades({ limit: 100 })
      setTrades(res.data)
    } catch { /* ignore */ }
    finally { setLoadingTrades(false) }
  }, [])

  useEffect(() => {
    fetchSummary()
    fetchSignals()
    fetchTrades()
  }, [fetchSummary, fetchSignals, fetchTrades])

  useEffect(() => {
    signalTimerRef.current = setInterval(fetchSignals, 60_000)
    return () => clearInterval(signalTimerRef.current)
  }, [fetchSignals])

  const handleWatchlistSaved = () => {
    setWatchlistModal(null)
    fetchSignals()
  }

  const handleTradeSaved = () => {
    setTradeModal(null)
    fetchTrades()
    fetchSummary()
  }

  const handleDeleteWatchlist = async (id) => {
    try {
      await spotApi.deleteWatchlist(id)
      fetchSignals()
    } catch { /* ignore */ }
    setDeleteId(null)
  }

  const watchlistSymbols = signals.map(s => s.symbol)

  const pnlColor = (v) =>
    v == null ? 'text-white' : v >= 0 ? 'text-emerald-400' : 'text-red-400'

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <TrendingUp size={20} className="text-indigo-400" />
            Spot Trading
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Pantau watchlist & catat transaksi spot token
          </p>
        </div>
        <button
          onClick={() => { fetchSummary(); fetchSignals(); fetchTrades() }}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-300 hover:bg-zinc-700 transition-colors"
        >
          <RefreshCw size={13} />
          Refresh
        </button>
      </div>

      {/* ── Section 1: Summary Cards ── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <SummaryCard
          label="Total Invested"
          value={loadingSummary ? '…' : `$${fmt(summary?.total_invested)}`}
        />
        <SummaryCard
          label="Current Value"
          value={loadingSummary ? '…' : `$${fmt(summary?.current_value)}`}
        />
        <SummaryCard
          label="Total PnL"
          value={loadingSummary ? '…' : `$${fmt(summary?.total_pnl)}`}
          valueClass={loadingSummary ? 'text-white' : pnlColor(summary?.total_pnl)}
        />
        <SummaryCard
          label="Win Rate"
          value={loadingSummary ? '…' : `${fmt((summary?.win_rate ?? 0) * 100)}%`}
          sub={summary ? `${summary.total_trades} trades` : undefined}
        />
      </div>

      {/* ── Section 2: Watchlist ── */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-white">Watchlist</h2>
          <div className="flex items-center gap-2">
            {loadingSignals && <RefreshCw size={12} className="text-zinc-500 animate-spin" />}
            <button
              onClick={() => setWatchlistModal('add')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
            >
              <Plus size={12} /> Tambah Token
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left">
                {['Symbol', 'Harga', '24h%', 'Sinyal', 'Target Beli', 'Target Jual', 'Aksi'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {signals.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-zinc-600 text-sm">
                    {loadingSignals ? 'Memuat…' : 'Watchlist kosong. Tambah token dulu.'}
                  </td>
                </tr>
              )}
              {signals.map(item => {
                const sigCfg = SIGNAL_CFG[item.signal] ?? SIGNAL_CFG.UNKNOWN
                const change = item.change_24h
                return (
                  <tr
                    key={item.id}
                    onClick={() => setTokenDetail(item)}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3 font-semibold text-white">{item.symbol}</td>
                    <td className="px-4 py-3 text-zinc-300">
                      {item.price != null ? `$${fmt(item.price, 4)}` : '—'}
                    </td>
                    <td className={clsx('px-4 py-3 font-medium', change == null ? 'text-zinc-600' : change >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {change != null ? `${change >= 0 ? '+' : ''}${fmt(change)}%` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge cfg={sigCfg} />
                    </td>
                    <td className="px-4 py-3 text-zinc-400">
                      {item.target_buy_price ? `$${fmt(item.target_buy_price, 4)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">
                      {item.target_sell_price ? `$${fmt(item.target_sell_price, 4)}` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={(e) => { e.stopPropagation(); setTokenDetail(item) }}
                          className="px-2.5 py-1 text-xs font-semibold bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded-md hover:bg-emerald-500/25 transition-colors"
                        >
                          Beli
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setWatchlistModal(item) }}
                          className="p-1.5 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-700 rounded-md transition-colors"
                          title="Edit target"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setDeleteId(item.id) }}
                          className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
                          title="Hapus"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Section 3: Trade History ── */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-white">Riwayat Spot Trades</h2>
          <button
            onClick={() => setTradeModal('')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
          >
            <Plus size={12} /> Catat Trade Baru
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left">
                {['Tanggal', 'Symbol', 'Type', 'Amount In', 'Amount Out', 'Harga', 'PnL', 'Status', 'TX Hash'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loadingTrades && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-zinc-600 text-sm">Memuat…</td>
                </tr>
              )}
              {!loadingTrades && trades.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-zinc-600 text-sm">
                    Belum ada trade tercatat.
                  </td>
                </tr>
              )}
              {trades.filter(t => t.status !== 'PENDING').map(t => {
                const typeCfg = TYPE_CFG[t.trade_type] ?? TYPE_CFG.BUY
                const statusCfg = STATUS_CFG[t.status] ?? STATUS_CFG.PENDING
                const date = t.created_at
                  ? new Date(t.created_at).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: '2-digit' })
                  : '—'
                return (
                  <tr key={t.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                    <td className="px-4 py-3 text-zinc-400 whitespace-nowrap">{date}</td>
                    <td className="px-4 py-3 font-semibold text-white">{t.symbol}</td>
                    <td className="px-4 py-3"><Badge cfg={typeCfg} /></td>
                    <td className="px-4 py-3 text-zinc-300">{fmt(t.amount_in, 4)}</td>
                    <td className="px-4 py-3 text-zinc-400">{t.amount_out != null ? fmt(t.amount_out, 4) : '—'}</td>
                    <td className="px-4 py-3 text-zinc-400">
                      {t.price_at_trade != null ? `$${fmt(t.price_at_trade, 6)}` : '—'}
                    </td>
                    <td className={clsx('px-4 py-3 font-medium', t.pnl == null ? 'text-zinc-600' : t.pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {t.pnl != null ? `$${fmt(t.pnl, 4)}` : '—'}
                    </td>
                    <td className="px-4 py-3"><Badge cfg={statusCfg} /></td>
                    <td className="px-4 py-3">
                      {t.tx_hash ? (
                        <a
                          href={`https://arbiscan.io/tx/${t.tx_hash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 transition-colors text-xs"
                        >
                          {t.tx_hash.slice(0, 8)}…
                          <ExternalLink size={11} />
                        </a>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Modals ── */}
      {(watchlistModal === 'add' || (watchlistModal && watchlistModal !== 'add')) && (
        <WatchlistModal
          initial={watchlistModal === 'add' ? null : watchlistModal}
          watchlistSymbols={watchlistSymbols}
          onSave={handleWatchlistSaved}
          onClose={() => setWatchlistModal(null)}
        />
      )}

      {tradeModal !== null && (
        <TradeModal
          preSymbol={tradeModal || ''}
          watchlistSymbols={watchlistSymbols}
          onSave={handleTradeSaved}
          onClose={() => setTradeModal(null)}
        />
      )}

      {deleteId !== null && (
        <ModalBackdrop onClose={() => setDeleteId(null)}>
          <h2 className="text-base font-bold text-white mb-2">Hapus dari Watchlist?</h2>
          <p className="text-sm text-zinc-400 mb-4">Token ini akan dihapus dari watchlist kamu.</p>
          <div className="flex gap-2">
            <button
              onClick={() => handleDeleteWatchlist(deleteId)}
              className="flex-1 bg-red-600 hover:bg-red-500 text-white text-sm font-semibold py-2 rounded-lg transition-colors"
            >
              Hapus
            </button>
            <button onClick={() => setDeleteId(null)} className={BTN_GHOST}>Batal</button>
          </div>
        </ModalBackdrop>
      )}

      {tokenDetail && (
        <TokenDetailModal
          item={tokenDetail}
          onClose={() => setTokenDetail(null)}
          onDone={() => { fetchTrades(); fetchSummary(); fetchSignals() }}
        />
      )}
    </div>
  )
}
