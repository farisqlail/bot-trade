import asyncio
from app.workers.celery_app import celery_app
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.tasks.run_ai_analysis", bind=True, max_retries=3)
def run_ai_analysis(self, symbol: str = "featured"):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.services.ai_service import AIService
        from app.services.exchange_service import ExchangeService

        async with AsyncSessionLocal() as db:
            exchange_svc = ExchangeService()
            market_data = await exchange_svc.get_market_data(symbol)
            ai_svc = AIService(db)
            analysis = await ai_svc.analyze_market(symbol, market_data)
            await db.commit()
            logger.info("scheduled_ai_analysis_done", symbol=symbol, analysis_id=analysis.id)
            return {"analysis_id": analysis.id, "symbol": symbol}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("ai_analysis_task_error", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.scan_market_opportunities", bind=True, max_retries=3)
def scan_market_opportunities(self):
    async def _run():
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.settings import Settings
        from app.services.scanner_service import ScannerService
        from app.services.telegram_service import TelegramService

        telegram = TelegramService()

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Settings).where(Settings.ai_analysis_enabled == True)
            )
            active_settings = result.scalars().all()
            scanner = ScannerService(db)

            for s in active_settings:
                if not s.continuous_scan_enabled:
                    continue
                if s.auto_trade or s.paper_trade_enabled:
                    if s.gmx_enabled and s.defi_wallet_address:
                        mode = "gmx"
                    elif s.defi_enabled and s.defi_wallet_address:
                        mode = "defi"
                    elif s.real_trade_enabled and s.polymarket_api_key:
                        mode = "bybit"
                    else:
                        mode = "paper"
                    coin_count = s.max_scan_coins if s.scan_all_coins else 30
                    await telegram.notify_bot_started(
                        coin_count=coin_count,
                        auto_trade=s.auto_trade or s.paper_trade_enabled,
                        mode=mode,
                    )

                opportunities = await scanner.scan_opportunities(
                    user_id=s.user_id,
                    deep_analysis=True,
                    execute_paper=s.paper_trade_enabled,
                )
                await telegram.notify_scan_results(opportunities)

            await db.commit()

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("scan_market_opportunities_error", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.run_auto_tuning", bind=True)
def run_auto_tuning(self):
    async def _run():
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.settings import Settings
        from app.services.tuning_service import TuningService
        from app.services.telegram_service import TelegramService

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Settings).where(Settings.ai_analysis_enabled == True)
            )
            all_settings = result.scalars().all()
            tg = TelegramService()

            for s in all_settings:
                try:
                    svc = TuningService(db)
                    record = await svc.run_tuning(s.user_id)

                    if record and record.status == "pending":
                        msg_id = await tg.notify_tuning_recommendation(
                            tuning_id=record.id,
                            approval_token=record.approval_token,
                            old_risk=record.old_risk_percent,
                            new_risk=record.new_risk_percent,
                            direction=record.change_direction or "no_change",
                            reason=record.reason or "",
                            metrics=record.metrics_snapshot or {},
                        )
                        if msg_id:
                            record.telegram_message_id = msg_id
                    elif record and record.status == "auto_applied":
                        await tg.send_message(
                            f"⚙️ <b>Auto-Tuning Applied</b>\n"
                            f"Risk per trade: <code>{record.old_risk_percent:.2f}%</code> → <code>{record.new_risk_percent:.2f}%</code>\n"
                            f"<i>{record.reason}</i>"
                        )
                except Exception as exc:
                    logger.error("auto_tuning_user_error", user_id=s.user_id, error=str(exc))

            await db.commit()

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("auto_tuning_task_error", error=str(exc))
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(name="app.workers.tasks.process_telegram_callbacks", bind=True)
def process_telegram_callbacks(self):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.services.telegram_callback_service import process_telegram_callbacks as _process

        async with AsyncSessionLocal() as db:
            count = await _process(db)
            if count:
                logger.info("telegram_callbacks_processed", count=count)

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("process_telegram_callbacks_error", error=str(exc))


