import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ActiveTrades from './pages/ActiveTrades'
import TradeHistory from './pages/TradeHistory'
import AIAnalysis from './pages/AIAnalysis'
import RiskSettings from './pages/RiskSettings'
import BotSettings from './pages/BotSettings'
import TradingChart from './pages/TradingChart'
import FuturesTrade from './pages/FuturesTrade'
import GTradeFutures from './pages/GTradeFutures'
import AltcoinScanner from './pages/AltcoinScanner'
import SpotTrading from './pages/SpotTrading'
import Portfolio from './pages/Portfolio'
import Login from './pages/Login'
import Register from './pages/Register'

function PrivateRoute({ children }) {
  const token = localStorage.getItem('access_token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="active-trades" element={<ActiveTrades />} />
          <Route path="trade-history" element={<TradeHistory />} />
          <Route path="ai-analysis" element={<AIAnalysis />} />
          <Route path="risk-settings" element={<RiskSettings />} />
          <Route path="bot-settings" element={<BotSettings />} />
          <Route path="chart" element={<TradingChart />} />
          <Route path="futures" element={<FuturesTrade />} />
          <Route path="gtrade" element={<GTradeFutures />} />
          <Route path="altcoins" element={<AltcoinScanner />} />
          <Route path="spot" element={<SpotTrading />} />
          <Route path="portfolio" element={<Portfolio />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
