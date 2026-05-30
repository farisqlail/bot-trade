import { useState } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, History, Brain, ShieldCheck,
  Settings2, LogOut, Zap, BarChart2, Layers, Triangle, Rocket,
  ChevronDown, ScanSearch, Boxes, PieChart
} from 'lucide-react'
import clsx from 'clsx'

const FLAT_TOP = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/portfolio', label: 'Portfolio', icon: PieChart },
  { path: '/active-trades', label: 'Active Trades', icon: TrendingUp },
  { path: '/trade-history', label: 'Trade History', icon: History },
  { path: '/spot', label: 'Spot Trading', icon: TrendingUp },
]

const SCAN_ITEMS = [
  { path: '/ai-analysis', label: 'AI Analysis', icon: Brain },
  { path: '/altcoins', label: 'Altcoin Scanner', icon: Rocket },
  { path: '/chart', label: 'Smart Chart', icon: BarChart2 },
]

const FUTURES_ITEMS = [
  { path: '/futures', label: 'Futures (GMX)', icon: Layers },
  { path: '/gtrade', label: 'Futures (gTrade)', icon: Triangle },
]

const FLAT_BOTTOM = [
  { path: '/risk-settings', label: 'Risk Settings', icon: ShieldCheck },
  { path: '/bot-settings', label: 'Bot Settings', icon: Settings2 },
]

function NavItem({ path, label, icon: Icon, end }) {
  return (
    <NavLink
      to={path}
      end={end}
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
          {isActive && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />}
        </>
      )}
    </NavLink>
  )
}

function CollapseGroup({ label, icon: GroupIcon, items, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  const location = useLocation()
  const hasActive = items.some(i => location.pathname === i.path)

  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className={clsx(
          'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-150 group border',
          hasActive
            ? 'text-indigo-300 border-indigo-500/20 bg-indigo-500/5'
            : 'text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-100 border-transparent'
        )}
      >
        <GroupIcon
          size={16}
          className={clsx('shrink-0 transition-colors', hasActive ? 'text-indigo-400' : 'text-zinc-500 group-hover:text-zinc-300')}
        />
        <span className="font-medium flex-1 text-left">{label}</span>
        <ChevronDown
          size={14}
          className={clsx(
            'shrink-0 transition-transform duration-200',
            open ? 'rotate-0' : '-rotate-90',
            hasActive ? 'text-indigo-400' : 'text-zinc-600 group-hover:text-zinc-400'
          )}
        />
      </button>

      <div
        className={clsx(
          'overflow-hidden transition-all duration-200',
          open ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className="ml-3 mt-0.5 pl-3 border-l border-zinc-800/80 space-y-0.5 pb-0.5">
          {items.map(({ path, label: l, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 group border',
                  isActive
                    ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/25 shadow-sm'
                    : 'text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-100 border-transparent'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    size={15}
                    className={clsx('shrink-0 transition-colors', isActive ? 'text-indigo-400' : 'text-zinc-500 group-hover:text-zinc-300')}
                  />
                  <span className="font-medium">{l}</span>
                  {isActive && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  const scanActive = SCAN_ITEMS.some(i => location.pathname === i.path)
  const futuresActive = FUTURES_ITEMS.some(i => location.pathname === i.path)

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

      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto">
        {FLAT_TOP.map(item => (
          <NavItem key={item.path} {...item} end={item.path === '/'} />
        ))}

        <div className="pt-1">
          <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">Tools</p>
          <div className="space-y-0.5">
            <CollapseGroup
              label="Scan"
              icon={ScanSearch}
              items={SCAN_ITEMS}
              defaultOpen={scanActive}
            />
            <CollapseGroup
              label="Futures"
              icon={Boxes}
              items={FUTURES_ITEMS}
              defaultOpen={futuresActive}
            />
          </div>
        </div>

        <div className="pt-1">
          <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">Config</p>
          <div className="space-y-0.5">
            {FLAT_BOTTOM.map(item => (
              <NavItem key={item.path} {...item} />
            ))}
          </div>
        </div>
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
