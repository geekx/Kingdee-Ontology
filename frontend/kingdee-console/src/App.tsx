import { NavLink, Outlet } from 'react-router-dom'

function App() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
      isActive
        ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
        : 'text-slate-600 hover:bg-slate-200/70 dark:text-slate-300 dark:hover:bg-slate-800'
    }`

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white/80 px-6 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <span className="text-xl">🧭</span>
          <span>Kingdee Console</span>
        </div>
        <nav className="flex gap-1">
          <NavLink to="/" className={linkClass} end>
            Dashboard
          </NavLink>
          <NavLink to="/chat" className={linkClass}>
            对话
          </NavLink>
        </nav>
      </header>
      <main className="flex-1 bg-slate-50 dark:bg-slate-950">
        <Outlet />
      </main>
    </div>
  )
}

export default App
