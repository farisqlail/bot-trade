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
    parts = cmd.strip().split()
    cmd = parts[0].lower()
    args = [p.upper() for p in parts[1:]]

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
            "/watch ETHUSDT ARBUSDT — Add coins to watchlist + scan now\n"
            "/unwatch ETHUSDT — Remove coin from watchlist\n"
            "/watchlist — View active watchlist\n"
            "/scan — Trigger manual scan\n"
            "/buy ARBUSDT — Force-buy token with USDC (DeFi → Bybit fallback)\n"
            "/sell ARBUSDT — Force-sell token → USDC (DeFi take profit)\n"
            "/buygmx ETHUSDT — Open GMX LONG futures position\n"
            "/sellgmx ETHUSDT — Open GMX SHORT futures position\n"
            "/gmxpositions — View open GMX positions\n"
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

    elif cmd == "/watch":
        if not args:
            return "⚠️ Usage: /watch ETHUSDT ARBUSDT"
        for s in all_settings:
            current = list(s.scanner_watchlist)
            new_symbols = [sym for sym in args if sym not in current]
            if new_symbols:
                s.scanner_watchlist = current + new_symbols
        await db.commit()

        from app.services.scanner_service import ScannerService
        scan_lines = []
        scan_error = None
        for s in all_settings:
            scanner = ScannerService(db)
            try:
                results = await scanner.scan_specific_symbols(
                    user_id=s.user_id,
                    symbols=args,
                    deep_analysis=False,
                    execute_defi=s.defi_enabled,
                )
                for r in results:
                    action = r.get("recommended_action", "HOLD")
                    score = r.get("score", 0)
                    emoji = "🟢" if action in {"BUY", "STRONG_BUY"} else "🔴" if action in {"SELL", "STRONG_SELL"} else "⚪"
                    scan_lines.append(f"{emoji} <code>{r['symbol']}</code>: {action} (score {score:+.4f})")
                if not results:
                    scan_error = f"No market data for {' '.join(args)} — check symbol format (e.g. WETHUSDT not WETH)"
            except Exception as exc:
                scan_error = str(exc)
                logger.warning("watch_scan_failed", error=str(exc))
        syms_str = " ".join(args)
        if scan_lines:
            result_text = "\n".join(scan_lines)
        elif scan_error:
            result_text = f"⚠️ {scan_error}"
        else:
            result_text = "⚠️ No results."
        return f"✅ Added to watchlist: <code>{syms_str}</code>\n\n📊 <b>Scan Result</b>\n{result_text}"

    elif cmd == "/unwatch":
        if not args:
            return "⚠️ Usage: /unwatch ETHUSDT"
        removed = []
        for s in all_settings:
            current = list(s.scanner_watchlist)
            removed.extend([sym for sym in current if sym in args])
            s.scanner_watchlist = [sym for sym in current if sym not in args]
        await db.commit()
        unique_removed = list(dict.fromkeys(removed))
        if unique_removed:
            return f"🗑 Removed from watchlist: <code>{' '.join(unique_removed)}</code>"
        return f"ℹ️ Not in watchlist: <code>{' '.join(args)}</code>"

    elif cmd == "/watchlist":
        lines = []
        for s in all_settings:
            wl = s.scanner_watchlist
            mode = "All coins" if s.scan_all_coins else "Watchlist"
            lines.append(
                f"📋 <b>Watchlist ({mode})</b>\n"
                + ", ".join(f"<code>{sym}</code>" for sym in wl)
            )
        return "\n\n".join(lines) if lines else "No watchlist found."

    elif cmd == "/scan":
        from app.services.scanner_service import ScannerService
        lines = []
        for s in all_settings:
            scanner = ScannerService(db)
            try:
                results = await scanner.scan_opportunities(user_id=s.user_id, deep_analysis=False)
                top = results[:5]
                scan_lines = []
                for r in top:
                    action = r.get("recommended_action", "HOLD")
                    score = r.get("score", 0)
                    emoji = "🟢" if action in {"BUY", "STRONG_BUY"} else "🔴" if action in {"SELL", "STRONG_SELL"} else "⚪"
                    scan_lines.append(f"{emoji} <code>{r['symbol']}</code>: {action} (score {score:+.4f})")
                lines.append("📊 <b>Scan Results (top 5)</b>\n" + "\n".join(scan_lines))
            except Exception as exc:
                lines.append(f"⚠️ Scan failed: {exc}")
        return "\n\n".join(lines) if lines else "No scan results."

    elif cmd == "/sell":
        if not args:
            return "⚠️ Usage: /sell ARBUSDT\nForce-sell all held tokens → USDC via DeFi."
        symbol = args[0].upper()
        results = []
        for s in all_settings:
            if not s.defi_enabled or not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
                results.append(f"⚠️ DeFi not configured for user {s.user_id}.")
                continue
            from app.services.defi_service import DeFiService
            svc = DeFiService(network=s.defi_network or "arbitrum")
            token_address = await svc.get_token_address(symbol)
            if not token_address:
                results.append(f"⚠️ <code>{symbol}</code> not found in {s.defi_network} token registry.")
                continue
            try:
                result = await svc.sell_all_to_usdc(
                    s.defi_wallet_private_key_encrypted,
                    token_address,
                    slippage=s.defi_slippage / 100,
                    fee=svc.get_token_fee(symbol),
                )
                status = result.get("status", "unknown")
                if status == "no_balance":
                    results.append(f"ℹ️ <code>{symbol}</code> — no token balance to sell.")
                else:
                    tx = result.get("tx_hash", "")
                    results.append(f"✅ <b>DeFi SELL</b> <code>{symbol}</code> → USDC\nTx: <code>{tx}</code>")
            except Exception as exc:
                results.append(f"⚠️ <b>SELL Failed</b> <code>{symbol}</code>\n<code>{exc}</code>")
        return "\n\n".join(results) if results else "No DeFi settings found."

    elif cmd == "/buy":
        if not args:
            return "⚠️ Usage: /buy ARBUSDT\nForce-buy token. Tries DeFi first, falls back to Bybit if token not on Arbitrum."
        symbol = args[0].upper()
        results = []
        for s in all_settings:
            defi_ok = s.defi_enabled and s.defi_wallet_address and s.defi_wallet_private_key_encrypted
            bybit_ok = s.real_trade_enabled and s.polymarket_api_key and s.polymarket_api_secret

            if not defi_ok and not bybit_ok:
                results.append(f"⚠️ Neither DeFi nor Bybit configured for user {s.user_id}.")
                continue

            # Try DeFi first
            defi_traded = False
            if defi_ok:
                from app.services.defi_service import DeFiService
                svc = DeFiService(network=s.defi_network or "arbitrum")
                token_address = await svc.get_token_address(symbol)
                if token_address:
                    try:
                        balance_info = await svc.get_balance(s.defi_wallet_address)
                        usdc = balance_info["usdc_balance"]
                        active_usdc = balance_info.get("active_usdc_address")
                        trade_amount = round(usdc * (s.defi_trade_percent / 100), 2)
                        if trade_amount < 0.5:
                            results.append(f"⚠️ USDC too low: ${usdc:.2f} (trade amount ${trade_amount:.2f} < $0.50)")
                            defi_traded = True  # don't fallback, it's a balance issue
                        else:
                            result = await svc.swap_usdc_to_token(
                                s.defi_wallet_private_key_encrypted,
                                token_address,
                                trade_amount,
                                slippage=s.defi_slippage / 100,
                                fee=svc.get_token_fee(symbol),
                                usdc_address=active_usdc,
                            )
                            tx = result.get("tx_hash", "")
                            results.append(f"✅ <b>DeFi BUY</b> <code>{symbol}</code> — spent ${trade_amount:.2f} USDC\nTx: <code>{tx}</code>")
                            defi_traded = True
                    except Exception as exc:
                        results.append(f"⚠️ <b>DeFi BUY Failed</b> <code>{symbol}</code>\n<code>{exc}</code>")
                        defi_traded = True  # attempted but failed, still try Bybit

            # Bybit fallback: if DeFi not configured or token not on Arbitrum
            if not defi_traded and bybit_ok:
                try:
                    from app.services.bybit_order_service import BybitOrderService
                    from app.services.exchange_service import ExchangeService
                    testnet = s.use_public_data_only
                    order_svc = BybitOrderService(
                        api_key=s.polymarket_api_key,
                        api_secret=s.polymarket_api_secret,
                        testnet=testnet,
                    )
                    ticker = await ExchangeService().get_ticker(symbol)
                    price = float(ticker.get("price") or 0)
                    if price <= 0:
                        results.append(f"⚠️ <b>Bybit BUY Failed</b> <code>{symbol}</code>\nCould not get price.")
                        continue
                    balance = await order_svc.get_wallet_balance(coin="USDT")
                    if balance < 1.0:
                        results.append(f"⚠️ Bybit USDT balance too low: ${balance:.2f}")
                        continue
                    risk_amount = balance * (s.risk_percent / 100)
                    qty_str = f"{risk_amount / price:.3f}"
                    try:
                        await order_svc.set_leverage(symbol, s.leverage)
                    except Exception:
                        pass
                    order = await order_svc.place_order(
                        symbol=symbol,
                        side="Buy",
                        qty=qty_str,
                        order_type="Market",
                    )
                    order_id = order.get("orderId", "N/A")
                    results.append(
                        f"✅ <b>Bybit BUY</b> <code>{symbol}</code>\n"
                        f"Price: <code>${price:,.4f}</code> | Qty: <code>{qty_str}</code>\n"
                        f"Order ID: <code>{order_id}</code>\n"
                        f"ℹ️ DeFi skipped — token tidak tersedia di Arbitrum"
                    )
                except Exception as exc:
                    results.append(f"⚠️ <b>Bybit BUY Failed</b> <code>{symbol}</code>\n<code>{exc}</code>")
            elif not defi_traded and not bybit_ok:
                results.append(f"⚠️ <code>{symbol}</code> tidak tersedia di DeFi dan Bybit tidak dikonfigurasi.")

        return "\n\n".join(results) if results else "No settings found."

    elif cmd in ("/buygmx", "/sellgmx"):
        if not args:
            return f"⚠️ Usage: {cmd} ETHUSDT\nOpen GMX futures position. Markets: ETHUSDT, ARBUSDT, LINKUSDT, SOLUSDT, AVAXUSDT, GMXUSDT, OPUSDT"
        symbol = args[0].upper()
        is_long = cmd == "/buygmx"
        results = []
        for s in all_settings:
            if not s.gmx_enabled:
                results.append(f"⚠️ GMX not enabled for user {s.user_id}. Enable via bot settings.")
                continue
            if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
                results.append(f"⚠️ Wallet not configured for user {s.user_id}.")
                continue
            from app.services.gmx_service import GMXService
            from app.services.exchange_service import ExchangeService
            svc = GMXService()
            if not svc.supports_symbol(symbol):
                markets = ", ".join(GMXService.get_available_markets()[i]["symbol"] for i in range(len(GMXService.get_available_markets())))
                results.append(f"⚠️ <code>{symbol}</code> not in GMX markets.\nAvailable: {markets}")
                continue
            try:
                ticker = await ExchangeService().get_ticker(symbol)
                current_price = float(ticker.get("price") or 0)
                if current_price <= 0:
                    results.append(f"⚠️ Cannot get price for <code>{symbol}</code>.")
                    continue
                from app.services.defi_service import DeFiService
                balance_info = await DeFiService(network="arbitrum").get_balance(s.defi_wallet_address)
                usdc = balance_info["usdc_balance"]
                collateral = round(usdc * (s.gmx_collateral_percent / 100), 2)
                if collateral < 1.0:
                    results.append(f"⚠️ USDC too low: ${usdc:.2f} (collateral ${collateral:.2f} < $1.00)")
                    continue
                result = await svc.open_position(
                    s.defi_wallet_private_key_encrypted,
                    symbol,
                    is_long=is_long,
                    collateral_usdc=collateral,
                    leverage=s.gmx_leverage,
                    current_price=current_price,
                )
                if result.get("status") == "success":
                    direction = "LONG 📈" if is_long else "SHORT 📉"
                    results.append(
                        f"⚡ <b>GMX {'BUY' if is_long else 'SELL'} Executed</b>\n"
                        f"Pair: <code>{symbol}</code> | {direction}\n"
                        f"Collateral: <code>${collateral:.2f}</code> USDC\n"
                        f"Size: <code>${result.get('size_usd', 0):.2f}</code> ({s.gmx_leverage}x)\n"
                        f"Entry: <code>${current_price:,.4f}</code>\n"
                        f"Tx: <code>{result.get('tx_hash')}</code>\n"
                        f"⏳ Pending keeper execution (~1-10s)"
                    )
                    from datetime import datetime, timezone
                    open_positions = dict(s.gmx_open_positions)
                    open_positions[symbol] = {
                        "is_long": is_long,
                        "entry_price": current_price,
                        "size_usd": result.get("size_usd", 0.0),
                        "collateral_usdc": collateral,
                        "opened_at": datetime.now(timezone.utc).isoformat(),
                    }
                    s.gmx_open_positions = open_positions
                    activity_log = list(s.gmx_activity_log)
                    activity_log.insert(0, {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event": "OPENED",
                        "symbol": symbol,
                        "direction": "LONG" if is_long else "SHORT",
                        "entry_price": current_price,
                        "size_usd": result.get("size_usd", 0.0),
                        "collateral_usdc": collateral,
                        "tx_hash": result.get("tx_hash"),
                        "source": "telegram",
                    })
                    s.gmx_activity_log = activity_log[:50]
                    await db.commit()
                else:
                    results.append(f"⚠️ <b>GMX Failed</b> <code>{symbol}</code>\n<code>{result.get('error')}</code>")
            except Exception as exc:
                results.append(f"⚠️ <b>GMX Error</b> <code>{symbol}</code>\n<code>{exc}</code>")
        return "\n\n".join(results) if results else "No GMX settings found."

    elif cmd == "/gmxpositions":
        results = []
        for s in all_settings:
            if not s.gmx_enabled or not s.defi_wallet_address:
                continue
            from app.services.gmx_service import GMXService
            svc = GMXService()
            try:
                positions = await svc.get_positions(s.defi_wallet_address)
                if not positions:
                    results.append(f"ℹ️ No open GMX positions for user {s.user_id}.")
                    continue
                lines = [f"📊 <b>GMX Open Positions</b> (user {s.user_id})\n"]
                for pos in positions:
                    direction = "📈 LONG" if pos["is_long"] else "📉 SHORT"
                    lines.append(
                        f"• <code>{pos['symbol']}</code> {direction}\n"
                        f"  Size: <code>${pos['size_usd']:,.2f}</code> | Collateral: <code>${pos['collateral_usdc']:,.2f}</code>"
                    )
                results.append("\n".join(lines))
            except Exception as exc:
                results.append(f"⚠️ GMX positions error: <code>{exc}</code>")
        return "\n\n".join(results) if results else "No GMX-enabled users found."

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
        logger.info("telegram_poll", offset=offset, updates_count=len(updates))
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

                elif data.startswith("bybit_tp_"):
                    trade_id_str = data[len("bybit_tp_"):]
                    await tg.answer_callback_query(cb_id, "💰 Closing Bybit position...")
                    from app.models.trade import Trade, TradeStatus
                    from sqlalchemy import select
                    from datetime import datetime, timezone

                    try:
                        trade_id = int(trade_id_str)
                    except ValueError:
                        await tg.answer_callback_query(cb_id, "Invalid trade ID.")
                        continue

                    t_result = await db.execute(select(Trade).where(Trade.id == trade_id))
                    trade = t_result.scalar_one_or_none()

                    if not trade:
                        reply_text = f"⚠️ Trade #{trade_id} not found."
                    elif trade.status != TradeStatus.OPEN:
                        reply_text = f"ℹ️ Trade #{trade_id} <code>{trade.symbol}</code> already closed."
                    else:
                        s_result = await db.execute(select(Settings).where(Settings.user_id == trade.user_id))
                        s = s_result.scalar_one_or_none()
                        if not s or not s.polymarket_api_key or not s.polymarket_api_secret:
                            reply_text = f"⚠️ No Bybit API key for user {trade.user_id}."
                        else:
                            from app.services.bybit_order_service import BybitOrderService
                            from app.services.exchange_service import ExchangeService
                            order_svc = BybitOrderService(
                                api_key=s.polymarket_api_key,
                                api_secret=s.polymarket_api_secret,
                                testnet=s.use_public_data_only,
                            )
                            try:
                                positions = await order_svc.get_positions(symbol=trade.symbol)
                                bybit_pos = next(
                                    (p for p in positions if p.get("symbol") == trade.symbol and float(p.get("size", 0)) > 0),
                                    None,
                                )
                                if not bybit_pos:
                                    reply_text = f"ℹ️ <code>{trade.symbol}</code> — no open position on Bybit (may already be closed)."
                                else:
                                    qty = bybit_pos.get("size", "0")
                                    side = bybit_pos.get("side", "Buy")
                                    await order_svc.close_position(symbol=trade.symbol, side=side, qty=str(qty))
                                    exchange_svc = ExchangeService()
                                    ticker = await exchange_svc.get_ticker(trade.symbol)
                                    exit_price = ticker["price"]
                                    from app.models.trade import TradeDirection
                                    is_long = trade.direction == TradeDirection.LONG
                                    pnl_mult = 1 if is_long else -1
                                    pnl_pct = pnl_mult * (exit_price - trade.entry_price) / trade.entry_price * 100 * trade.leverage
                                    pnl_usd = trade.risk_amount * pnl_pct / 100 if trade.risk_amount else 0.0
                                    trade.status = TradeStatus.CLOSED
                                    trade.exit_price = exit_price
                                    trade.pnl = round(pnl_usd, 4)
                                    trade.pnl_percent = round(pnl_pct, 4)
                                    trade.closed_at = datetime.now(timezone.utc)
                                    await db.commit()
                                    reply_text = (
                                        f"✅ <b>Bybit TP Executed</b> <code>{trade.symbol}</code>\n"
                                        f"Exit: <code>${exit_price:,.6g}</code>\n"
                                        f"PnL: <code>{pnl_pct:+.2f}%</code> (<code>${pnl_usd:+.2f}</code>)"
                                    )
                                    logger.info("bybit_tp_callback_executed", trade_id=trade_id, symbol=trade.symbol, pnl=pnl_usd)
                            except Exception as exc:
                                logger.error("bybit_tp_callback_failed", trade_id=trade_id, error=str(exc))
                                reply_text = f"⚠️ <b>Bybit TP Failed</b> <code>{trade.symbol}</code>\n<code>{exc}</code>"

                    if message_id:
                        await tg.edit_message_text(message_id, reply_text)
                    await tg.send_message(reply_text)
                    processed += 1

                elif data.startswith("defi_tp_"):
                    symbol = data[len("defi_tp_"):]
                    await tg.answer_callback_query(cb_id, f"💰 Selling {symbol}...")
                    all_settings = await _get_all_settings(db)
                    sell_results = []
                    for s in all_settings:
                        if not s.defi_enabled or not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
                            continue
                        from app.services.defi_service import DeFiService
                        svc = DeFiService(network=s.defi_network or "arbitrum")
                        token_address = await svc.get_token_address(symbol)
                        if not token_address:
                            sell_results.append(f"⚠️ <code>{symbol}</code> not found in token registry.")
                            continue
                        try:
                            result = await svc.sell_all_to_usdc(
                                s.defi_wallet_private_key_encrypted,
                                token_address,
                                slippage=s.defi_slippage / 100,
                                fee=svc.get_token_fee(symbol),
                            )
                            status = result.get("status", "unknown")
                            if status == "no_balance":
                                sell_results.append(f"ℹ️ <code>{symbol}</code> — no balance to sell.")
                            else:
                                tx = result.get("tx_hash", "N/A")
                                sell_results.append(
                                    f"✅ <b>DeFi Take Profit</b> <code>{symbol}</code> → USDC\n"
                                    f"Tx: <code>{tx}</code>"
                                )
                        except Exception as exc:
                            logger.error("defi_tp_callback_sell_failed", symbol=symbol, error=str(exc))
                            sell_results.append(f"⚠️ Sell failed: <code>{exc}</code>")
                    reply_text = "\n\n".join(sell_results) if sell_results else f"⚠️ No DeFi settings for {symbol}."
                    if message_id:
                        await tg.edit_message_text(message_id, reply_text)
                    await tg.send_message(reply_text)
                    logger.info("defi_tp_callback_processed", symbol=symbol)
                    processed += 1

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

        logger.info("telegram_command_received", command=text.split()[0], chat_id=chat_id, expected=str(settings.TELEGRAM_CHAT_ID))
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
