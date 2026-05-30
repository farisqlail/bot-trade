import { useEffect, useRef, useState, useCallback, useMemo } from 'react'

function buildWsUrl() {
  const token = localStorage.getItem('access_token')
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  let base
  if (apiUrl.startsWith('http')) {
    base = apiUrl.replace(/^https?/, (p) => (p === 'https' ? 'wss' : 'ws'))
  } else {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    base = `${proto}//${window.location.host}${apiUrl}`
  }
  return `${base}/ws?token=${encodeURIComponent(token || '')}`
}

/**
 * Subscribe to one or more channels on the general WS endpoint.
 *
 * Usage:
 *   const { data, status } = useWsChannel(['dashboard', 'trades'])
 *   const { data, status } = useWsChannel(['prices'], { symbols: ['BTCUSDT', 'ETHUSDT'] })
 *
 * Returns:
 *   data    - object keyed by channel name, e.g. data.dashboard, data.trades
 *   status  - 'connecting' | 'connected' | 'disconnected'
 */
export function useWsChannel(channels, { symbols = [] } = {}) {
  const ws = useRef(null)
  const [channelData, setChannelData] = useState({})
  const [status, setStatus] = useState('disconnected')
  const reconnectTimer = useRef(null)
  const mountedRef = useRef(true)

  // Stable string keys so the effect doesn't re-fire on every render
  const channelsKey = useMemo(() => [...channels].sort().join(','), [channels])
  const symbolsKey = useMemo(() => [...symbols].sort().join(','), [symbols])

  const connect = useCallback(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    const url = buildWsUrl()
    const socket = new WebSocket(url)
    ws.current = socket
    setStatus('connecting')

    socket.onopen = () => {
      setStatus('connected')
      socket.send(JSON.stringify({
        action: 'subscribe',
        channels: channelsKey.split(',').filter(Boolean),
        symbols: symbolsKey ? symbolsKey.split(',') : [],
      }))
    }

    socket.onmessage = (e) => {
      try {
        const { channel, data } = JSON.parse(e.data)
        if (channel && channel !== 'subscribed' && channel !== 'pong') {
          setChannelData((prev) => ({ ...prev, [channel]: data }))
        }
      } catch {}
    }

    socket.onclose = () => {
      if (!mountedRef.current) return
      setStatus('disconnected')
      reconnectTimer.current = setTimeout(connect, 5000)
    }

    socket.onerror = () => socket.close()
  }, [channelsKey, symbolsKey])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  const send = useCallback((msg) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg))
    }
  }, [])

  return { data: channelData, status, send }
}
