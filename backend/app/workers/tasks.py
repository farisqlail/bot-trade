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
                opportunities = await scanner.scan_opportunities(
                    user_id=s.user_id,
                    deep_analysis=True,
                    execute_paper=s.auto_trade,
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
                    await TelegramService().notify_trade_closed(
                        symbol=closed.symbol,
                        pnl=closed.pnl or 0.0,
                        pnl_percent=closed.pnl_percent or 0.0,
                        exit_price=closed.exit_price or price,
                        reason=reason,
                    )

            await db.commit()

    try:
        run_async(_run())
    except Exception as exc:
        logger.error("sl_tp_check_error", error=str(exc))
