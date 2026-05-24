import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Loader2, XCircle, Zap, CheckCircle2, Circle, Brain, ShieldCheck, BarChart3 } from 'lucide-react'
import { authApi } from '../services/api'

const FEATURES = [
  { icon: Brain, title: 'AI Probability Analysis', desc: 'DeepSeek AI membaca momentum market Polymarket secara berkala' },
  { icon: ShieldCheck, title: 'Risk Management', desc: 'Strategy SL/TP, loss limit, dan tracking drawdown' },
  { icon: BarChart3, title: 'Real-time Dashboard', desc: 'Monitor strategy stats, signals, dan riwayat market' },
]

function PasswordStrength({ password }) {
  const checks = [
    { label: 'Min 8 karakter', ok: password.length >= 8 },
    { label: 'Huruf besar (A-Z)', ok: /[A-Z]/.test(password) },
    { label: 'Angka (0-9)', ok: /[0-9]/.test(password) },
  ]
  if (!password) return null
  return (
    <div className="mt-2 space-y-1">
      {checks.map((c) => (
        <div key={c.label} className="flex items-center gap-2 text-xs">
          {c.ok
            ? <CheckCircle2 size={12} className="text-emerald-400 shrink-0" />
            : <Circle size={12} className="text-zinc-600 shrink-0" />
          }
          <span className={c.ok ? 'text-zinc-400' : 'text-zinc-600'}>{c.label}</span>
        </div>
      ))}
    </div>
  )
}

export default function Register() {
  const [form, setForm] = useState({ email: '', username: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirm) { setError('Password tidak cocok'); return }
    if (form.password.length < 8) { setError('Password minimal 8 karakter'); return }
    if (!/[A-Z]/.test(form.password)) { setError('Password harus ada huruf besar'); return }
    if (!/[0-9]/.test(form.password)) { setError('Password harus ada angka'); return }

    setLoading(true)
    try {
      await authApi.register({ email: form.email, username: form.username, password: form.password })
      navigate('/login', { state: { registered: true } })
    } catch (e) {
      const detail = e.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg?.replace('Value error, ', '') || d.msg).join(' · '))
      } else {
        setError(typeof detail === 'string' ? detail : e.response?.data?.error || 'Registrasi gagal')
      }
    } finally {
      setLoading(false)
    }
  }

  const passwordOk =
    form.password.length >= 8 && /[A-Z]/.test(form.password) && /[0-9]/.test(form.password)

  const confirmMatch = form.confirm && form.confirm === form.password
  const confirmMismatch = form.confirm && form.confirm !== form.password

  return (
    <div className="min-h-screen bg-zinc-950 flex">
      <div className="hidden lg:flex lg:w-[480px] xl:w-[520px] bg-gradient-to-b from-zinc-900 to-zinc-950 border-r border-zinc-800/60 flex-col justify-between p-10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-indigo-500 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Zap size={17} className="text-white" strokeWidth={2.5} />
          </div>
          <span className="text-lg font-bold text-white">TradingBot</span>
        </div>

        <div>
          <div className="space-y-3 mb-10">
            {FEATURES.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-4 bg-zinc-800/50 border border-zinc-700/40 rounded-2xl p-4">
                <div className="shrink-0 w-9 h-9 bg-indigo-500/15 border border-indigo-500/20 rounded-xl flex items-center justify-center">
                  <Icon size={16} className="text-indigo-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{title}</p>
                  <p className="text-xs text-zinc-500 mt-0.5 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
          <h2 className="text-3xl font-bold text-white mb-3 leading-tight">
            Trading lebih cerdas<br />dengan sinyal prediction market.
          </h2>
          <p className="text-sm text-zinc-500 leading-relaxed">Gabung sekarang dan mulai eksplorasi data Polymarket dengan AI.</p>
        </div>

        <p className="text-xs text-zinc-700">© 2026 TradingBot. Polymarket strategy dashboard.</p>
      </div>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">
              <Zap size={15} className="text-white" strokeWidth={2.5} />
            </div>
            <span className="text-base font-bold text-white">TradingBot</span>
          </div>

          <h1 className="text-2xl font-bold text-white mb-1">Buat akun baru</h1>
          <p className="text-sm text-zinc-500 mb-8">Gratis. Tidak perlu kartu kredit.</p>

          {error && (
            <div className="mb-5 flex items-start gap-2.5 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-xl">
              <XCircle size={15} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Email</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={set('email')}
                className="w-full bg-zinc-900 border border-zinc-700/60 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500/70 focus:ring-1 focus:ring-indigo-500/30 transition-all"
                placeholder="you@example.com"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Username</label>
              <input
                type="text"
                required
                value={form.username}
                onChange={set('username')}
                className="w-full bg-zinc-900 border border-zinc-700/60 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500/70 focus:ring-1 focus:ring-indigo-500/30 transition-all"
                placeholder="min 3 karakter (huruf, angka, _)"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Password</label>
              <input
                type="password"
                required
                value={form.password}
                onChange={set('password')}
                className="w-full bg-zinc-900 border border-zinc-700/60 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500/70 focus:ring-1 focus:ring-indigo-500/30 transition-all"
                placeholder="••••••••"
              />
              <PasswordStrength password={form.password} />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Konfirmasi Password</label>
              <div className="relative">
                <input
                  type="password"
                  required
                  value={form.confirm}
                  onChange={set('confirm')}
                  className={`w-full bg-zinc-900 border rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 transition-all pr-10 ${
                    confirmMismatch
                      ? 'border-red-500/50 focus:border-red-500/70 focus:ring-red-500/20'
                      : confirmMatch
                      ? 'border-emerald-500/50 focus:border-emerald-500/70 focus:ring-emerald-500/20'
                      : 'border-zinc-700/60 focus:border-indigo-500/70 focus:ring-indigo-500/30'
                  }`}
                  placeholder="••••••••"
                />
                {confirmMatch && (
                  <CheckCircle2 size={15} className="absolute right-4 top-1/2 -translate-y-1/2 text-emerald-400" />
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !passwordOk || form.password !== form.confirm}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all text-sm mt-2 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Membuat akun...
                </>
              ) : 'Daftar Sekarang'}
            </button>
          </form>

          <p className="text-center text-sm text-zinc-600 mt-6">
            Sudah punya akun?{' '}
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
              Login
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
