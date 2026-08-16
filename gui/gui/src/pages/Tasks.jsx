import React, { useState, useEffect } from 'react'
import { useAgentStore } from '../stores/agentStore'
import { useAPI } from '../hooks/useAPI'
import { send, checkCircle, circle, alertCircle } from 'lucide-react'

export const Tasks = () => {
  const { tasks } = useAgentStore()
  const { getTasks, submitTask } = useAPI()
  const [formData, setFormData] = useState({ type: 'browser', url: '' })

  useEffect(() => {
    const refresh = async () => {
      try {
        const data = await getTasks(50)
        useAgentStore.setState({ tasks: data })
      } catch (err) {
        console.error('Failed to fetch tasks:', err)
      }
    }
    refresh()
    const interval = setInterval(refresh, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleSubmit = async () => {
    if (!formData.url.trim()) return
    try {
      await submitTask(formData)
      setFormData({ type: 'browser', url: '' })
      const data = await getTasks(50)
      useAgentStore.setState({ tasks: data })
    } catch (err) {
      console.error('Failed to submit task:', err)
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'done':
        return <checkCircle size={16} className="text-neon-green" />
      case 'running':
        return <circle size={16} className="text-neon-blue animate-spin" />
      case 'queued':
        return <circle size={16} className="text-yellow-400" />
      case 'error':
        return <alertCircle size={16} className="text-red-400" />
      default:
        return <circle size={16} className="text-gray-400" />
    }
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">Task Management</h1>

      <div className="grid grid-cols-3 gap-8">
        {/* Submit Task */}
        <div className="glass rounded-lg p-6 glow col-span-1">
          <h2 className="text-xl font-bold text-neon-green mb-6">📤 Submit Task</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Task Type</label>
              <select
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                className="w-full bg-dark-700 border border-neon-blue border-opacity-30 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-neon-green"
              >
                <option value="browser">Browser Automation</option>
                <option value="vision">Vision Analysis</option>
                <option value="webhook">Webhook</option>
              </select>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">URL/Command</label>
              <input
                type="text"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                placeholder="https://example.com"
                className="w-full bg-dark-700 border border-neon-blue border-opacity-30 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-neon-green"
              />
            </div>

            <button
              onClick={handleSubmit}
              className="w-full bg-gradient-to-r from-neon-green to-neon-blue text-dark-900 font-bold py-3 rounded-lg hover:shadow-lg hover:shadow-neon-green/50 transition-all"
            >
              <send size={16} className="inline mr-2" />
              Submit Task
            </button>
          </div>
        </div>

        {/* Recent Tasks */}
        <div className="glass rounded-lg p-6 glow col-span-2">
          <h2 className="text-xl font-bold text-neon-blue mb-6">📋 Recent Tasks ({tasks?.length || 0})</h2>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {tasks && tasks.length > 0 ? (
              tasks.map((task) => (
                <div key={task.task_id} className="bg-dark-700 rounded-lg p-3 flex items-center gap-3 hover:bg-opacity-70 transition-colors">
                  {getStatusIcon(task.status || 'queued')}
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-sm text-neon-green truncate">{task.task_id}</p>
                    <p className="text-xs text-gray-400">{task.created_at || 'Just now'}</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${
                    task.status === 'done' ? 'bg-neon-green bg-opacity-20 text-neon-green' :
                    task.status === 'running' ? 'bg-neon-blue bg-opacity-20 text-neon-blue' :
                    task.status === 'error' ? 'bg-red-500 bg-opacity-20 text-red-400' :
                    'bg-yellow-500 bg-opacity-20 text-yellow-400'
                  }`}>
                    {task.status || 'queued'}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-center py-8">No tasks</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
JS_EOF

cat > gui/src/App.jsx << 'JSX_EOF'
import React, { useState, useEffect } from 'react'
import { Sidebar } from './components/Sidebar'
import { Header } from './components/Header'
import { Dashboard } from './pages/Dashboard'
import { Agents } from './pages/Agents'
import { Tasks } from './pages/Tasks'

function App() {
  const [active, setActive] = useState('dashboard')

  const pages = {
    dashboard: <Dashboard />,
    agents: <Agents />,
    tasks: <Tasks />,
    settings: <div className="p-8"><h1 className="text-3xl font-bold">Settings (Coming Soon)</h1></div>
  }

  return (
    <div className="flex h-screen bg-dark-900">
      <Sidebar active={active} setActive={setActive} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto">{pages[active]}</main>
      </div>
    </div>
  )
}

export default App
JS_EOF

cat > gui/src/main.jsx << 'JSX_EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
JS_EOF

cat > gui/index.html << 'HTML_EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HDS Control Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
HTML_EOF

echo "✅ React GUI Complete!"
echo ""
echo "📦 Created files:"
echo "  - src/App.jsx"
echo "  - src/main.jsx"
echo "  - src/components/Sidebar.jsx"
echo "  - src/components/Header.jsx"
echo "  - src/pages/Dashboard.jsx"
echo "  - src/pages/Agents.jsx"
echo "  - src/pages/Tasks.jsx"
echo "  - src/stores/agentStore.js"
echo "  - src/hooks/useAPI.js"
echo "  - src/hooks/useWebSocket.js"
echo "  - src/index.css"
echo "  - vite.config.js"
echo "  - tailwind.config.js"
echo "  - postcss.config.js"
echo "  - package.json"
echo "  - index.html"