@celery_app.task(name="app.workers.tasks.check_risk_limits", bind=True)
def check_risk_limits(self):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.user import User
        from app.models.settings import Settings
        from app.services.risk_service import RiskService
        from app.services.exchange_service import ExchangeService
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Settings).where(Settings.bot_enabled == True)
            )
            active_settings = result.scalars().all()
            exchange_svc = ExchangeService()
            account = await exchange_svc.get_account_balance()

            for s in active_settings:
                risk_svc = RiskService(db)
                await risk_svc.check_and_log_risk_events(s.user_id, s.paper_balance or account["balance"])

            await db.commit()

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("risk_check_task_error", error=str(exc))


@celery_app.task(name="app.workers.tasks.check_stop_loss_take_profit", bind=True)
def check_stop_loss_take_profit(self):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.trade import Trade, TradeStatus, TradeDirection
        from app.services.trading_service import TradingService
        from app.services.exchange_service import ExchangeService
        from app.schemas.trade import TradeClose
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Trade).where(Trade.status == TradeStatus.OPEN)
            )
            open_trades = result.scalars().all()
            if not open_trades:
                return

            symbols = list(set(t.symbol for t in open_trades))
            exchange_svc = ExchangeService()
            prices = {}
            for sym in symbols:
                ticker = await exchange_svc.get_ticker(sym)
                prices[sym] = ticker["price"]

            trading_svc = TradingService(db)
            for trade in open_trades:
                price = prices.get(trade.symbol)
                if not price:
                    continue

                if trade.direction == TradeDirection.LONG:
                    hit_sl = price <= trade.stop_loss
                    hit_tp = price >= trade.take_profit
                else:
                    hit_sl = price >= trade.stop_loss
                    hit_tp = price <= trade.take_profit

                if hit_sl or hit_tp:
                    reason = "SL hit" if hit_sl else "TP hit"
                    close_data = TradeClose(exit_price=price, notes=reason)
                    closed = await trading_svc.close_trade(trade.id, trade.user_id, close_data)
                    logger.info("auto_close_trade", trade_id=trade.id,
                                reason="SL" if hit_sl else "TP", price=price)
                    from app.services.telegram_service import TelegramService
                    from app.models.settings import Settings as _Settings
                    _sr = await db.execute(
                        select(_Settings).where(_Settings.user_id == trade.user_id)
                    )
                    _s = _sr.scalar_one_or_none()
                    new_balance = None
                    if _s and _s.paper_balance is not None:
                        new_balance = round(_s.paper_balance + (closed.pnl or 0.0), 2)
                    await TelegramService().notify_trade_closed(
                        symbol=closed.symbol,
                        pnl=closed.pnl or 0.0,
                        pnl_percent=closed.pnl_percent or 0.0,
                        exit_price=closed.exit_price or price,
                        reason=reason,
                        new_balance=new_balance,
                    )

            await db.commit()

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("sl_tp_check_error", error=str(exc))


