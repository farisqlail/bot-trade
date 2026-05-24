import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b border-zinc-800/60 flex items-center justify-end px-6 shrink-0 bg-zinc-950">
          <div className="flex items-center gap-4">
            <span className="text-xs text-zinc-600 hidden sm:block">
              {new Date().toLocaleDateString('id-ID', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
            <div className="w-8 h-8 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-xs font-bold text-indigo-300 shrink-0">
              U
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6 bg-zinc-950">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
