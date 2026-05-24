import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(url) {
  const ws = useRef(null)
  const [data, setData] = useState(null)
  const [status, setStatus] = useState('disconnected')
  const reconnectTimer = useRef(null)

  const connect = useCallback(() => {
    if (!url) return
    ws.current = new WebSocket(url)
    setStatus('connecting')

    ws.current.onopen = () => setStatus('connected')
    ws.current.onmessage = (e) => {
      try { setData(JSON.parse(e.data)) } catch {}
    }
    ws.current.onclose = () => {
      setStatus('disconnected')
      reconnectTimer.current = setTimeout(connect, 5000)
    }
    ws.current.onerror = () => ws.current?.close()
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  const send = useCallback((msg) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg))
    }
  }, [])

  return { data, status, send }
}
