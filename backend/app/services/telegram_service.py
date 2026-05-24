import httpx
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TelegramService:
    BASE_URL = "https://api.telegram.org"

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)

    async def send_message(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/bot{self.bot_token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("telegram_send_failed", error=str(exc))
            return False

    async def notify_scan_results(self, opportunities: list[dict]) -> None:
        if not self.enabled:
            return
        signals = [o for o in opportunities if o.get("recommended_action") in ("BUY", "SELL")]
        if not signals:
            return

        lines = ["📊 <b>Auto Scan Results</b>"]
        for o in signals[:5]:
            action = o["recommended_action"]
            emoji = "🟢" if action == "BUY" else "🔴"
            conf = int((o.get("confidence") or 0) * 100)
            entry = o.get("suggested_entry") or 0
            sl = o.get("suggested_sl") or 0
            tp = o.get("suggested_tp") or 0
            lines.append(
                f"\n{emoji} <b>{o['symbol']}</b> — {action}\n"
                f"   Entry: <code>${entry:,.4f}</code>\n"
                f"   SL: <code>${sl:,.4f}</code>  TP: <code>${tp:,.4f}</code>\n"
                f"   Confidence: {conf}%"
            )

        await self.send_message("\n".join(lines))

    async def notify_trade_opened(self, symbol: str, direction: str, entry_price: float,
                                   stop_loss: float, take_profit: float) -> None:
        if not self.enabled:
            return
        emoji = "🟢" if direction == "LONG" else "🔴"
        text = (
            f"{emoji} <b>Trade Opened</b>\n"
            f"Symbol: <b>{symbol}</b>\n"
            f"Direction: {direction}\n"
            f"Entry: <code>${entry_price:,.4f}</code>\n"
            f"SL: <code>${stop_loss:,.4f}</code>  TP: <code>${take_profit:,.4f}</code>"
        )
        await self.send_message(text)

    async def notify_trade_closed(self, symbol: str, pnl: float, pnl_percent: float,
                                   exit_price: float, reason: str) -> None:
        if not self.enabled:
            return
        emoji = "✅" if pnl >= 0 else "❌"
        text = (
            f"{emoji} <b>Trade Closed</b>\n"
            f"Symbol: <b>{symbol}</b>\n"
            f"PnL: <code>${pnl:+.2f}</code> ({pnl_percent:+.2f}%)\n"
            f"Exit: <code>${exit_price:,.4f}</code>\n"
            f"Reason: {reason}"
        )
        await self.send_message(text)
