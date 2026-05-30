import asyncio
from app.workers.celery_app import celery_app
from app.core.logging_config import get_logger
from app.utils.crypto import safe_decrypt as _safe_decrypt

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

            from app.services.telegram_service import TelegramService
            from app.models.settings import Settings as _Settings

            # Cache settings per user to avoid repeated queries
            user_settings_cache: dict = {}

            async def _get_user_settings(uid: int):
                if uid not in user_settings_cache:
                    _sr = await db.execute(select(_Settings).where(_Settings.user_id == uid))
                    user_settings_cache[uid] = _sr.scalar_one_or_none()
                return user_settings_cache[uid]

            trading_svc = TradingService(db)
            for trade in open_trades:
                price = prices.get(trade.symbol)
                if not price:
                    continue

                _s = await _get_user_settings(trade.user_id)
                is_long = trade.direction == TradeDirection.LONG

                # Trailing SL: update virtual stop_loss in trade object
                if _s and _s.trailing_sl_enabled and price > 0:
                    trail_pct = _s.trailing_sl_percent / 100.0
                    paper_peaks = dict(_s.paper_peak_prices)
                    peak_key = str(trade.id)
                    current_peak = float(paper_peaks.get(peak_key, trade.entry_price))

                    if is_long:
                        new_peak = max(current_peak, price)
                        new_trail_sl = new_peak * (1.0 - trail_pct)
                        if new_trail_sl > trade.stop_loss and new_peak > trade.entry_price:
                            trade.stop_loss = new_trail_sl
                    else:
                        new_peak = min(current_peak, price) if current_peak > 0 else price
                        new_trail_sl = new_peak * (1.0 + trail_pct)
                        if 0 < new_trail_sl < trade.stop_loss and new_peak < trade.entry_price:
                            trade.stop_loss = new_trail_sl

                    if new_peak != current_peak:
                        paper_peaks[peak_key] = new_peak
                        _s.paper_peak_prices = paper_peaks

                if is_long:
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
                    # Clear peak price after close
                    if _s:
                        paper_peaks = dict(_s.paper_peak_prices)
                        paper_peaks.pop(str(trade.id), None)
                        _s.paper_peak_prices = paper_peaks
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


