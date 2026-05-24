import { useState } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { Loader2, CheckCircle2, XCircle, Zap, BarChart3, Shield, Brain } from 'lucide-react'
import { authApi } from '../services/api'

const STATS = [
  { label: 'Market', value: 'Crypto', color: 'text-indigo-400' },
  { label: 'Signal Bias', value: 'Yes / No', color: 'text-emerald-400' },
  { label: 'Risk / Trade', value: '1%', color: 'text-amber-400' },
  { label: 'Feed', value: 'Polymarket', color: 'text-sky-400' },
]

export default function Login() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const registered = location.state?.registered

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await authApi.login(form)
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('refresh_token', res.data.refresh_token)
      navigate('/')
    } catch (e) {
      const msg = e.response?.data?.detail || e.response?.data?.error || 'Login gagal'
      setError(typeof msg === 'string' ? msg : 'Email atau password salah')
    } finally {
      setLoading(false)
    }
  }

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
          <div className="grid grid-cols-2 gap-3 mb-10">
            {STATS.map((s) => (
              <div key={s.label} className="bg-zinc-800/50 border border-zinc-700/40 rounded-2xl p-4">
                <p className="text-xs text-zinc-500 mb-1.5">{s.label}</p>
                <p className={`text-base font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
          <h2 className="text-3xl font-bold text-white mb-3 leading-tight">
            Prediction market analysis<br />with AI-powered signals.
          </h2>
          <p className="text-sm text-zinc-500 leading-relaxed">
            Track Polymarket probabilities, manage strategy risk, and let AI analyze market momentum in one dashboard.
          </p>
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

          <h1 className="text-2xl font-bold text-white mb-1">Selamat datang kembali</h1>
          <p className="text-sm text-zinc-500 mb-8">Masuk ke dashboard strategy kamu</p>

          {registered && (
            <div className="mb-5 flex items-center gap-2.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm px-4 py-3 rounded-xl">
              <CheckCircle2 size={15} className="shrink-0" />
              Akun berhasil dibuat. Silakan login.
            </div>
          )}

          {error && (
            <div className="mb-5 flex items-center gap-2.5 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-xl">
              <XCircle size={15} className="shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Email</label>
              <input
                type="email"
                required
                autoComplete="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                className="w-full bg-zinc-900 border border-zinc-700/60 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500/70 focus:ring-1 focus:ring-indigo-500/30 transition-all"
                placeholder="you@example.com"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Password</label>
              <input
                type="password"
                required
                autoComplete="current-password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                className="w-full bg-zinc-900 border border-zinc-700/60 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500/70 focus:ring-1 focus:ring-indigo-500/30 transition-all"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all text-sm mt-2 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Logging in...
                </>
              ) : 'Login'}
            </button>
          </form>

          <p className="text-center text-sm text-zinc-600 mt-6">
            Belum punya akun?{' '}
            <Link to="/register" className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
              Daftar gratis
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
