import { useState, useEffect } from 'react'
import { riskApi, botApi, tuningApi } from '../services/api'
import { Bot, TrendingUp, TrendingDown, Minus, RefreshCw, CheckCircle2, XCircle } from 'lucide-react'
import clsx from 'clsx'

const SEVERITY_COLOR = {
  LOW: 'text-green-400',
  MEDIUM: 'text-yellow-400',
  HIGH: 'text-orange-400',
  CRITICAL: 'text-red-400',
}

const STATUS_STYLE = {
  pending: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  approved: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  rejected: 'text-red-400 bg-red-500/10 border-red-500/20',
  auto_applied: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
  skipped: 'text-gray-500 bg-gray-800/50 border-gray-700',
}

export default function RiskSettings() {
  const [riskStatus, setRiskStatus] = useState(null)
  const [events, setEvents] = useState([])
  const [settings, setSettings] = useState(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({})

  const [tuningHistory, setTuningHistory] = useState([])
  const [pending, setPending] = useState(null)
  const [runningTuning, setRunningTuning] = useState(false)
  const [tuningAction, setTuningAction] = useState(null)

  const loadTuning = async () => {
    try {
      const [histRes, pendRes] = await Promise.all([tuningApi.getHistory(), tuningApi.getPending()])
      setTuningHistory(histRes.data || [])
      setPending(pendRes.data || null)
    } catch {
      // non-critical
    }
  }

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [statusRes, eventsRes, settingsRes] = await Promise.all([
          riskApi.getStatus(),
          riskApi.getEvents({ limit: 20 }),
          botApi.getSettings(),
        ])
        setRiskStatus(statusRes.data)
        setEvents(eventsRes.data)
        setSettings(settingsRes.data)
        setForm({
          risk_percent: settingsRes.data.risk_percent,
          daily_loss_limit_percent: settingsRes.data.daily_loss_limit_percent,
          max_drawdown_percent: settingsRes.data.max_drawdown_percent,
          consecutive_loss_limit: settingsRes.data.consecutive_loss_limit,
          max_open_trades: settingsRes.data.max_open_trades,
          auto_tuning_enabled: settingsRes.data.auto_tuning_enabled ?? false,
          tuning_frequency: settingsRes.data.tuning_frequency ?? 'weekly',
          require_manual_approval_for_tuning: settingsRes.data.require_manual_approval_for_tuning ?? true,
        })
      } catch (e) {
        console.error(e)
      }
    }
    fetchAll()
    loadTuning()
  }, [])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await botApi.updateSettings(form)
      alert('Risk settings saved')
      const res = await botApi.getSettings()
      setSettings(res.data)
    } catch (e) {
      alert(e.response?.data?.error || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleRunTuning = async () => {
    setRunningTuning(true)
    try {
      const res = await tuningApi.runManual()
      alert(res.data ? `Tuning: ${res.data.reason || 'No change needed'}` : 'No change needed')
      await loadTuning()
    } catch (e) {
      alert(e.response?.data?.detail || 'Tuning failed')
    } finally {
      setRunningTuning(false)
    }
  }

  const handleApprove = async (id) => {
    setTuningAction(id)
    try {
      await tuningApi.approve(id)
      await loadTuning()
      const res = await botApi.getSettings()
      setSettings(res.data)
      setForm((f) => ({ ...f, risk_percent: res.data.risk_percent }))
    } catch (e) {
      alert(e.response?.data?.detail || 'Approve failed')
    } finally {
      setTuningAction(null)
    }
  }

  const handleReject = async (id) => {
    setTuningAction(id)
    try {
      await tuningApi.reject(id)
      await loadTuning()
    } catch (e) {
      alert(e.response?.data?.detail || 'Reject failed')
    } finally {
      setTuningAction(null)
    }
  }

  const Field = ({ label, name, type = 'number', step = '0.1' }) => (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input
        type={type}
        step={step}
        value={form[name] ?? ''}
        onChange={(e) => setForm((f) => ({ ...f, [name]: parseFloat(e.target.value) || e.target.value }))}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
      />
    </div>
  )

  const Toggle = ({ label, name }) => (
    <div className="flex items-center justify-between py-3 border-b border-gray-800">
      <span className="text-sm">{label}</span>
      <button
        type="button"
        onClick={() => setForm((f) => ({ ...f, [name]: !f[name] }))}
        className={`relative w-10 h-5 rounded-full transition-colors p-0 overflow-hidden ${form[name] ? 'bg-indigo-600' : 'bg-gray-700'}`}
      >
        <span className={`absolute left-0 top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${form[name] ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </button>
    </div>
  )

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Risk Settings</h2>

      {riskStatus && (
        <div className={clsx(
          'rounded-xl border p-4',
          riskStatus.status === 'SAFE' ? 'border-green-500/30 bg-green-500/5' :
          riskStatus.status === 'WARNING' ? 'border-yellow-500/30 bg-yellow-500/5' :
          'border-red-500/30 bg-red-500/5'
        )}>
          <p className="font-semibold">Current Risk Status: {riskStatus.status}</p>
          <p className="text-sm text-gray-400 mt-1">
            Daily loss: {riskStatus.daily_loss_percent?.toFixed(2)}% /
            Drawdown: {riskStatus.current_drawdown_percent?.toFixed(2)}% /
            Consecutive losses: {riskStatus.consecutive_losses}
          </p>
        </div>
      )}

      {/* Pending Approval Banner */}
      {pending && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-semibold text-amber-300 flex items-center gap-2">
                <Bot size={16} /> Tuning Recommendation Pending Approval
              </p>
              <p className="text-sm text-gray-300 mt-1">
                Risk per trade: <span className="font-mono">{pending.old_risk_percent?.toFixed(2)}%</span>
                {' → '}
                <span className="font-mono font-bold">
                  {pending.new_risk_percent?.toFixed(2)}%
                </span>
                {' '}
                {pending.change_direction === 'increase'
                  ? <TrendingUp size={14} className="inline text-emerald-400" />
                  : <TrendingDown size={14} className="inline text-red-400" />
                }
              </p>
              <p className="text-xs text-gray-500 mt-1">{pending.reason}</p>
              {pending.metrics_snapshot && (
                <p className="text-xs text-gray-600 mt-1">
                  Win rate {(pending.metrics_snapshot.win_rate * 100).toFixed(0)}%  ·
                  PF {pending.metrics_snapshot.profit_factor?.toFixed(2)}  ·
                  {pending.metrics_snapshot.total_trades} trades analyzed
                </p>
              )}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => handleApprove(pending.id)}
                disabled={tuningAction === pending.id}
                className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-sm rounded-lg hover:bg-emerald-500/25 disabled:opacity-50 transition-colors"
              >
                <CheckCircle2 size={14} /> Approve
              </button>
              <button
                onClick={() => handleReject(pending.id)}
                disabled={tuningAction === pending.id}
                className="flex items-center gap-1.5 px-4 py-2 bg-red-500/15 border border-red-500/30 text-red-300 text-sm rounded-lg hover:bg-red-500/25 disabled:opacity-50 transition-colors"
              >
                <XCircle size={14} /> Reject
              </button>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-5">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-4">Risk Parameters</h3>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Risk per Trade (%)" name="risk_percent" />
            <Field label="Max Open Trades" name="max_open_trades" step="1" />
            <Field label="Daily Loss Limit (%)" name="daily_loss_limit_percent" />
            <Field label="Max Drawdown (%)" name="max_drawdown_percent" />
            <Field label="Consecutive Loss Limit" name="consecutive_loss_limit" step="1" />
          </div>
        </div>

        {/* Auto-Tuning Config */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold mb-2 flex items-center gap-2">
            <Bot size={16} className="text-indigo-400" />
            Auto-Tuning
          </h3>
          <p className="text-xs text-gray-500 mb-4">
            Analisis performa trade dan sesuaikan risk_per_trade otomatis berdasarkan win rate, profit factor, dan consecutive losses.
          </p>
          <Toggle label="Enable Auto-Tuning" name="auto_tuning_enabled" />
          {form.auto_tuning_enabled && (
            <>
              <Toggle label="Require Manual Approval (via Telegram / dashboard)" name="require_manual_approval_for_tuning" />
              <div className="mt-4">
                <label className="block text-xs text-gray-500 mb-1">Tuning Frequency</label>
                <select
                  value={form.tuning_frequency || 'weekly'}
                  onChange={(e) => setForm((f) => ({ ...f, tuning_frequency: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
            </>
          )}
        </div>

        <button
          type="submit"
          disabled={saving}
          className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm rounded-lg"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </form>

      {/* Manual Tuning Run */}
      {form.auto_tuning_enabled && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-sm">Run Tuning Now</p>
              <p className="text-xs text-gray-500 mt-0.5">Analisis performa 30 hari terakhir, butuh min 5 closed trades.</p>
            </div>
            <button
              onClick={handleRunTuning}
              disabled={runningTuning}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-sm rounded-lg hover:bg-indigo-500/25 disabled:opacity-50 transition-colors"
            >
              <RefreshCw size={14} className={runningTuning ? 'animate-spin' : ''} />
              {runningTuning ? 'Running...' : 'Run Manual Tuning'}
            </button>
          </div>
        </div>
      )}

      {/* Tuning History */}
      {tuningHistory.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h3 className="font-semibold mb-3">Tuning History</h3>
          <div className="space-y-2">
            {tuningHistory.map((t) => (
              <div key={t.id} className="flex items-start gap-3 py-2.5 border-b border-gray-800/50">
                <span className={clsx(
                  'text-xs font-semibold px-2 py-0.5 rounded-full border shrink-0 mt-0.5',
                  STATUS_STYLE[t.status] || 'text-gray-500 border-gray-700'
                )}>
                  {t.status}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm">
                    {t.old_risk_percent?.toFixed(2)}% → {t.new_risk_percent?.toFixed(2)}%
                    {t.change_direction === 'increase'
                      ? <TrendingUp size={12} className="inline ml-1 text-emerald-400" />
                      : t.change_direction === 'decrease'
                      ? <TrendingDown size={12} className="inline ml-1 text-red-400" />
                      : <Minus size={12} className="inline ml-1 text-gray-500" />
                    }
                  </p>
                  {t.reason && <p className="text-xs text-gray-500 mt-0.5 truncate">{t.reason}</p>}
                </div>
                <span className="text-xs text-gray-600 shrink-0">
                  {new Date(t.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="font-semibold mb-3">Risk Events</h3>
        {events.length === 0 ? (
          <p className="text-gray-500 text-sm">No risk events</p>
        ) : (
          <div className="space-y-2">
            {events.map((e) => (
              <div key={e.id} className="flex items-start gap-3 py-2 border-b border-gray-800/50">
                <span className={clsx('text-xs font-bold w-16', SEVERITY_COLOR[e.severity])}>
                  {e.severity}
                </span>
                <div className="flex-1">
                  <p className="text-sm">{e.title}</p>
                  {e.description && <p className="text-xs text-gray-500">{e.description}</p>}
                </div>
                <span className="text-xs text-gray-600">
                  {new Date(e.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
