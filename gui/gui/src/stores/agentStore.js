import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

export const useAgentStore = create(
  subscribeWithSelector((set) => ({
    agents: [],
    tasks: [],
    stats: null,
    loading: false,
    error: null,
    wsConnected: false,

    setAgents: (agents) => set({ agents }),
    setTasks: (tasks) => set({ tasks }),
    setStats: (stats) => set({ stats }),
    setLoading: (loading) => set({ loading }),
    setError: (error) => set({ error }),
    setWsConnected: (connected) => set({ wsConnected: connected }),

    addTask: (task) => set((state) => ({ 
      tasks: [task, ...state.tasks].slice(0, 50) 
    })),

    updateAgent: (id, data) => set((state) => ({
      agents: state.agents.map(a => a.instance_id === id ? { ...a, ...data } : a)
    })),

    removeAgent: (id) => set((state) => ({
      agents: state.agents.filter(a => a.instance_id !== id)
    })),

    reset: () => set({
      agents: [],
      tasks: [],
      stats: null,
      loading: false,
      error: null
    })
  }))
)
