import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const res = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refresh })
          localStorage.setItem('access_token', res.data.access_token)
          localStorage.setItem('refresh_token', res.data.refresh_token)
          error.config.headers.Authorization = `Bearer ${res.data.access_token}`
          return api.request(error.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
}

export const dashboardApi = {
  get: () => api.get('/dashboard'),
}

export const tradesApi = {
  create: (data) => api.post('/trades', data),
  getOpen: () => api.get('/trades/open'),
  getHistory: (params) => api.get('/trades/history', { params }),
  getOne: (id) => api.get(`/trades/${id}`),
  update: (id, data) => api.patch(`/trades/${id}`, data),
  close: (id, data) => api.post(`/trades/${id}/close`, data),
}

export const aiApi = {
  analyze: (symbol) => api.post(`/ai/analyze/${symbol}`),
  getLatest: (symbol) => api.get(`/ai/latest/${symbol}`),
  getHistory: (symbol, limit = 20) => api.get(`/ai/history/${symbol}`, { params: { limit } }),
  getCachedOpportunities: () => api.get('/ai/opportunities/cached'),
  scanOpportunities: async (params) => {
    try {
      return await api.post('/ai/opportunities', null, { params, timeout: 300000 })
    } catch (error) {
      if (error.response?.status === 405) {
        return api.get('/ai/opportunities', { params, timeout: 300000 })
      }
      throw error
    }
  },
  watchAndScan: (symbol, execute_defi = true) =>
    api.post('/ai/watch', { symbol, execute_defi }, { timeout: 300000 }),
  getAltcoins: (params) => api.get('/ai/altcoins', { params, timeout: 120000 }),
}

export const riskApi = {
  getStatus: () => api.get('/risk/status'),
  getEvents: (params) => api.get('/risk/events', { params }),
}

export const botApi = {
  getSettings: () => api.get('/bot/settings'),
  updateSettings: (data) => api.patch('/bot/settings', data),
  start: () => api.post('/bot/start'),
  stop: () => api.post('/bot/stop'),
  testTelegram: () => api.post('/bot/test-telegram'),
}

export const tuningApi = {
  getHistory: (limit = 20) => api.get('/tuning/history', { params: { limit } }),
  getPending: () => api.get('/tuning/pending'),
  approve: (id) => api.post(`/tuning/${id}/approve`),
  reject: (id) => api.post(`/tuning/${id}/reject`),
  runManual: () => api.post('/tuning/run'),
}

export const defiApi = {
  getNetworks: () => api.get('/defi/networks'),
  testConnection: (data) => api.post('/defi/test-connection', data),
  getBalance: () => api.get('/defi/balance'),
  swap: (data) => api.post('/defi/swap', data),
  checkSupport: (symbol) => api.get(`/defi/check/${symbol}`),
}

export const gtradeApi = {
  getPairs: () => api.get('/gtrade/pairs'),
  getStatus: () => api.get('/gtrade/status'),
  getPositions: () => api.get('/gtrade/positions'),
  openTrade: (data) => api.post('/gtrade/trade', data),
  closePosition: (symbol) => api.post('/gtrade/close', { symbol }),
  applyAiTpsl: (symbol = null) => api.post('/gtrade/apply-ai-tpsl', { symbol }, { timeout: 120000 }),
  forceCloseAll: () => api.post('/gtrade/force-close-all', {}, { timeout: 120000 }),
  getLogs: () => api.get('/gtrade/logs'),
}

export const bybitFuturesApi = {
  openTrade: (data) => api.post('/bybit-futures/trade', data),
  getBalance: () => api.get('/bybit-futures/balance'),
  getDepositAddress: (coin = 'USDC') => api.get('/bybit-futures/deposit-address', { params: { coin } }),
}

export const gmxApi = {
  getMarkets: () => api.get('/gmx/markets'),
  getStatus: () => api.get('/gmx/status'),
  getPositions: () => api.get('/gmx/positions'),
  openTrade: (data) => api.post('/gmx/trade', data),
  closePosition: (symbol) => api.post('/gmx/close', { symbol }),
  getLogs: () => api.get('/gmx/logs'),
}

export const chartApi = {
  getBundle: (symbol, interval = '60', limit = 200) =>
    api.get(`/chart/${symbol}/analysis`, { params: { interval, limit } }),
  getCandles: (symbol, interval = '60', limit = 200) =>
    api.get(`/chart/${symbol}/candles`, { params: { interval, limit } }),
  getSignal: (symbol) => api.get(`/chart/${symbol}/signal`),
  getActiveTrade: (symbol) => api.get(`/chart/${symbol}/active-trade`),
  getWatchlist: (limit = 30) => api.get('/chart/watchlist/ranking', { params: { limit } }),
}

export const spotApi = {
  getSummary: () => api.get('/spot-trades/stats/summary'),
  listTrades: (params) => api.get('/spot-trades/', { params }),
  createTrade: (data) => api.post('/spot-trades/', data),
  updateTrade: (id, data) => api.put(`/spot-trades/${id}`, data),
  deleteTrade: (id) => api.delete(`/spot-trades/${id}`),

  listWatchlist: () => api.get('/spot-watchlist/'),
  addWatchlist: (data) => api.post('/spot-watchlist/', data),
  updateWatchlist: (id, data) => api.put(`/spot-watchlist/${id}`, data),
  deleteWatchlist: (id) => api.delete(`/spot-watchlist/${id}`),
  getPrices: () => api.get('/spot-watchlist/prices'),
  getSignals: () => api.get('/spot-watchlist/signals'),
}

// ===== SPOT TRADES API =====
export const spotTradesApi = {
  getAll: (params) => api.get('/spot-trades', { params }),
  create: (data) => api.post('/spot-trades', data),
  update: (id, data) => api.put(`/spot-trades/${id}`, data),
  delete: (id) => api.delete(`/spot-trades/${id}`),
  getSummary: () => api.get('/spot-trades/stats/summary'),
}

// ===== SPOT WATCHLIST API =====
export const spotWatchlistApi = {
  getAll: () => api.get('/spot-watchlist'),
  create: (data) => api.post('/spot-watchlist', data),
  update: (id, data) => api.put(`/spot-watchlist/${id}`, data),
  delete: (id) => api.delete(`/spot-watchlist/${id}`),
  getPrices: () => api.get('/spot-watchlist/prices'),
  getSignals: () => api.get('/spot-watchlist/signals'),
}

export const portfolioApi = {
  get: () => api.get('/portfolio', { timeout: 20000 }),
}

export const sentimentApi = {
  get: () => api.get('/sentiment', { timeout: 12000 }),
}

export default api
