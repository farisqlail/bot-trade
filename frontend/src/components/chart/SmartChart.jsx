import { useEffect, useRef } from 'react'
import { createChart, ColorType, CrosshairMode, LineStyle } from 'lightweight-charts'

const THEME = {
  layout: {
    background: { type: ColorType.Solid, color: '#09090b' },
    textColor: '#a1a1aa',
  },
  grid: {
    vertLines: { color: '#18181b' },
    horzLines: { color: '#18181b' },
  },
  crosshair: { mode: CrosshairMode.Normal },
  rightPriceScale: { borderColor: '#27272a' },
  timeScale: { borderColor: '#27272a', timeVisible: true, secondsVisible: false },
}

const CANDLE_OPTS = {
  upColor: '#22c55e',
  downColor: '#ef4444',
  borderUpColor: '#22c55e',
  borderDownColor: '#ef4444',
  wickUpColor: '#22c55e',
  wickDownColor: '#ef4444',
}

function addPriceLine(series, price, color, title, style = LineStyle.Dashed) {
  if (!price) return null
  return series.createPriceLine({ price, color, lineWidth: 2, lineStyle: style, axisLabelVisible: true, title })
}

export default function SmartChart({ candles = [], signal, activeTrade, markers = [] }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef({})
  const priceLinesRef = useRef([])

  // Init chart once
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      ...THEME,
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight || 480,
    })

    const candleSeries = chart.addCandlestickSeries(CANDLE_OPTS)
    const ema20 = chart.addLineSeries({
      color: '#22d3ee', lineWidth: 1, title: 'EMA20',
      priceLineVisible: false, lastValueVisible: true,
    })
    const ema50 = chart.addLineSeries({
      color: '#f59e0b', lineWidth: 1, title: 'EMA50',
      priceLineVisible: false, lastValueVisible: true,
    })
    const ema200 = chart.addLineSeries({
      color: '#a855f7', lineWidth: 2, title: 'EMA200',
      priceLineVisible: false, lastValueVisible: true,
    })

    chartRef.current = chart
    seriesRef.current = { candleSeries, ema20, ema50, ema200 }

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.resize(containerRef.current.clientWidth, containerRef.current.clientHeight)
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = {}
    }
  }, [])

  // Update candle + EMA data
  useEffect(() => {
    const { candleSeries, ema20, ema50, ema200 } = seriesRef.current
    if (!candleSeries || !candles.length) return

    candleSeries.setData(
      candles.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close }))
    )
    ema20.setData(candles.filter((c) => c.ema20 != null).map((c) => ({ time: c.time, value: c.ema20 })))
    ema50.setData(candles.filter((c) => c.ema50 != null).map((c) => ({ time: c.time, value: c.ema50 })))
    ema200.setData(candles.filter((c) => c.ema200 != null).map((c) => ({ time: c.time, value: c.ema200 })))
  }, [candles])

  // Update price lines from signal / active trade
  useEffect(() => {
    const { candleSeries } = seriesRef.current
    if (!candleSeries) return

    priceLinesRef.current.forEach((line) => {
      try { candleSeries.removePriceLine(line) } catch {}
    })
    priceLinesRef.current = []

    const lines = []

    if (signal) {
      lines.push(addPriceLine(candleSeries, signal.entry, '#3b82f6', 'Entry'))
      lines.push(addPriceLine(candleSeries, signal.stop_loss, '#ef4444', 'SL'))
      lines.push(addPriceLine(candleSeries, signal.tp1, '#22c55e', 'TP1'))
      lines.push(addPriceLine(candleSeries, signal.tp2, '#16a34a', 'TP2'))
      lines.push(addPriceLine(candleSeries, signal.tp3, '#15803d', 'TP3'))
    } else if (activeTrade) {
      lines.push(addPriceLine(candleSeries, activeTrade.entry_price, '#3b82f6', 'Entry', LineStyle.Solid))
      lines.push(addPriceLine(candleSeries, activeTrade.stop_loss, '#ef4444', 'SL', LineStyle.Solid))
      lines.push(addPriceLine(candleSeries, activeTrade.take_profit, '#22c55e', 'TP', LineStyle.Solid))
      if (activeTrade.current_price) {
        lines.push(addPriceLine(candleSeries, activeTrade.current_price, '#a855f7', 'Now', LineStyle.Dotted))
      }
    }

    priceLinesRef.current = lines.filter(Boolean)
  }, [signal, activeTrade])

  // Update BUY/SELL history markers
  useEffect(() => {
    const { candleSeries } = seriesRef.current
    if (!candleSeries) return

    const markerData = (markers || [])
      .filter((m) => m.time && m.action)
      .map((m) => ({
        time: m.time,
        position: m.action === 'BUY' ? 'belowBar' : 'aboveBar',
        color: m.action === 'BUY' ? '#22c55e' : '#ef4444',
        shape: m.action === 'BUY' ? 'arrowUp' : 'arrowDown',
        text: m.confidence ? `${m.action} ${(m.confidence * 100).toFixed(0)}%` : m.action,
      }))
      .sort((a, b) => a.time - b.time)

    candleSeries.setMarkers(markerData)
  }, [markers])

  return <div ref={containerRef} className="w-full h-full" />
}