@celery_app.task(name="app.workers.tasks.monitor_bybit_positions", bind=True)
def monitor_bybit_positions(self):
    async def _run():
        from app.database import AsyncSessionLocal
        from sqlalchemy import select, and_
        from app.models.settings import Settings
        from app.models.trade import Trade, TradeStatus, TradeDirection
        from app.services.bybit_order_service import BybitOrderService
        from app.services.exchange_service import ExchangeService
        from app.services.telegram_service import TelegramService
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            # Only real trades (have exchange_order_id)
            result = await db.execute(
                select(Trade).where(
                    and_(
                        Trade.status == TradeStatus.OPEN,
                        Trade.exchange_order_id.isnot(None),
                    )
                )
            )
            real_trades = result.scalars().all()
            if not real_trades:
                return

            exchange_svc = ExchangeService()
            tg = TelegramService()

            for trade in real_trades:
                # Get API keys for this user
                s_result = await db.execute(select(Settings).where(Settings.user_id == trade.user_id))
                s = s_result.scalar_one_or_none()
                if not s or not s.polymarket_api_key or not s.polymarket_api_secret:
                    continue

                order_svc = BybitOrderService(
                    api_key=s.polymarket_api_key,
                    api_secret=s.polymarket_api_secret,
                    testnet=s.use_public_data_only,
                )

                # Sync: check if Bybit already closed this position
                try:
                    positions = await order_svc.get_positions(symbol=trade.symbol)
                    bybit_pos = next(
                        (p for p in positions if p.get("symbol") == trade.symbol and float(p.get("size", 0)) > 0),
                        None,
                    )
                except Exception as exc:
                    logger.warning("bybit_monitor_get_positions_failed", symbol=trade.symbol, error=str(exc))
                    continue

                if bybit_pos is None:
                    # Bybit position closed (SL/TP hit at exchange) — sync DB
                    try:
                        ticker = await exchange_svc.get_ticker(trade.symbol)
                        exit_price = ticker["price"]
                    except Exception:
                        exit_price = trade.entry_price

                    pnl_mult = 1 if trade.direction == TradeDirection.LONG else -1
                    pnl_pct = pnl_mult * (exit_price - trade.entry_price) / trade.entry_price * 100 * trade.leverage
                    pnl_usd = trade.risk_amount * pnl_pct / 100 if trade.risk_amount else 0.0

                    trade.status = TradeStatus.CLOSED
                    trade.exit_price = exit_price
                    trade.pnl = round(pnl_usd, 4)
                    trade.pnl_percent = round(pnl_pct, 4)
                    trade.closed_at = datetime.now(timezone.utc)
                    logger.info("bybit_monitor_synced_close", trade_id=trade.id, symbol=trade.symbol, pnl=pnl_usd)
                    await tg.notify_trade_closed(
                        symbol=trade.symbol,
                        pnl=pnl_usd,
                        pnl_percent=pnl_pct,
                        exit_price=exit_price,
                        reason="Bybit SL/TP (synced)",
                    )
                    continue

                # Position still open — check signal for early exit
                try:
                    market_data = await exchange_svc.get_market_data(trade.symbol)
                except Exception:
                    continue

                candles = market_data.get("candles") or []
                current_price = float(market_data.get("price") or 0.0)
                if len(candles) >= 2 and candles[0].get("close"):
                    momentum = (candles[-1]["close"] - candles[0]["close"]) / candles[0]["close"]
                else:
                    momentum = 0.0
                change_score = float(market_data.get("change_24h") or 0.0) / 100.0
                sentiment_score = float(market_data.get("polymarket_bias_score") or 0.0)
                score = (momentum * 0.45) + (change_score * 0.25) + (sentiment_score * 0.30)

                is_long = trade.direction == TradeDirection.LONG
                # Signal flip: LONG + bearish signal, or SHORT + bullish signal
                signal_flip = (is_long and score <= -0.005) or (not is_long and score >= 0.005)
                if not signal_flip:
                    # Optionally move SL to breakeven if in profit > 1%
                    if current_price and trade.entry_price:
                        profit_pct = (current_price - trade.entry_price) / trade.entry_price * (1 if is_long else -1) * 100
                        if profit_pct >= 1.5 and trade.stop_loss:
                            be_sl = trade.entry_price * (1.001 if is_long else 0.999)
                            current_sl = float(bybit_pos.get("stopLoss") or 0)
                            sl_already_moved = (is_long and current_sl >= be_sl) or (not is_long and 0 < current_sl <= be_sl)
                            if not sl_already_moved:
                                try:
                                    await order_svc.set_trading_stop(symbol=trade.symbol, stop_loss=be_sl)
                                    trade.stop_loss = be_sl
                                    logger.info("bybit_monitor_sl_moved_to_be", symbol=trade.symbol, sl=be_sl)
                                    await tg.send_message_with_keyboard(
                                        f"🔒 <b>SL moved to breakeven</b> <code>{trade.symbol}</code>\n"
                                        f"Profit: <code>+{profit_pct:.2f}%</code> → SL: <code>${be_sl:,.6g}</code>\n"
                                        f"Current: <code>${current_price:,.6g}</code>",
                                        inline_keyboard=[[
                                            {"text": "💰 Take Profit Now", "callback_data": f"bybit_tp_{trade.id}"},
                                        ]]
                                    )
                                except Exception as exc:
                                    logger.warning("bybit_monitor_sl_amend_failed", symbol=trade.symbol, error=str(exc))
                    continue

                # Signal flip detected — close position
                qty = bybit_pos.get("size", "0")
                side = bybit_pos.get("side", "Buy")
                action_label = "STRONG_SELL signal on LONG" if is_long else "STRONG_BUY signal on SHORT"
                logger.info("bybit_monitor_signal_exit", symbol=trade.symbol, action=action_label, score=round(score, 4))
                try:
                    await order_svc.close_position(symbol=trade.symbol, side=side, qty=str(qty))
                    pnl_mult = 1 if is_long else -1
                    pnl_pct = pnl_mult * (current_price - trade.entry_price) / trade.entry_price * 100 * trade.leverage
                    pnl_usd = trade.risk_amount * pnl_pct / 100 if trade.risk_amount else 0.0
                    trade.status = TradeStatus.CLOSED
                    trade.exit_price = current_price
                    trade.pnl = round(pnl_usd, 4)
                    trade.pnl_percent = round(pnl_pct, 4)
                    trade.closed_at = datetime.now(timezone.utc)
                    await tg.send_message(
                        f"🚨 <b>Bybit Signal Exit</b> <code>{trade.symbol}</code>\n"
                        f"Reason: {action_label} (score {score:+.4f})\n"
                        f"Exit: <code>${current_price:,.6g}</code>\n"
                        f"PnL: <code>{pnl_pct:+.2f}%</code> (<code>${pnl_usd:+.2f}</code>)"
                    )
                except Exception as exc:
                    logger.error("bybit_monitor_close_failed", symbol=trade.symbol, error=str(exc))
                    await tg.send_message(
                        f"⚠️ <b>Bybit Signal Exit Failed</b> <code>{trade.symbol}</code>\n<code>{exc}</code>"
                    )

            await db.commit()

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("monitor_bybit_positions_error", error=str(exc))


