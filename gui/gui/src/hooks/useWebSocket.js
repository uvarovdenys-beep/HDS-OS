import { useEffect, useRef } from 'react'
import { useAgentStore } from '../stores/agentStore'

export const useWebSocket = (url) => {
  const wsRef = useRef(null)
  const setWsConnected = useAgentStore(s => s.setWsConnected)

  useEffect(() => {
    const connect = () => {
      try {
        const wsUrl = url.replace(/^http/, 'ws')
        wsRef.current = new WebSocket(wsUrl)

        wsRef.current.onopen = () => {
          setWsConnected(true)
          console.log('🔗 WebSocket connected')
        }

        wsRef.current.onclose = () => {
          setWsConnected(false)
          console.log('🔌 WebSocket disconnected')
          setTimeout(connect, 3000)
        }

        wsRef.current.onerror = (err) => {
          console.error('❌ WebSocket error:', err)
        }
      } catch (err) {
        console.error('Failed to connect WebSocket:', err)
      }
    }

    connect()

    return () => {
      if (wsRef.current) wsRef.current.close()
    }
  }, [url, setWsConnected])

  return wsRef.current
}
