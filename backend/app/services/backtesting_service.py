from datetime import datetime, timezone
from app.services.exchange_service import ExchangeService
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BacktestingService:
    def __init__(self):
        self.exchange_svc = ExchangeService()

    def _compute_heuristic_score(self, candles: list, idx: int, window_size: int = 10) -> dict:
        if idx < 1 or idx >= len(candles):
            return {"score": 0.0, "action": "HOLD", "price": 0.0}

        window = candles[max(0, idx - window_size + 1): idx + 1]
        if len(window) < 2:
            return {"score": 0.0, "action": "HOLD", "price": candles[idx]["close"]}

        current = window[-1]["close"]
        first = window[0]["close"]
        momentum = (current - first) / first if first > 0 else 0.0

        # 24h change: 24 candles back for hourly, 96 for 15m, etc.
        lookback_24 = 24
        if idx >= lookback_24:
            price_24h_ago = candles[idx - lookback_24]["close"]
            change_24h = (current - price_24h_ago) / price_24h_ago if price_24h_ago > 0 else 0.0
        else:
            change_24h = 0.0

        # Polymarket bias not available for historical backtest
        score = (momentum * 0.45) + (change_24h * 0.25)

        if score >= 0.001:
            action = "BUY"
        elif score <= -0.001:
            action = "SELL"
        else:
            action = "HOLD"

        return {"score": round(score, 6), "action": action, "price": current}

    async def run_backtest(
        self,
        symbol: str,
        days: int = 30,
        interval: str = "60",
        sl_percent: float = 1.5,
        tp_percent: float = 3.0,
        initial_balance: float = 10000.0,
        risk_percent: float = 1.0,
    ) -> dict:
        limit = min(days * 24, 1000) if interval == "60" else min(days * 96, 1000)
        candles = await self.exchange_svc.get_klines_range(symbol, interval=interval, limit=limit)

        if len(candles) < 25:
            return {"error": f"Insufficient candle data for {symbol}: got {len(candles)}"}

        balance = initial_balance
        equity_curve = []
        trades_log = []
        open_trade = None

        for i in range(10, len(candles)):
            sig = self._compute_heuristic_score(candles, i)
            price = sig["price"]
            action = sig["action"]
            ts = datetime.fromtimestamp(
                candles[i]["open_time"] / 1000, tz=timezone.utc
            ).isoformat()

            # Check open trade for SL/TP hit on this candle
            if open_trade:
                entry = open_trade["entry_price"]
                sl = open_trade["sl"]
                tp = open_trade["tp"]
                direction = open_trade["direction"]
                high = candles[i]["high"]
                low = candles[i]["low"]

                hit_sl = (low <= sl) if direction == "LONG" else (high >= sl)
                hit_tp = (high >= tp) if direction == "LONG" else (low <= tp)

                if hit_sl or hit_tp:
                    exit_price = sl if hit_sl else tp
                    if direction == "LONG":
                        pnl_pct = (exit_price - entry) / entry * 100
                    else:
                        pnl_pct = (entry - exit_price) / entry * 100
                    risk_amt = balance * (risk_percent / 100)
                    pnl = risk_amt * pnl_pct / 100
                    balance += pnl
                    trades_log.append({
                        **open_trade,
                        "exit_price": exit_price,
                        "exit_time": ts,
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "exit_reason": "SL" if hit_sl else "TP",
                    })
                    open_trade = None

            # Open new trade on signal (only if flat)
            if not open_trade:
                if action == "BUY":
                    sl_price = price * (1 - sl_percent / 100)
                    tp_price = price * (1 + tp_percent / 100)
                    open_trade = {
                        "direction": "LONG",
                        "entry_price": price,
                        "entry_time": ts,
                        "sl": sl_price,
                        "tp": tp_price,
                    }
                elif action == "SELL":
                    sl_price = price * (1 + sl_percent / 100)
                    tp_price = price * (1 - tp_percent / 100)
                    open_trade = {
                        "direction": "SHORT",
                        "entry_price": price,
                        "entry_time": ts,
                        "sl": sl_price,
                        "tp": tp_price,
                    }

            equity_curve.append({
                "time": ts,
                "price": round(price, 6),
                "balance": round(balance, 2),
                "signal": action,
                "score": sig["score"],
            })

        # Force-close open trade at end of data
        if open_trade:
            exit_price = candles[-1]["close"]
            direction = open_trade["direction"]
            entry = open_trade["entry_price"]
            pnl_pct = (
                (exit_price - entry) / entry * 100
                if direction == "LONG"
                else (entry - exit_price) / entry * 100
            )
            risk_amt = balance * (risk_percent / 100)
            pnl = risk_amt * pnl_pct / 100
            balance += pnl
            trades_log.append({
                **open_trade,
                "exit_price": exit_price,
                "exit_time": equity_curve[-1]["time"] if equity_curve else None,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "exit_reason": "EOD",
            })

        pnls = [t["pnl"] for t in trades_log]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total_pnl = sum(pnls)

        # Max drawdown from equity curve
        running = initial_balance
        peak = initial_balance
        max_dd = 0.0
        for t in trades_log:
            running += t["pnl"]
            if running > peak:
                peak = running
            dd = (peak - running) / peak * 100 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        logger.info(
            "backtest_complete",
            symbol=symbol,
            days=days,
            total_trades=len(trades_log),
            total_pnl=round(total_pnl, 2),
        )

        return {
            "symbol": symbol,
            "days": days,
            "interval": interval,
            "candles_used": len(candles),
            "initial_balance": initial_balance,
            "final_balance": round(balance, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percent": round(total_pnl / initial_balance * 100, 2),
            "total_trades": len(trades_log),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(trades_log) * 100, 2) if trades_log else 0.0,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
            "avg_loss": round(abs(sum(losses)) / len(losses), 2) if losses else 0.0,
            "profit_factor": (
                round(sum(wins) / abs(sum(losses)), 2)
                if losses and sum(losses) != 0
                else 0.0
            ),
            "max_drawdown": round(max_dd, 2),
            "sl_percent": sl_percent,
            "tp_percent": tp_percent,
            "risk_percent": risk_percent,
            "equity_curve": equity_curve[-200:],
            "trades": trades_log,
        }