@celery_app.task(name="app.workers.tasks.monitor_defi_positions", bind=True)
def monitor_defi_positions(self):
    async def _run():
        from app.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.settings import Settings
        from app.services.defi_service import DeFiService, ARBITRUM_KNOWN_TOKENS
        from app.services.exchange_service import ExchangeService
        from app.services.telegram_service import TelegramService

        # Symbols to monitor across all networks (price data from Bybit, token address from DexScreener)
        MONITOR_SYMBOLS = list(ARBITRUM_KNOWN_TOKENS.keys())

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Settings).where(
                    Settings.bot_enabled == True,
                    Settings.defi_enabled == True,
                    Settings.auto_trade == True,
                )
            )
            active_settings = result.scalars().all()
            exchange_svc = ExchangeService()

            for s in active_settings:
                if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
                    continue

                for network in s.defi_networks:
                    svc = DeFiService(network=network)

                    for symbol in MONITOR_SYMBOLS:
                        token_address = await svc.get_token_address(symbol)
                        if not token_address:
                            continue

                        try:
                            token_raw, _ = await svc.get_token_balance(s.defi_wallet_address, token_address)
                        except Exception:
                            continue

                        if token_raw == 0:
                            continue

                        # Token held on this network — get current signal
                        try:
                            market_data = await exchange_svc.get_market_data(symbol)
                        except Exception as exc:
                            logger.warning("defi_monitor_market_data_failed", symbol=symbol, network=network, error=str(exc))
                            continue

                        candles = market_data.get("candles") or []
                        current_price = float(market_data.get("price") or 0.0)
                        if len(candles) >= 2 and candles[0].get("close"):
                            momentum = (candles[-1]["close"] - candles[0]["close"]) / candles[0]["close"]
                        else:
                            momentum = 0.0
                        change_score = float(market_data.get("change_24h") or 0.0) / 100.0
                        sentiment_score = float(market_data.get("polymarket_bias_score") or 0.0)
                        score = (momentum * 0.45) + (change_score * 0.25) + (sentiment_score * 0.30)

                        # Stop-loss check: sell immediately if price drops below entry * (1 - sl_pct)
                        entry_prices = s.defi_entry_prices
                        entry_price = float(entry_prices.get(symbol, 0.0))
                        sl_pct = s.defi_stop_loss_percent / 100.0
                        is_stop_loss = (
                            entry_price > 0
                            and current_price > 0
                            and current_price <= entry_price * (1.0 - sl_pct)
                        )

                        if not is_stop_loss and score > -0.001:
                            logger.info("defi_monitor_holding_ok", symbol=symbol, network=network, score=round(score, 4), price=current_price)
                            continue

                        if is_stop_loss:
                            action = "STOP_LOSS"
                            loss_pct = (entry_price - current_price) / entry_price * 100
                            logger.warning(
                                "defi_monitor_stop_loss_triggered",
                                symbol=symbol, network=network,
                                entry=entry_price, current=current_price,
                                loss_pct=round(loss_pct, 2), user_id=s.user_id,
                            )
                        else:
                            action = "STRONG_SELL" if score <= -0.005 else "SELL"
                            logger.info("defi_monitor_sell_triggered", symbol=symbol, network=network, action=action, score=round(score, 4), user_id=s.user_id)

                        try:
                            sell_result = await asyncio.wait_for(
                                svc.sell_all_to_usdc(
                                    s.defi_wallet_private_key_encrypted,
                                    token_address,
                                    slippage=s.defi_slippage / 100,
                                    fee=svc.get_token_fee(symbol),
                                ),
                                timeout=180,
                            )
                            status = sell_result.get("status")
                            if status == "no_balance":
                                continue
                            tx = sell_result.get("tx_hash", "N/A")
                            if is_stop_loss:
                                await TelegramService().send_message(
                                    f"🛑 <b>DeFi Stop-Loss Triggered</b> <code>{symbol}</code> [{network}]\n"
                                    f"Entry: <code>${entry_price:,.6g}</code> → Now: <code>${current_price:,.6g}</code>\n"
                                    f"Loss: <code>{loss_pct:.2f}%</code> (SL: {s.defi_stop_loss_percent}%)\n"
                                    f"Tx: <code>{tx}</code>"
                                )
                            else:
                                await TelegramService().send_message(
                                    f"🔴 <b>DeFi Auto-Exit</b> <code>{symbol}</code> [{network}]\n"
                                    f"Signal: <b>{action}</b> (score {score:+.4f})\n"
                                    f"Price: <code>${current_price:,.6g}</code>\n"
                                    f"Tx: <code>{tx}</code>"
                                )
                            # Clear entry price after any successful sell
                            updated_entries = dict(s.defi_entry_prices)
                            updated_entries.pop(symbol, None)
                            s.defi_entry_prices = updated_entries
                            await db.commit()
                        except asyncio.TimeoutError:
                            logger.warning("defi_monitor_sell_timeout", symbol=symbol, network=network)
                            await TelegramService().send_message(
                                f"⚠️ <b>DeFi Auto-Exit Timeout</b> <code>{symbol}</code> [{network}]\nTransaction took >180s."
                            )
                        except Exception as exc:
                            logger.error("defi_monitor_sell_failed", symbol=symbol, network=network, error=str(exc))
                            await TelegramService().send_message(
                                f"⚠️ <b>DeFi Auto-Exit Failed</b> <code>{symbol}</code> [{network}]\n<code>{exc}</code>"
                            )

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("monitor_defi_positions_error", error=str(exc))


