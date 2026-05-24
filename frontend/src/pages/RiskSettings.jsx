import { useState, useEffect } from 'react'
import { riskApi, botApi } from '../services/api'
import clsx from 'clsx'

const SEVERITY_COLOR = {
  LOW: 'text-green-400',
  MEDIUM: 'text-yellow-400',
  HIGH: 'text-orange-400',
  CRITICAL: 'text-red-400',
}

export default function RiskSettings() {
  const [riskStatus, setRiskStatus] = useState(null)
  const [events, setEvents] = useState([])
  const [settings, setSettings] = useState(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({})

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
        })
      } catch (e) {
        console.error(e)
      }
    }
    fetchAll()
  }, [])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await botApi.updateSettings(form)
      alert('Risk settings saved')
    } catch (e) {
      alert(e.response?.data?.error || 'Save failed')
    } finally {
      setSaving(false)
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

      <form onSubmit={handleSave} className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="font-semibold mb-4">Risk Parameters</h3>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Risk per Trade (%)" name="risk_percent" />
          <Field label="Max Open Trades" name="max_open_trades" step="1" />
          <Field label="Daily Loss Limit (%)" name="daily_loss_limit_percent" />
          <Field label="Max Drawdown (%)" name="max_drawdown_percent" />
          <Field label="Consecutive Loss Limit" name="consecutive_loss_limit" step="1" />
        </div>
        <button
          type="submit"
          disabled={saving}
          className="mt-4 px-6 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm rounded-lg"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </form>

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
