import { useCallback, useEffect, useRef, useState } from 'react'
import { chartApi } from '../services/api'

function buildWsUrl(symbol) {
  const token = localStorage.getItem('access_token')
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  let base
  if (apiUrl.startsWith('http')) {
    base = apiUrl.replace(/^https?/, (p) => (p === 'https' ? 'wss' : 'ws')).replace('/api/v1', '')
  } else {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    base = `${proto}//${window.location.host}`
  }
  return `${base}/api/v1/chart/ws/${symbol}?token=${encodeURIComponent(token || '')}`
}

export function useChartData(symbol, timeframe = '60') {
  const [bundle, setBundle] = useState(null)
  const [watchlist, setWatchlist] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const loadBundle = useCallback(async () => {
    if (!symbol) return
    setLoading(true)
    setError(null)
    try {
      const [bundleRes, watchlistRes] = await Promise.allSettled([
        chartApi.getBundle(symbol, timeframe),
        chartApi.getWatchlist(),
      ])
      if (bundleRes.status === 'fulfilled') setBundle(bundleRes.value.data)
      else setError(bundleRes.reason?.message || 'Failed to load chart')
      if (watchlistRes.status === 'fulfilled') setWatchlist(watchlistRes.value.data)
    } finally {
      setLoading(false)
    }
  }, [symbol, timeframe])

  useEffect(() => {
    loadBundle()
  }, [loadBundle])

  useEffect(() => {
    if (!symbol) return

    const connect = () => {
      const ws = new WebSocket(buildWsUrl(symbol))
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type !== 'chart_update') return
          setBundle((prev) => {
            if (!prev) return prev
            const updated = { ...prev }
            if (msg.latest_candle) {
              const candles = [...prev.candles]
              const idx = candles.findIndex((c) => c.time === msg.latest_candle.time)
              if (idx >= 0) {
                candles[idx] = { ...candles[idx], ...msg.latest_candle }
              } else {
                candles.push(msg.latest_candle)
              }
              updated.candles = candles
            }
            if (msg.signal) updated.signal = msg.signal
            return updated
          })
        } catch {}
      }

      ws.onclose = () => {
        reconnectRef.current = setTimeout(connect, 5000)
      }
      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [symbol])

  return { bundle, watchlist, loading, error, reload: loadBundle }
}
