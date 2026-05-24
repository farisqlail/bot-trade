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
                logger.info("telegram_send_ok", chat_id=self.chat_id)
                return True
        except Exception as exc:
            logger.warning("telegram_send_failed", error=str(exc), chat_id=self.chat_id)
            return False

    async def notify_scan_results(self, opportunities: list[dict]) -> None:
        if not self.enabled:
            logger.warning("telegram_disabled_skip_scan_notify")
            return
        if not opportunities:
            logger.info("telegram_scan_notify_skipped_no_opportunities")
            return

        signals = [o for o in opportunities if o.get("recommended_action") in ("BUY", "SELL")]
        hold_count = len(opportunities) - len(signals)

        action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
        header_emoji = "📊" if signals else "🔇"
        lines = [
            f"{header_emoji} <b>Scan Results</b> — {len(opportunities)} coins"
            f"  ({len(signals)} actionable)\n"
        ]

        # Sort: BUY/SELL first (by confidence), then HOLD (by |change|)
        actionable = sorted(signals, key=lambda o: o.get("confidence") or 0, reverse=True)
        holds = sorted(
            [o for o in opportunities if o.get("recommended_action") == "HOLD"],
            key=lambda o: abs(o.get("change_24h") or 0),
            reverse=True,
        )

        for o in actionable + holds:
            action = o.get("recommended_action", "HOLD")
            emoji = action_emoji.get(action, "⚪")
            conf = int((o.get("confidence") or 0) * 100)
            entry = o.get("suggested_entry") or 0
            sl = o.get("suggested_sl") or 0
            tp = o.get("suggested_tp") or 0
            change = o.get("change_24h") or 0
            vol = o.get("volume_24h") or 0
            sentiment = o.get("sentiment") or action
            lines.append(
                f"{emoji} <b>{o['symbol']}</b>  {action}  ({change:+.2f}%)\n"
                f"   💰 Entry: <code>${entry:,.6g}</code>\n"
                f"   🛑 SL: <code>${sl:,.6g}</code>   🎯 TP: <code>${tp:,.6g}</code>\n"
                f"   📈 Sentiment: {sentiment}   Conf: {conf}%\n"
                f"   📦 Vol 24h: {vol:,.0f}"
            )

        logger.info(
            "telegram_scan_notify_send",
            total=len(opportunities),
            buy_sell=len(signals),
            hold=hold_count,
        )
        # Telegram max 4096 chars per message — chunk if needed
        MAX_LEN = 4000
        chunks = []
        current = ""
        for line in lines:
            candidate = (current + "\n" + line) if current else line
            if len(candidate) > MAX_LEN:
                chunks.append(current)
                current = line
            else:
                current = candidate
        if current:
            chunks.append(current)
        for chunk in chunks:
            await self.send_message(chunk)

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
