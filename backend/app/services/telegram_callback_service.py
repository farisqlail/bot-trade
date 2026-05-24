import httpx
import redis as redis_sync
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.config import settings
from app.core.logging_config import get_logger
from app.models.settings import Settings
from app.models.trade import Trade, TradeStatus
from app.services.tuning_service import TuningService
from app.services.telegram_service import TelegramService
from app.services.risk_service import RiskService

logger = get_logger(__name__)

OFFSET_KEY = "tg_callback_offset"


def _get_redis():
    return redis_sync.from_url(settings.REDIS_URL, decode_responses=True)


async def _fetch_updates(token: str, offset: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 0, "limit": 50},
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("result") or []


async def _get_all_settings(db: AsyncSession) -> list[Settings]:
    result = await db.execute(select(Settings))
    return result.scalars().all()


async def _handle_command(cmd: str, db: AsyncSession) -> str:
    """Handle /command messages. Returns reply text (HTML)."""
    cmd = cmd.strip().split()[0].lower()  # strip args + lowercase

    if cmd == "/help":
        return (
            "🤖 <b>Available Commands</b>\n\n"
            "/status — Bot status overview\n"
            "/risk — Current risk status\n"
            "/report — Trade performance summary\n"
            "/pause — Pause bot (disable trading)\n"
            "/resume — Resume bot\n"
            "/enable_autotrade — Toggle auto-trade on/off\n"
            "/close_all — Close all open paper trades\n"
            "/help — Show this message"
        )

    all_settings = await _get_all_settings(db)
    if not all_settings:
        return "⚠️ No bot settings found in database."

    if cmd == "/status":
        lines = []
        for s in all_settings:
            bot_icon = "▶️" if s.bot_enabled else "⏸"
            at_icon = "✅" if s.auto_trade else "❌"
            tune_icon = "✅" if s.auto_tuning_enabled else "❌"
            scan_mode = f"All coins (top {s.max_scan_coins}, vol≥${s.min_volume_filter/1e6:.0f}M)" if s.scan_all_coins else f"Watchlist ({len(s.scanner_watchlist)} coins)"
            lines.append(
                f"{bot_icon} <b>Bot:</b> {'Running' if s.bot_enabled else 'Paused'}\n"
                f"Auto-trade: {at_icon}\n"
                f"Auto-tuning: {tune_icon} ({s.tuning_frequency})\n"
                f"Scan mode: {scan_mode}\n"
                f"Risk/trade: <code>{s.risk_percent:.2f}%</code>  |  Max open: {s.max_open_trades}\n"
                f"Daily loss limit: <code>{s.daily_loss_limit_percent:.1f}%</code>  |  Max drawdown: <code>{s.max_drawdown_percent:.1f}%</code>\n"
                f"Paper balance: <code>${s.paper_balance:,.2f}</code>\n"
                f"Symbol: <code>{s.symbol}</code>  |  Leverage: {s.leverage}x"
            )
        return "\n\n".join(lines) if lines else "No settings found."

    elif cmd == "/risk":
        lines = []
        for s in all_settings:
            risk_svc = RiskService(db)
            risk = await risk_svc.get_risk_status(s.user_id, s.paper_balance)
            emoji = "🟢" if risk["status"] == "SAFE" else "🟡" if risk["status"] == "WARNING" else "🔴"
            lines.append(
                f"{emoji} <b>Risk: {risk['status']}</b>\n"
                f"Daily loss: <code>{risk['daily_loss_percent']:.2f}%</code> / limit {risk['daily_loss_limit_percent']:.1f}%\n"
                f"Drawdown: <code>{risk['current_drawdown_percent']:.2f}%</code> / max {risk['max_drawdown_percent']:.1f}%\n"
                f"Consecutive losses: <code>{risk['consecutive_losses']}</code> / limit {risk['consecutive_loss_limit']}\n"
                f"Open positions: {risk['open_positions']} / {risk['max_open_trades']}\n"
                f"Risk/trade: <code>{s.risk_percent:.2f}%</code>"
            )
        return "\n\n".join(lines)

    elif cmd == "/pause":
        for s in all_settings:
            s.bot_enabled = False
        await db.commit()
        return "⏸ <b>Bot paused.</b> Trading disabled for all accounts."

    elif cmd == "/resume":
        for s in all_settings:
            s.bot_enabled = True
        await db.commit()
        return "▶️ <b>Bot resumed.</b> Trading enabled for all accounts."

    elif cmd == "/enable_autotrade":
        results = []
        for s in all_settings:
            s.auto_trade = not s.auto_trade
            state = "ON ✅" if s.auto_trade else "OFF ❌"
            results.append(f"Auto-trade: {state}")
        await db.commit()
        return "🔄 " + "\n".join(results)

    elif cmd == "/report":
        lines = []
        for s in all_settings:
            total_r = await db.execute(
                select(func.count(Trade.id)).where(
                    and_(Trade.user_id == s.user_id, Trade.status == TradeStatus.CLOSED)
                )
            )
            total = total_r.scalar() or 0

            win_r = await db.execute(
                select(func.count(Trade.id)).where(
                    and_(Trade.user_id == s.user_id, Trade.status == TradeStatus.CLOSED, Trade.pnl > 0)
                )
            )
            wins = win_r.scalar() or 0

            pnl_r = await db.execute(
                select(func.sum(Trade.pnl)).where(
                    and_(Trade.user_id == s.user_id, Trade.status == TradeStatus.CLOSED)
                )
            )
            total_pnl = pnl_r.scalar() or 0.0

            open_r = await db.execute(
                select(func.count(Trade.id)).where(
                    and_(Trade.user_id == s.user_id, Trade.status == TradeStatus.OPEN)
                )
            )
            open_count = open_r.scalar() or 0

            win_rate = (wins / total * 100) if total > 0 else 0.0
            bot_state = "▶️ Running" if s.bot_enabled else "⏸ Paused"
            lines.append(
                f"📊 <b>Trade Report</b> [{bot_state}]\n"
                f"Closed: {total} trade(s)  ({wins}W / {total - wins}L)\n"
                f"Win rate: <code>{win_rate:.1f}%</code>\n"
                f"Total PnL: <code>${total_pnl:+.2f}</code>\n"
                f"Open positions: {open_count}\n"
                f"Paper balance: <code>${s.paper_balance:,.2f}</code>\n"
                f"Risk/trade: <code>{s.risk_percent:.2f}%</code>"
            )
        return "\n\n".join(lines) if lines else "No trade data."

    elif cmd == "/close_all":
        closed_count = 0
        for s in all_settings:
            open_result = await db.execute(
                select(Trade).where(
                    and_(Trade.user_id == s.user_id, Trade.status == TradeStatus.OPEN)
                )
            )
            open_trades = open_result.scalars().all()
            now = datetime.now(timezone.utc)
            for trade in open_trades:
                trade.status = TradeStatus.CLOSED
                trade.exit_price = trade.entry_price
                trade.pnl = 0.0
                trade.pnl_percent = 0.0
                trade.closed_at = now
                closed_count += 1
        await db.commit()
        if closed_count:
            return f"🔒 Closed {closed_count} open paper trade(s) at entry price."
        return "ℹ️ No open trades to close."

    return f"❓ Unknown command: <code>{cmd}</code>. Use /help."


