import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, TrendingUp, History, Brain, ShieldCheck, Settings2, LogOut, Zap, BarChart2 } from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/active-trades', label: 'Active Trades', icon: TrendingUp },
  { path: '/trade-history', label: 'Trade History', icon: History },
  { path: '/ai-analysis', label: 'AI Analysis', icon: Brain },
  { path: '/chart', label: 'Smart Chart', icon: BarChart2 },
  { path: '/risk-settings', label: 'Risk Settings', icon: ShieldCheck },
  { path: '/bot-settings', label: 'Bot Settings', icon: Settings2 },
]

export default function Sidebar() {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login')
  }

  return (
    <aside className="w-64 bg-zinc-950 border-r border-zinc-800/60 flex flex-col shrink-0">
      <div className="h-16 px-5 flex items-center gap-3 border-b border-zinc-800/60">
        <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/20">
          <Zap size={15} className="text-white" strokeWidth={2.5} />
        </div>
        <div>
          <p className="text-sm font-bold text-white leading-none">TradingBot</p>
          <p className="text-[10px] text-zinc-500 mt-0.5 leading-none">Polymarket strategy</p>
        </div>
      </div>

      <nav className="flex-1 py-3 px-3 space-y-0.5">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-150 group border',
                isActive
                  ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/25 shadow-sm'
                  : 'text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-100 border-transparent'
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={16}
                  className={clsx('shrink-0 transition-colors', isActive ? 'text-indigo-400' : 'text-zinc-500 group-hover:text-zinc-300')}
                />
                <span className="font-medium">{label}</span>
                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-zinc-800/60">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all duration-150 group"
        >
          <LogOut size={16} className="group-hover:text-red-400 transition-colors" />
          <span className="font-medium">Logout</span>
        </button>
      </div>
    </aside>
  )
}