@celery_app.task(name="app.workers.tasks.send_weekly_report", bind=True)
def send_weekly_report(self):
    async def _run():
        from datetime import timedelta
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.settings import Settings
        from app.services.trading_service import TradingService
        from app.services.telegram_service import TelegramService
        import datetime as _dt

        tg = TelegramService()
        now = _dt.datetime.now(_dt.timezone.utc)
        week_ago = now - timedelta(days=7)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Settings).where(Settings.bot_enabled == True))
            active_settings = result.scalars().all()
            if not active_settings:
                return

            for s in active_settings:
                try:
                    svc = TradingService(db)
                    analytics = await svc.get_performance_analytics(s.user_id, days=7)
                    await tg.send_weekly_report(
                        total_trades=analytics["total_trades"],
                        winning_trades=analytics["winning_trades"],
                        losing_trades=analytics["losing_trades"],
                        win_rate=analytics["win_rate"],
                        total_pnl=analytics["total_pnl"],
                        best_trade=analytics["best_trade"],
                        worst_trade=analytics["worst_trade"],
                        profit_factor=analytics["profit_factor"],
                        sharpe_ratio=analytics["sharpe_ratio"],
                        max_drawdown=analytics["max_drawdown"],
                        start_date=week_ago.strftime("%d %b"),
                        end_date=now.strftime("%d %b %Y"),
                    )
                except Exception as exc:
                    logger.error("weekly_report_user_error", user_id=s.user_id, error=str(exc))

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("send_weekly_report_error", error=str(exc))


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
                _api_key = _safe_decrypt(s.polymarket_api_key)
                _api_secret = _safe_decrypt(s.polymarket_api_secret)
                if not s or not _api_key or not _api_secret:
                    continue

                order_svc = BybitOrderService(
                    api_key=_api_key,
                    api_secret=_api_secret,
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
                    # Clean up trailing peak
                    if s and s.trailing_sl_enabled:
                        peaks = dict(s.trailing_peak_prices)
                        peaks.pop(str(trade.id), None)
                        s.trailing_peak_prices = peaks
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
                polymarket_score = float(market_data.get("polymarket_bias_score") or 0.0)
                polymarket_count = int(market_data.get("polymarket_market_count") or 0)
                try:
                    from app.services.sentiment_service import SentimentService
                    _ss = SentimentService()
                    _fng = await _ss.get_fear_greed_score()
                    _trending = await _ss.get_trending_symbols()
                except Exception:
                    _fng, _trending = 0.0, set()
                base_sym = trade.symbol.replace("USDT", "").replace("USDC", "").upper()
                _trending_bonus = 0.10 if base_sym in _trending else 0.0
                if polymarket_count > 0:
                    sentiment_score = polymarket_score * 0.50 + _fng * 0.35 + _trending_bonus * 0.15
                else:
                    sentiment_score = _fng * 0.85 + _trending_bonus * 0.15
                score = (momentum * 0.45) + (change_score * 0.25) + (sentiment_score * 0.30)

                is_long = trade.direction == TradeDirection.LONG
                # Signal flip: LONG + bearish signal, or SHORT + bullish signal
                signal_flip = (is_long and score <= -0.005) or (not is_long and score >= 0.005)
                if not signal_flip:
                    if current_price and trade.entry_price:
                        if s.trailing_sl_enabled:
                            # Trailing SL: track peak price and keep SL at (peak - trail_pct)
                            trail_pct = s.trailing_sl_percent / 100.0
                            peaks = dict(s.trailing_peak_prices)
                            peak_key = str(trade.id)
                            current_peak = float(peaks.get(peak_key, trade.entry_price))

                            if is_long:
                                new_peak = max(current_peak, current_price)
                                new_trail_sl = new_peak * (1.0 - trail_pct)
                            else:
                                new_peak = min(current_peak, current_price) if current_peak > 0 else current_price
                                new_trail_sl = new_peak * (1.0 + trail_pct)

                            if new_peak != current_peak:
                                peaks[peak_key] = new_peak
                                s.trailing_peak_prices = peaks

                            current_sl = float(bybit_pos.get("stopLoss") or 0)
                            should_update = (
                                (is_long and new_trail_sl > current_sl)
                                or (not is_long and 0 < new_trail_sl < current_sl)
                            )
                            if should_update and abs(new_trail_sl - trade.stop_loss) > 0.0001:
                                try:
                                    await order_svc.set_trading_stop(symbol=trade.symbol, stop_loss=new_trail_sl)
                                    trade.stop_loss = new_trail_sl
                                    logger.info(
                                        "bybit_monitor_trailing_sl_updated",
                                        symbol=trade.symbol, sl=new_trail_sl, peak=new_peak,
                                    )
                                except Exception as exc:
                                    logger.warning("bybit_monitor_trailing_sl_failed", symbol=trade.symbol, error=str(exc))
                        else:
                            # Fallback: move SL to breakeven when profit >= 1.5%
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
                    # Clean up trailing peak for this trade
                    if s and s.trailing_sl_enabled:
                        peaks = dict(s.trailing_peak_prices)
                        peaks.pop(str(trade.id), None)
                        s.trailing_peak_prices = peaks
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

                        # Stop-loss check: static and trailing
                        entry_prices = s.defi_entry_prices
                        entry_price = float(entry_prices.get(symbol, 0.0))
                        sl_pct = s.defi_stop_loss_percent / 100.0
                        is_stop_loss = (
                            entry_price > 0
                            and current_price > 0
                            and current_price <= entry_price * (1.0 - sl_pct)
                        )

                        # Trailing SL for DeFi: track peak price, exit if drops trail_pct from peak
                        is_trailing_sl = False
                        if not is_stop_loss and s.trailing_sl_enabled and current_price > 0:
                            trail_pct = s.trailing_sl_percent / 100.0
                            defi_peaks = dict(s.defi_peak_prices)
                            current_peak = float(defi_peaks.get(symbol, entry_price if entry_price > 0 else current_price))
                            new_peak = max(current_peak, current_price)
                            if new_peak != current_peak:
                                defi_peaks[symbol] = new_peak
                                s.defi_peak_prices = defi_peaks
                            if current_price <= new_peak * (1.0 - trail_pct) and new_peak > entry_price:
                                is_trailing_sl = True
                                loss_from_peak = (new_peak - current_price) / new_peak * 100

                        if not is_stop_loss and not is_trailing_sl and score > -0.001:
                            logger.info("defi_monitor_holding_ok", symbol=symbol, network=network, score=round(score, 4), price=current_price)
                            continue

                        if is_trailing_sl:
                            action = "TRAILING_SL"
                            loss_pct = loss_from_peak
                            logger.warning(
                                "defi_monitor_trailing_sl_triggered",
                                symbol=symbol, network=network,
                                peak=new_peak, current=current_price,
                                loss_pct=round(loss_pct, 2), user_id=s.user_id,
                            )
                        elif is_stop_loss:
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
                            loss_pct = 0.0
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
                            if is_trailing_sl:
                                await TelegramService().send_message(
                                    f"🔶 <b>DeFi Trailing SL Triggered</b> <code>{symbol}</code> [{network}]\n"
                                    f"Peak: <code>${new_peak:,.6g}</code> → Now: <code>${current_price:,.6g}</code>\n"
                                    f"Drop from peak: <code>{loss_pct:.2f}%</code> (Trail: {s.trailing_sl_percent}%)\n"
                                    f"Tx: <code>{tx}</code>"
                                )
                            elif is_stop_loss:
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
                            # Clear entry price and peak after any successful sell
                            updated_entries = dict(s.defi_entry_prices)
                            updated_entries.pop(symbol, None)
                            s.defi_entry_prices = updated_entries
                            updated_peaks = dict(s.defi_peak_prices)
                            updated_peaks.pop(symbol, None)
                            s.defi_peak_prices = updated_peaks
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


@celery_app.task(name="app.workers.tasks.check_spot_price_alerts", bind=True)
def check_spot_price_alerts(self):
    async def _run():
        import redis.asyncio as aioredis
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.spot_watchlist import SpotWatchlist
        from app.models.spot_trade import SpotTrade, SpotTradeStatus
        from app.services.spot_market_service import SpotMarketService
        from app.services.telegram_service import TelegramService
        from app.config import settings

        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        tg = TelegramService()
        spot_svc = SpotMarketService()

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(SpotWatchlist).where(SpotWatchlist.alert_enabled == True)
                )
                watchlist_items = result.scalars().all()

                if not watchlist_items:
                    return

                # Group by user, collect unique symbols
                user_symbols: dict[int, list[str]] = {}
                for item in watchlist_items:
                    user_symbols.setdefault(item.user_id, [])
                    if item.symbol not in user_symbols[item.user_id]:
                        user_symbols[item.user_id].append(item.symbol)

                all_symbols = list({s for syms in user_symbols.values() for s in syms})
                prices = await spot_svc.get_multiple_prices(all_symbols)
                price_map = {p["symbol"]: p for p in prices}

                for item in watchlist_items:
                    price_data = price_map.get(item.symbol)
                    if not price_data:
                        continue

                    current_price = price_data["price"]
                    if not current_price:
                        continue

                    try:
                        # --- a. Buy alert ---
                        if item.target_buy_price and item.target_buy_price > 0:
                            threshold = item.target_buy_price * 1.02
                            if current_price <= threshold:
                                alert_key = f"spot_alert:buy:{item.user_id}:{item.symbol}"
                                if not await redis_client.get(alert_key):
                                    await tg.send_message(
                                        f"🟢 <b>BUY ALERT</b>: <code>{item.symbol}</code> sekarang "
                                        f"<code>${current_price:,.6g}</code>, mendekati target beli kamu "
                                        f"<code>${item.target_buy_price:,.6g}</code>"
                                    )
                                    await redis_client.setex(alert_key, 86400, "1")

                        # --- b. Sell alert (only if user has COMPLETED trade for this symbol) ---
                        if item.target_sell_price and item.target_sell_price > 0:
                            trade_result = await db.execute(
                                select(SpotTrade).where(
                                    SpotTrade.user_id == item.user_id,
                                    SpotTrade.symbol == item.symbol,
                                    SpotTrade.status == SpotTradeStatus.COMPLETED,
                                ).limit(1)
                            )
                            has_completed_trade = trade_result.scalar_one_or_none() is not None
                            if has_completed_trade:
                                threshold = item.target_sell_price * 0.98
                                if current_price >= threshold:
                                    alert_key = f"spot_alert:sell:{item.user_id}:{item.symbol}"
                                    if not await redis_client.get(alert_key):
                                        await tg.send_message(
                                            f"🔴 <b>SELL ALERT</b>: <code>{item.symbol}</code> sekarang "
                                            f"<code>${current_price:,.6g}</code>, mendekati target jual kamu "
                                            f"<code>${item.target_sell_price:,.6g}</code>"
                                        )
                                        await redis_client.setex(alert_key, 86400, "1")

                        # --- c. Heuristic signal alert (BUY only, once per 24h) ---
                        signal_key = f"spot_alert:signal:{item.user_id}:{item.symbol}"
                        if not await redis_client.get(signal_key):
                            analysis = spot_svc.analyze_spot_signal(item.symbol, price_data)
                            if analysis["signal"] == "BUY":
                                change = price_data.get("change_24h", 0.0)
                                await tg.send_message(
                                    f"📊 <b>SPOT SIGNAL</b>: <code>{item.symbol}</code> turun "
                                    f"<code>{abs(change):.1f}%</code>, potensi entry menarik di "
                                    f"<code>${current_price:,.6g}</code>"
                                )
                                await redis_client.setex(signal_key, 86400, "1")

                    except Exception as exc:
                        logger.warning(
                            "spot_alert_item_error",
                            symbol=item.symbol,
                            user_id=item.user_id,
                            error=str(exc),
                        )

        finally:
            await redis_client.aclose()

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("check_spot_price_alerts_error", error=str(exc))


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

                    # Static stop-loss check
                    if is_long:
                        is_sl = current_price <= entry_price * (1.0 - sl_pct)
                        loss_pct = (entry_price - current_price) / entry_price * 100
                    else:
                        is_sl = current_price >= entry_price * (1.0 + sl_pct)
                        loss_pct = (current_price - entry_price) / entry_price * 100

                    # Trailing SL for GMX
                    is_trailing_sl = False
                    trailing_loss_pct = 0.0
                    if not is_sl and s.trailing_sl_enabled and current_price > 0:
                        trail_pct = s.trailing_sl_percent / 100.0
                        gmx_peaks = dict(s.gmx_peak_prices)
                        if is_long:
                            current_peak = float(gmx_peaks.get(symbol, entry_price))
                            new_peak = max(current_peak, current_price)
                            if new_peak != current_peak:
                                gmx_peaks[symbol] = new_peak
                                s.gmx_peak_prices = gmx_peaks
                            if current_price <= new_peak * (1.0 - trail_pct) and new_peak > entry_price:
                                is_trailing_sl = True
                                trailing_loss_pct = (new_peak - current_price) / new_peak * 100
                        else:
                            current_peak = float(gmx_peaks.get(symbol, entry_price))
                            new_peak = min(current_peak, current_price) if current_peak > 0 else current_price
                            if new_peak != current_peak:
                                gmx_peaks[symbol] = new_peak
                                s.gmx_peak_prices = gmx_peaks
                            if current_price >= new_peak * (1.0 + trail_pct) and new_peak < entry_price:
                                is_trailing_sl = True
                                trailing_loss_pct = (current_price - new_peak) / new_peak * 100

                    if not is_sl and not is_trailing_sl:
                        logger.info(
                            "gmx_monitor_holding",
                            symbol=symbol, direction="LONG" if is_long else "SHORT",
                            entry=entry_price, current=current_price,
                        )
                        continue

                    if is_trailing_sl and not is_sl:
                        loss_pct = trailing_loss_pct

                    logger.warning(
                        "gmx_monitor_stop_loss" if is_sl else "gmx_monitor_trailing_sl",
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
                            sl_label = "Trailing SL" if is_trailing_sl else "Stop-Loss"
                            await TelegramService().send_message(
                                f"🛑 <b>GMX {sl_label} Triggered</b> <code>{symbol}</code>\n"
                                f"Direction: <b>{direction_str}</b>\n"
                                f"Entry: <code>${entry_price:,.6g}</code> → Now: <code>${current_price:,.6g}</code>\n"
                                f"Loss: <code>{loss_pct:.2f}%</code>\n"
                                f"Size closed: <code>${size_usd:.2f}</code>\n"
                                f"Tx: <code>{tx}</code>\n"
                                f"⚠️ Close order pending keeper execution"
                            )
                            open_positions.pop(symbol, None)
                            s.gmx_open_positions = open_positions
                            # Clear GMX peak price for this symbol
                            gmx_peaks = dict(s.gmx_peak_prices)
                            gmx_peaks.pop(symbol, None)
                            s.gmx_peak_prices = gmx_peaks
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
