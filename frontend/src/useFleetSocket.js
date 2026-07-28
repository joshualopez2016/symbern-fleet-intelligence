import { useEffect, useRef, useState } from 'react'
import { getAuthToken } from './api'

// Connects to the realtime fleet WebSocket and exposes the latest pushed
// snapshot. Auto-reconnects with backoff. Enabled only when authenticated.
export function useFleetSocket(enabled) {
  const [connected, setConnected] = useState(false)
  const [snapshot, setSnapshot] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    if (!enabled) return
    let closed = false
    let reconnectTimer = null

    function connect() {
      const token = getAuthToken()
      if (!token) return
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${window.location.host}/api/ws?token=${encodeURIComponent(token)}`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'snapshot') setSnapshot(msg)
        } catch {
          /* ignore malformed frames */
        }
      }
      ws.onclose = () => {
        setConnected(false)
        if (!closed) reconnectTimer = setTimeout(connect, 2000)
      }
      ws.onerror = () => {
        try { ws.close() } catch { /* noop */ }
      }
    }

    connect()
    return () => {
      closed = true
      clearTimeout(reconnectTimer)
      try { wsRef.current?.close() } catch { /* noop */ }
    }
  }, [enabled])

  return { connected, snapshot }
}
