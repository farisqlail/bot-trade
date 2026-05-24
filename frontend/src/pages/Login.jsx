import { useState } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { authApi } from '../services/api'

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
    <div className="min-h-screen bg-[#0a0a0f] flex">
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-indigo-950 via-[#0d0d1a] to-[#0a0a0f] flex-col justify-between p-12">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-indigo-500 rounded-xl flex items-center justify-center text-lg font-bold">⚡</div>
          <span className="text-xl font-bold text-white">TradingBot</span>
        </div>
        <div>
          <div className="grid grid-cols-2 gap-4 mb-12">
            {[
              { label: 'Market', value: 'featured', color: 'text-indigo-400' },
              { label: 'Signal Bias', value: 'Yes / No', color: 'text-green-400' },
              { label: 'Risk / Trade', value: '1%', color: 'text-yellow-400' },
              { label: 'Feed', value: 'Polymarket', color: 'text-red-400' },
            ].map((s) => (
              <div key={s.label} className="bg-white/5 rounded-xl p-4 border border-white/10">
                <p className="text-xs text-gray-500 mb-1">{s.label}</p>
                <p className={`text-lg font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
          <h2 className="text-3xl font-bold text-white mb-3">Prediction market analysis<br />with AI-powered signals.</h2>
          <p className="text-gray-500">Track Polymarket probabilities, manage strategy risk, and let AI analyze market momentum in one dashboard.</p>
        </div>
        <p className="text-gray-700 text-sm">© 2026 TradingBot. Polymarket strategy dashboard.</p>
      </div>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">⚡</div>
            <span className="text-lg font-bold text-white">TradingBot</span>
          </div>

          <h1 className="text-2xl font-bold text-white mb-1">Selamat datang kembali</h1>
          <p className="text-gray-500 text-sm mb-8">Masuk ke dashboard strategy kamu</p>

          {registered && (
            <div className="mb-4 flex items-center gap-3 bg-green-500/10 border border-green-500/20 text-green-400 text-sm px-4 py-3 rounded-xl">
              <span className="text-base">✓</span>
              Akun berhasil dibuat. Silakan login.
            </div>
          )}

          {error && (
            <div className="mb-4 flex items-center gap-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-xl">
              <span className="text-base">✕</span>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-400 uppercase tracking-wider">Email</label>
              <input
                type="email"
                required
                autoComplete="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 focus:bg-white/8 transition-all"
                placeholder="you@example.com"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-gray-400 uppercase tracking-wider">Password</label>
              </div>
              <input
                type="password"
                required
                autoComplete="current-password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 focus:bg-white/8 transition-all"
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
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Logging in...
                </>
              ) : 'Login'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-600 mt-6">
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
