import React, { useEffect } from 'react'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useAgentStore } from '../stores/agentStore'
import { useAPI } from '../hooks/useAPI'
import { Activity, Zap, Database, Server } from 'lucide-react'

export const Dashboard = () => {
  const { stats, agents, tasks } = useAgentStore()
  const { getStats, getAgents, getTasks } = useAPI()

  useEffect(() => {
    const refresh = async () => {
      try {
        const [s, a, t] = await Promise.all([
          getStats(),
          getAgents(),
          getTasks(10)
        ])
        useAgentStore.setState({ stats: s, agents: a, tasks: t })
      } catch (err) {
        console.error('Failed to fetch data:', err)
      }
    }

    refresh()
    const interval = setInterval(refresh, 2000)
    return () => clearInterval(interval)
  }, [])

  const StatCard = ({ icon: Icon, label, value, color }) => (
    <div className="glass rounded-lg p-6 glow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm">{label}</p>
          <p className={`text-3xl font-bold mt-2 ${color}`}>{value}</p>
        </div>
        <Icon size={40} className={`${color} opacity-30`} />
      </div>
    </div>
  )

  const chartData = tasks.slice(0, 10).reverse().map((t, i) => ({
    name: `T${i}`,
    completed: Math.random() * 100
  }))

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">Dashboard Overview</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={Server}
          label="Active Agents"
          value={stats?.agents || 0}
          color="text-neon-green"
        />
        <StatCard
          icon={Database}
          label="Total Tasks"
          value={stats?.tasks || 0}
          color="text-neon-blue"
        />
        <StatCard
          icon={Zap}
          label="Active Daemons"
          value={stats?.daemons || 0}
          color="text-neon-purple"
        />
        <StatCard
          icon={Activity}
          label="Memory (MB)"
          value={stats?.memory || 0}
          color="text-pink-400"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <div className="glass rounded-lg p-6 glow">
          <h3 className="text-lg font-bold mb-4">Task Completion</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="name" stroke="#666" />
              <YAxis stroke="#666" />
              <Tooltip contentStyle={{ background: '#0f1229', border: '1px solid #00ff41' }} />
              <Bar dataKey="completed" fill="#00ff41" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="glass rounded-lg p-6 glow">
          <h3 className="text-lg font-bold mb-4">System Load</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="name" stroke="#666" />
              <YAxis stroke="#666" />
              <Tooltip contentStyle={{ background: '#0f1229', border: '1px solid #00d4ff' }} />
              <Line type="monotone" dataKey="completed" stroke="#00d4ff" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Agents List */}
      <div className="glass rounded-lg p-6 glow">
        <h3 className="text-lg font-bold mb-4">🟢 Active Agents</h3>
        <div className="space-y-3">
          {agents && agents.length > 0 ? (
            agents.map((agent) => (
              <div key={agent.instance_id} className="bg-dark-700 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-neon-green">{agent.name}</p>
                  <p className="text-sm text-gray-400">Instance: {agent.instance_id}</p>
                </div>
                <div className="flex gap-4 text-sm">
                  <span>Memory: <span className="text-neon-blue">{agent.memory}MB</span></span>
                  <span>Tasks: <span className="text-neon-purple">{agent.task_count || 0}</span></span>
                  <span>Uptime: <span className="text-pink-400">{formatUptime(agent.uptime || 0)}</span></span>
                </div>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-center py-8">No agents running</p>
          )}
        </div>
      </div>
    </div>
  )
}

function formatUptime(seconds) {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}
JS_EOF

echo "✅ Dashboard page created"
