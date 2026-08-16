import React from 'react'
import { activity, settings, zap, database, server } from 'lucide-react'

export const Sidebar = ({ active, setActive }) => {
  const items = [
    { id: 'dashboard', label: 'Dashboard', icon: activity },
    { id: 'agents', label: 'Agents', icon: server },
    { id: 'tasks', label: 'Tasks', icon: database },
    { id: 'settings', label: 'Settings', icon: settings },
  ]

  return (
    <div className="w-64 bg-dark-800 border-r border-neon-blue border-opacity-20 h-screen flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-neon-blue border-opacity-20">
        <h1 className="text-2xl gradient-text font-bold">HDS</h1>
        <p className="text-xs text-gray-400 mt-1">Control Center v1.1</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {items.map((item) => {
          const Icon = item.icon
          const isActive = active === item.id
          return (
            <button
              key={item.id}
              onClick={() => setActive(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                isActive
                  ? 'bg-neon-green bg-opacity-20 text-neon-green border border-neon-green'
                  : 'text-gray-400 hover:text-neon-green hover:bg-dark-700'
              }`}
            >
              <Icon size={18} />
              <span className="font-semibold">{item.label}</span>
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-neon-blue border-opacity-20 text-xs text-gray-500 text-center">
        <p>Ready for production</p>
        <p className="text-neon-green mt-1">●</p>
      </div>
    </div>
  )
}
JS_EOF

cat > gui/src/components/Header.jsx << 'JSX_EOF'
import React from 'react'
import { bell, settings, menu } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'

export const Header = () => {
  const { wsConnected, stats } = useAgentStore()

  return (
    <header className="bg-dark-800 border-b border-neon-blue border-opacity-20 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-bold">Control Center</h2>
          <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
            wsConnected ? 'bg-neon-green bg-opacity-10 text-neon-green' : 'bg-red-500 bg-opacity-10 text-red-400'
          }`}>
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-neon-green' : 'bg-red-400'} animate-pulse`}></div>
            {wsConnected ? 'Connected' : 'Disconnected'}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {stats && (
            <div className="flex gap-6 text-sm">
              <div className="flex flex-col">
                <span className="text-gray-400">Agents</span>
                <span className="text-lg font-bold text-neon-green">{stats.agents || 0}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-gray-400">Tasks</span>
                <span className="text-lg font-bold text-neon-blue">{stats.tasks || 0}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-gray-400">Daemons</span>
                <span className="text-lg font-bold text-neon-purple">{stats.daemons || 0}</span>
              </div>
            </div>
          )}

          <button className="p-2 hover:bg-dark-700 rounded-lg transition-colors">
            <bell size={20} className="text-gray-400 hover:text-neon-green" />
          </button>
          <button className="p-2 hover:bg-dark-700 rounded-lg transition-colors">
            <settings size={20} className="text-gray-400 hover:text-neon-green" />
          </button>
        </div>
      </div>
    </header>
  )
}
JS_EOF

echo "✅ Sidebar and Header components created"