async def process_telegram_callbacks(db: AsyncSession) -> int:
    """Poll getUpdates, handle commands and tuning callbacks. Returns count processed."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return 0

    r = _get_redis()
    try:
        offset = int(r.get(OFFSET_KEY) or 0)
    except Exception:
        offset = 0

    try:
        updates = await _fetch_updates(settings.TELEGRAM_BOT_TOKEN, offset)
    except Exception as exc:
        logger.warning("telegram_getUpdates_failed", error=str(exc))
        return 0

    if not updates:
        return 0

    tg = TelegramService()
    tuning_svc = TuningService(db)
    processed = 0

    for update in updates:
        new_offset = update["update_id"] + 1
        if new_offset > offset:
            offset = new_offset

        # --- callback_query: tuning approve/reject buttons ---
        cb = update.get("callback_query")
        if cb:
            cb_id = cb["id"]
            data = cb.get("data", "")
            message_id = (cb.get("message") or {}).get("message_id")

            try:
                if data.startswith("tuning_approve_"):
                    token = data[len("tuning_approve_"):]
                    record = await tuning_svc.approve_by_token(token)
                    if record:
                        await tg.answer_callback_query(cb_id, "✅ Approved!")
                        if message_id:
                            await tg.edit_message_text(
                                message_id,
                                f"✅ <b>Tuning Approved</b>\n"
                                f"Risk/trade: <code>{record.old_risk_percent:.2f}%</code> → <code>{record.new_risk_percent:.2f}%</code>",
                            )
                        logger.info("tuning_approved_via_telegram", token=token[:8])
                        processed += 1
                    else:
                        await tg.answer_callback_query(cb_id, "Already resolved or not found.")

                elif data.startswith("tuning_reject_"):
                    token = data[len("tuning_reject_"):]
                    record = await tuning_svc.reject_by_token(token)
                    if record:
                        await tg.answer_callback_query(cb_id, "❌ Rejected.")
                        if message_id:
                            await tg.edit_message_text(
                                message_id,
                                f"❌ <b>Tuning Rejected</b>\n"
                                f"Risk/trade remains at <code>{record.old_risk_percent:.2f}%</code>.",
                            )
                        logger.info("tuning_rejected_via_telegram", token=token[:8])
                        processed += 1
                    else:
                        await tg.answer_callback_query(cb_id, "Already resolved or not found.")

            except Exception as exc:
                logger.warning("telegram_callback_process_error", data=data, error=str(exc))
                await tg.answer_callback_query(cb_id, "Error processing request.")

            continue  # done with this update

        # --- message: bot commands ---
        msg = update.get("message")
        if not msg:
            continue

        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            continue

        # Security: only accept from authorized chat
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        if chat_id != str(settings.TELEGRAM_CHAT_ID):
            logger.warning("telegram_command_unauthorized_chat", chat_id=chat_id)
            continue

        logger.info("telegram_command_received", command=text.split()[0])
        try:
            reply = await _handle_command(text, db)
            await tg.send_message(reply)
            processed += 1
        except Exception as exc:
            logger.warning("telegram_command_error", command=text, error=str(exc))
            await tg.send_message(f"⚠️ Error: {exc}")

    if updates:
        try:
            r.set(OFFSET_KEY, offset)
        except Exception as exc:
            logger.warning("redis_offset_save_failed", error=str(exc))

    await db.commit()
    return processed
