import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAgentStore } from '../stores/agentStore'
import { useAPI } from '../hooks/useAPI'
import { play, square, trash2, info } from 'lucide-react'

export const Agents = () => {
  const { agents } = useAgentStore()
  const { getAgents, startAgent, stopAgent } = useAPI()
  const [form, setForm] = useState({ ai_name: '', mode: 'monitor', auto_kill: false, audio: false })

  useEffect(() => {
    const refresh = async () => {
      try {
        const data = await getAgents()
        useAgentStore.setState({ agents: data })
      } catch (err) {
        console.error('Failed to fetch agents:', err)
      }
    }
    refresh()
    const interval = setInterval(refresh, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleStart = async () => {
    if (!form.ai_name.trim()) return
    try {
      await startAgent(form)
      setForm({ ai_name: '', mode: 'monitor', auto_kill: false, audio: false })
      const data = await getAgents()
      useAgentStore.setState({ agents: data })
    } catch (err) {
      console.error('Failed to start agent:', err)
    }
  }

  const handleStop = async (id) => {
    if (!window.confirm('Stop this agent?')) return
    try {
      await stopAgent(id)
      const data = await getAgents()
      useAgentStore.setState({ agents: data })
    } catch (err) {
      console.error('Failed to stop agent:', err)
    }
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">Agent Management</h1>

      <div className="grid grid-cols-2 gap-8">
        {/* Start New Agent */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-lg p-6 glow"
        >
          <h2 className="text-xl font-bold text-neon-green mb-6">🚀 Start New Agent</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">AI Name</label>
              <input
                type="text"
                value={form.ai_name}
                onChange={(e) => setForm({ ...form, ai_name: e.target.value })}
                placeholder="e.g., ProjectAlpha"
                className="w-full bg-dark-700 border border-neon-blue border-opacity-30 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-neon-green transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">Mode</label>
              <select
                value={form.mode}
                onChange={(e) => setForm({ ...form, mode: e.target.value })}
                className="w-full bg-dark-700 border border-neon-blue border-opacity-30 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-neon-green transition-colors"
              >
                <option value="monitor">Monitor (continuous)</option>
                <option value="once">Once (single cycle)</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-3 text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.auto_kill}
                  onChange={(e) => setForm({ ...form, auto_kill: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm">Auto-kill conflicts</span>
              </label>
              <label className="flex items-center gap-3 text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.audio}
                  onChange={(e) => setForm({ ...form, audio: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm">Enable audio notifications</span>
              </label>
            </div>

            <button
              onClick={handleStart}
              className="w-full bg-gradient-to-r from-neon-green to-neon-blue text-dark-900 font-bold py-3 rounded-lg hover:shadow-lg hover:shadow-neon-green/50 transition-all"
            >
              <play size={18} className="inline mr-2" />
              Start Agent
            </button>
          </div>
        </motion.div>

        {/* Active Agents */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass rounded-lg p-6 glow"
        >
          <h2 className="text-xl font-bold text-neon-blue mb-6">🟢 Active Agents ({agents?.length || 0})</h2>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {agents && agents.length > 0 ? (
              agents.map((agent) => (
                <motion.div
                  key={agent.instance_id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="bg-dark-700 rounded-lg p-4 border border-neon-green border-opacity-30 hover:border-opacity-100 transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-semibold text-neon-green flex items-center gap-2">
                        <span className="w-2 h-2 bg-neon-green rounded-full animate-pulse"></span>
                        {agent.name}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">{agent.instance_id}</p>
                    </div>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      agent.status === 'online'
                        ? 'bg-neon-green bg-opacity-20 text-neon-green'
                        : 'bg-red-500 bg-opacity-20 text-red-400'
                    }`}>
                      {agent.status}
                    </span>
                  </div>

                  <div className="text-xs text-gray-400 space-y-1 mb-3">
                    <p>Ports: Vision:{agent.vision_port} Browser:{agent.browser_port} Webhook:{agent.webhook_port}</p>
                    <p>Memory: {agent.memory}MB | Tasks: {agent.task_count || 0} | Uptime: {formatUptime(agent.uptime || 0)}</p>
                  </div>

                  <div className="flex gap-2">
                    <button className="flex-1 flex items-center justify-center gap-2 bg-dark-600 hover:bg-dark-500 rounded px-3 py-2 text-sm transition-colors">
                      <info size={14} />
                      Details
                    </button>
                    <button
                      onClick={() => handleStop(agent.instance_id)}
                      className="flex-1 flex items-center justify-center gap-2 bg-red-500 bg-opacity-20 hover:bg-opacity-30 text-red-400 rounded px-3 py-2 text-sm transition-colors"
                    >
                      <square size={14} />
                      Stop
                    </button>
                  </div>
                </motion.div>
              ))
            ) : (
              <p className="text-gray-500 text-center py-8">No agents running</p>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

function formatUptime(seconds) {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h`
}
JS_EOF

echo "✅ Agents page created"