@celery_app.task(name="app.workers.tasks.monitor_gmx_positions", bind=True)
def monitor_gmx_positions(self):
    async def _run():
        from app.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.settings import Settings
        from app.services.gmx_service import GMXService
        from app.services.exchange_service import ExchangeService
        from app.services.telegram_service import TelegramService

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Settings).where(
                    Settings.bot_enabled == True,
                    Settings.auto_trade == True,
                )
            )
            active_settings = result.scalars().all()
            exchange_svc = ExchangeService()

            for s in active_settings:
                if not s.gmx_enabled:
                    continue
                if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
                    continue

                open_positions = dict(s.gmx_open_positions)
                if not open_positions:
                    continue

                svc = GMXService()
                sl_pct = s.gmx_sl_percent / 100.0

                for symbol, pos_info in list(open_positions.items()):
                    is_long = pos_info.get("is_long", True)
                    entry_price = float(pos_info.get("entry_price", 0.0))
                    size_usd = float(pos_info.get("size_usd", 0.0))

                    if entry_price <= 0 or size_usd <= 0:
                        continue

                    try:
                        market_data = await exchange_svc.get_market_data(symbol)
                    except Exception as exc:
                        logger.warning("gmx_monitor_price_failed", symbol=symbol, error=str(exc))
                        continue

                    current_price = float(market_data.get("price") or 0.0)
                    if current_price <= 0:
                        continue

                    # Stop-loss: LONG → price fell; SHORT → price rose
                    if is_long:
                        is_sl = current_price <= entry_price * (1.0 - sl_pct)
                        loss_pct = (entry_price - current_price) / entry_price * 100
                    else:
                        is_sl = current_price >= entry_price * (1.0 + sl_pct)
                        loss_pct = (current_price - entry_price) / entry_price * 100

                    if not is_sl:
                        logger.info(
                            "gmx_monitor_holding",
                            symbol=symbol, direction="LONG" if is_long else "SHORT",
                            entry=entry_price, current=current_price,
                        )
                        continue

                    logger.warning(
                        "gmx_monitor_stop_loss",
                        symbol=symbol, is_long=is_long,
                        entry=entry_price, current=current_price,
                        loss_pct=round(loss_pct, 2),
                    )

                    try:
                        close_result = await asyncio.wait_for(
                            svc.close_position(
                                s.defi_wallet_private_key_encrypted,
                                symbol, is_long, size_usd,
                                current_price=current_price,
                            ),
                            timeout=180,
                        )
                        if close_result.get("status") == "success":
                            tx = close_result.get("tx_hash", "N/A")
                            direction_str = "LONG" if is_long else "SHORT"
                            await TelegramService().send_message(
                                f"🛑 <b>GMX Stop-Loss Triggered</b> <code>{symbol}</code>\n"
                                f"Direction: <b>{direction_str}</b>\n"
                                f"Entry: <code>${entry_price:,.6g}</code> → Now: <code>${current_price:,.6g}</code>\n"
                                f"Loss: <code>{loss_pct:.2f}%</code> (SL: {s.gmx_sl_percent}%)\n"
                                f"Size closed: <code>${size_usd:.2f}</code>\n"
                                f"Tx: <code>{tx}</code>\n"
                                f"⚠️ Close order pending keeper execution"
                            )
                            open_positions.pop(symbol, None)
                            s.gmx_open_positions = open_positions
                            await db.commit()
                        else:
                            logger.error("gmx_sl_close_failed", symbol=symbol, error=close_result.get("error"))
                            await TelegramService().send_message(
                                f"⚠️ <b>GMX SL Close Failed</b> <code>{symbol}</code>\n"
                                f"<code>{close_result.get('error')}</code>"
                            )
                    except asyncio.TimeoutError:
                        logger.warning("gmx_sl_close_timeout", symbol=symbol)
                        await TelegramService().send_message(
                            f"⚠️ <b>GMX SL Close Timeout</b> <code>{symbol}</code>\nTransaction took >180s."
                        )
                    except Exception as exc:
                        logger.error("gmx_sl_close_error", symbol=symbol, error=str(exc))
                        await TelegramService().send_message(
                            f"⚠️ <b>GMX SL Close Error</b> <code>{symbol}</code>\n<code>{exc}</code>"
                        )

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("monitor_gmx_positions_error", error=str(exc))
