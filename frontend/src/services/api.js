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

export default api
