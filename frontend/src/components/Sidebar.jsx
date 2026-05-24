import { NavLink, useNavigate } from 'react-router-dom'
import clsx from 'clsx'

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: '📊' },
  { path: '/active-trades', label: 'Active Trades', icon: '📈' },
  { path: '/trade-history', label: 'Trade History', icon: '📋' },
  { path: '/ai-analysis', label: 'AI Analysis', icon: '🤖' },
  { path: '/risk-settings', label: 'Risk Settings', icon: '🛡️' },
  { path: '/bot-settings', label: 'Bot Settings', icon: '⚙️' },
]

export default function Sidebar() {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login')
  }

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
      <div className="p-6 border-b border-gray-800">
        <h1 className="text-xl font-bold text-indigo-400">⚡ TradingBot</h1>
        <p className="text-xs text-gray-500 mt-1">Polymarket strategy dashboard</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {NAV_ITEMS.map(({ path, label, icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <span>{icon}</span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <button
          onClick={handleLogout}
          className="w-full px-4 py-2 text-sm text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded-lg transition-colors"
        >
          Logout
        </button>
      </div>
    </aside>
  )
}
