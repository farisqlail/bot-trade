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
            await self.send_message("🔇 <b>Scan complete</b> — no market data returned. Check watchlist or bot settings.")
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

    async def send_message_with_keyboard(self, text: str, inline_keyboard: list) -> int | None:
        """Send message with inline keyboard. Returns message_id or None on failure."""
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": {"inline_keyboard": inline_keyboard},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                msg_id = data.get("result", {}).get("message_id")
                logger.info("telegram_keyboard_message_sent", message_id=msg_id)
                return msg_id
        except Exception as exc:
            logger.warning("telegram_keyboard_send_failed", error=str(exc))
            return None

    async def edit_message_text(self, message_id: int, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/bot{self.bot_token}/editMessageText",
                    json={
                        "chat_id": self.chat_id,
                        "message_id": message_id,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("telegram_edit_message_failed", error=str(exc))
            return False

    async def answer_callback_query(self, callback_query_id: str, text: str = "") -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/bot{self.bot_token}/answerCallbackQuery",
                    json={"callback_query_id": callback_query_id, "text": text},
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("telegram_answer_callback_failed", error=str(exc))
            return False

    async def notify_tuning_recommendation(
        self,
        tuning_id: int,
        approval_token: str,
        old_risk: float,
        new_risk: float,
        direction: str,
        reason: str,
        metrics: dict,
    ) -> int | None:
        """Send tuning recommendation with Approve/Reject inline buttons. Returns message_id."""
        if not self.enabled:
            logger.warning("telegram_disabled_skip_tuning_notify")
            return None

        direction_emoji = "📈" if direction == "increase" else "📉"
        win_rate = metrics.get("win_rate", 0)
        pf = metrics.get("profit_factor", 0)
        total = metrics.get("total_trades", 0)

        text = (
            f"🔧 <b>Auto-Tuning Recommendation</b>\n\n"
            f"{direction_emoji} Risk per trade: <code>{old_risk:.2f}%</code> → <code>{new_risk:.2f}%</code>\n\n"
            f"📊 <b>Performance ({metrics.get('period_days', 30)}d):</b>\n"
            f"   Trades: {total}  ·  Win rate: {win_rate*100:.0f}%\n"
            f"   Profit factor: {pf:.2f}  ·  Max consec losses: {metrics.get('max_consecutive_losses', 0)}\n\n"
            f"💬 <i>{reason}</i>\n\n"
            f"Approve or reject this change:"
        )

        keyboard = [[
            {"text": "✅ Approve", "callback_data": f"tuning_approve_{approval_token}"},
            {"text": "❌ Reject", "callback_data": f"tuning_reject_{approval_token}"},
        ]]

        return await self.send_message_with_keyboard(text, keyboard)

    async def notify_bot_started(self, coin_count: int, auto_trade: bool, mode: str = "paper") -> None:
        if not self.enabled:
            return
        mode_emoji = "📄" if mode == "paper" else "🔗"
        trade_status = "✅ AKTIF" if auto_trade else "⏸ MANUAL"
        text = (
            f"🤖 <b>Bot Trading Dimulai</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔍 Scanning: <b>{coin_count} koin</b>\n"
            f"{mode_emoji} Mode: <b>{mode.upper()}</b>\n"
            f"⚡ Auto Trade: {trade_status}\n"
            f"🕐 Waktu: <code>{__import__('datetime').datetime.now().strftime('%H:%M:%S')}</code>"
        )
        await self.send_message(text)

    async def notify_trade_opened(
        self, symbol: str, direction: str, entry_price: float,
        stop_loss: float, take_profit: float,
        score: float | None = None,
        sentiment: str | None = None,
        confidence: float | None = None,
        volume_24h: float | None = None,
        change_24h: float | None = None,
    ) -> None:
        if not self.enabled:
            return
        emoji = "🟢" if direction == "LONG" else "🔴"
        conf_str = f"  Conf: {int(confidence * 100)}%" if confidence is not None else ""
        score_str = f"\n📊 Score: <code>{score:.4f}</code>{conf_str}" if score is not None else ""
        sentiment_str = f"\n🧠 Sentiment: {sentiment}" if sentiment else ""
        change_str = f"\n📈 24h Change: {change_24h:+.2f}%" if change_24h is not None else ""
        vol_str = f"\n📦 Volume 24h: ${volume_24h:,.0f}" if volume_24h is not None else ""
        text = (
            f"{emoji} <b>Trade Dibuka — {symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Arah: <b>{direction}</b>\n"
            f"Entry: <code>${entry_price:,.6g}</code>\n"
            f"SL: <code>${stop_loss:,.6g}</code>   TP: <code>${take_profit:,.6g}</code>"
            f"{score_str}{sentiment_str}{change_str}{vol_str}"
        )
        await self.send_message(text)

    async def notify_trade_closed(
        self, symbol: str, pnl: float, pnl_percent: float,
        exit_price: float, reason: str,
        new_balance: float | None = None,
    ) -> None:
        if not self.enabled:
            return
        emoji = "✅" if pnl >= 0 else "❌"
        balance_str = f"\n💰 Saldo Baru: <code>${new_balance:,.2f}</code>" if new_balance is not None else ""
        text = (
            f"{emoji} <b>Trade Ditutup — {symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"PnL: <code>${pnl:+.2f}</code> ({pnl_percent:+.2f}%)\n"
            f"Exit: <code>${exit_price:,.6g}</code>\n"
            f"Alasan: {reason}"
            f"{balance_str}"
        )
        await self.send_message(text)
