import { useCallback } from 'react'
import axios from 'axios'
import { useAgentStore } from '../stores/agentStore'

const API = axios.create({ baseURL: '/api/v1' })

export const useAPI = () => {
  const setError = useAgentStore(s => s.setError)
  const setLoading = useAgentStore(s => s.setLoading)

  const request = useCallback(async (method, url, data = null) => {
    try {
      setLoading(true)
      setError(null)
      const config = { method, url }
      if (data) config.data = data
      const res = await API(config)
      return res.data
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }, [setError, setLoading])

  return {
    getAgents: () => request('get', '/agents'),
    startAgent: (data) => request('post', '/agent/start', data),
    stopAgent: (id) => request('post', `/agent/${id}/stop`),
    getTasks: (limit = 20) => request('get', `/tasks?limit=${limit}`),
    submitTask: (data) => request('post', '/task', data),
    getStats: () => request('get', '/stats'),
    getHealth: () => request('get', '/health'),
  }
}
