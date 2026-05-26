import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Settings
from app.models.trade import Trade, TradeStatus, TradeDirection
from app.schemas.trade import TradeCreate
from app.services.ai_service import AIService
from app.services.exchange_service import ExchangeService
from app.services.trading_service import TradingService
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ScannerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.exchange_svc = ExchangeService()
        self.ai_svc = AIService(db)
        self.trading_svc = TradingService(db)

    async def _get_settings(self, user_id: int) -> Settings | None:
        result = await self.db.execute(select(Settings).where(Settings.user_id == user_id))
        return result.scalar_one_or_none()

    def _heuristic_signal(self, symbol: str, market_data: dict) -> dict:
        candles = market_data.get("candles") or []
        current_price = float(market_data.get("price") or 0.0)
        if len(candles) >= 2 and candles[0]["close"]:
            momentum = (candles[-1]["close"] - candles[0]["close"]) / candles[0]["close"]
        else:
            momentum = 0.0

        change_score = float(market_data.get("change_24h") or 0.0) / 100.0
        sentiment_score = float(market_data.get("polymarket_bias_score") or 0.0)
        score = (momentum * 0.45) + (change_score * 0.25) + (sentiment_score * 0.30)

        if score >= 0.001:
            action = "BUY"
            sentiment = "STRONG_BUY" if score >= 0.005 else "BUY"
            trend = "BULLISH"
            suggested_sl = current_price * 0.985
            suggested_tp = current_price * 1.03
        elif score <= -0.001:
            action = "SELL"
            sentiment = "STRONG_SELL" if score <= -0.005 else "SELL"
            trend = "BEARISH"
            suggested_sl = current_price * 1.015
            suggested_tp = current_price * 0.97
        else:
            action = "HOLD"
            sentiment = "HOLD"
            trend = "SIDEWAYS"
            suggested_sl = current_price * 0.99 if current_price else 0.0
            suggested_tp = current_price * 1.01 if current_price else 0.0

        summary = market_data.get("polymarket_markets") or []
        top_summary = "; ".join(
            f"{item['question']} (yes {item['yes_price']:.2f})"
            for item in summary[:2]
        ) or "No strong Polymarket market context found."

        return {
            "symbol": symbol,
            "score": round(score, 4),
            "trend": trend,
            "sentiment": sentiment,
            "recommended_action": action,
            "suggested_entry": round(current_price, 6),
            "suggested_sl": round(suggested_sl, 6),
            "suggested_tp": round(suggested_tp, 6),
            "price_at_analysis": round(current_price, 6),
            "change_24h": round(float(market_data.get("change_24h") or 0.0), 4),
            "volume_24h": float(market_data.get("volume_24h") or 0.0),
            "polymarket_bias_score": round(float(market_data.get("polymarket_bias_score") or 0.0), 4),
            "polymarket_market_count": int(market_data.get("polymarket_market_count") or 0),
            "analysis_text": f"Momentum {momentum:.4f}; 24h change {change_score:.4f}; Polymarket bias {sentiment_score:.4f}. {top_summary}",
            "confidence": min(abs(score) * 8, 0.95),
            "market_data": market_data,
        }

    async def _execute_defi_trade(self, user_id: int, settings: Settings, opportunity: dict) -> dict | None:
        from app.services.defi_service import DeFiService

        symbol = opportunity["symbol"]
        action = opportunity.get("recommended_action")
        is_buy = action in {"BUY", "STRONG_BUY"}
        is_sell = action in {"SELL", "STRONG_SELL"}
        if not is_buy and not is_sell:
            return None

        service = DeFiService(network=settings.defi_network or "arbitrum")
        token_address = await service.get_token_address(symbol)
        if not token_address:
            return None

        token_fee = service.get_token_fee(symbol)

        try:
            token_raw, _ = await service.get_token_balance(settings.defi_wallet_address, token_address)
        except Exception as exc:
            logger.warning("defi_balance_check_failed", symbol=symbol, error=str(exc))
            return None

        in_position = token_raw > 0
        result = None

        try:
            if is_buy and not in_position:
                balance_info = await service.get_balance(settings.defi_wallet_address)
                usdc_available = balance_info["usdc_balance"]
                trade_amount = round(usdc_available * (settings.defi_trade_percent / 100), 2)
                if trade_amount < 0.5:
                    logger.info("defi_skip_buy_low_usdc", user_id=user_id, symbol=symbol, usdc=usdc_available)
                    return None
                result = await service.swap_usdc_to_token(
                    settings.defi_wallet_private_key_encrypted,
                    token_address,
                    trade_amount,
                    slippage=settings.defi_slippage / 100,
                    fee=token_fee,
                )
            elif is_sell and in_position:
                result = await service.sell_all_to_usdc(
                    settings.defi_wallet_private_key_encrypted,
                    token_address,
                    slippage=settings.defi_slippage / 100,
                    fee=token_fee,
                )
        except Exception as exc:
            logger.error("defi_swap_failed", user_id=user_id, symbol=symbol, action=action, error=str(exc))
            return None

        if result and result.get("status") == "success":
            from app.services.telegram_service import TelegramService
            emoji = "🟢" if is_buy else "🔴"
            await TelegramService().send_message(
                f"🔗 <b>DeFi Trade Executed</b>\n\n"
                f"Pair: <code>{symbol}</code>\n"
                f"Direction: {emoji} {action}\n"
                f"Network: <code>{settings.defi_network or 'arbitrum'}</code>\n"
                f"TX: <code>{result.get('tx_hash', 'N/A')}</code>\n"
                f"Gas used: {result.get('gas_used', 'N/A')}"
            )
            logger.info("defi_trade_success", user_id=user_id, symbol=symbol, action=action, tx=result.get("tx_hash"))

        return result

    async def _open_paper_trade_if_needed(self, user_id: int, settings: Settings, opportunity: dict):
        action = opportunity["recommended_action"]
        if action not in {"BUY", "SELL", "STRONG_BUY", "STRONG_SELL"}:
            return None

        result = await self.db.execute(
            select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.symbol == opportunity["symbol"],
                    Trade.status == TradeStatus.OPEN,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        trade_data = TradeCreate(
            symbol=opportunity["symbol"],
            direction=TradeDirection.LONG if action in {"BUY", "STRONG_BUY"} else TradeDirection.SHORT,
            entry_price=opportunity["suggested_entry"],
            stop_loss=opportunity["suggested_sl"],
            take_profit=opportunity["suggested_tp"],
            risk_percent=settings.risk_percent,
            leverage=settings.leverage,
            notes="auto_paper_trade:polymarket_sentiment+bybit_data",
        )
        trade = await self.trading_svc.create_trade(user_id, trade_data, settings.paper_balance)
        from app.services.telegram_service import TelegramService
        direction_str = "LONG" if action in {"BUY", "STRONG_BUY"} else "SHORT"
        await TelegramService().notify_trade_opened(
            symbol=opportunity["symbol"],
            direction=direction_str,
            entry_price=opportunity["suggested_entry"],
            stop_loss=opportunity["suggested_sl"],
            take_profit=opportunity["suggested_tp"],
            score=opportunity.get("score"),
            sentiment=opportunity.get("sentiment"),
            confidence=opportunity.get("confidence"),
            volume_24h=opportunity.get("volume_24h"),
            change_24h=opportunity.get("change_24h"),
        )
        return trade

    async def scan_opportunities(
        self,
        user_id: int,
        deep_analysis: bool = True,
        execute_paper: bool = False,
    ) -> list[dict]:
        settings = await self._get_settings(user_id)

        if settings and settings.scan_all_coins:
            min_vol = settings.min_volume_filter
            max_coins = settings.max_scan_coins
            all_tickers = await self.exchange_svc.get_all_tickers(min_turnover_usd=min_vol)
            watchlist = [t["symbol"] for t in all_tickers[:max_coins]]
            logger.info(
                "scanner_all_coins_mode",
                total_eligible=len(all_tickers),
                scanning=len(watchlist),
                min_volume_usd=min_vol,
            )
        elif settings and (settings.notification_settings or {}).get("scanner_watchlist"):
            watchlist = self.exchange_svc.get_watchlist(settings.scanner_watchlist)
        else:
            min_vol = settings.min_volume_filter if settings else 1_000_000.0
            all_tickers = await self.exchange_svc.get_all_tickers(min_turnover_usd=min_vol)
            watchlist = [t["symbol"] for t in all_tickers[:30]]
            logger.info(
                "scanner_top_movers_mode",
                scanning=len(watchlist),
                min_volume_usd=min_vol,
            )

        # Deduplicate preserving order
        watchlist = list(dict.fromkeys(watchlist))

        # DeFi-only scan: restrict to coins with known Arbitrum ERC-20 addresses
        if settings and settings.defi_enabled and settings.defi_only_scan:
            from app.services.defi_service import ARBITRUM_KNOWN_TOKENS
            arbitrum_symbols = set(ARBITRUM_KNOWN_TOKENS.keys())
            before_count = len(watchlist)
            filtered = [s for s in watchlist if s in arbitrum_symbols]
            if filtered:
                watchlist = filtered
                logger.info("scanner_defi_only_filter", before=before_count, after=len(filtered))
            else:
                logger.warning("scanner_defi_only_filter_empty_fallback", watchlist_size=before_count)

        fetch_sem = asyncio.Semaphore(3)

        async def _fetch_symbol(symbol: str):
            async with fetch_sem:
                for attempt in range(3):
                    try:
                        return symbol, await self.exchange_svc.get_market_data(symbol)
                    except Exception as exc:
                        if attempt == 2:
                            logger.warning("scanner_symbol_fetch_failed", symbol=symbol, error=str(exc))
                            return symbol, None
                        await asyncio.sleep(1.5 ** attempt)

        fetch_results = await asyncio.gather(*[_fetch_symbol(s) for s in watchlist])
        opportunities = [
            self._heuristic_signal(symbol, market_data)
            for symbol, market_data in fetch_results
            if market_data is not None
        ]

        if not opportunities:
            raise ValueError("No market data available from Bybit for the current watchlist")

        opportunities.sort(key=lambda item: abs(item["score"]), reverse=True)

        # Save heuristic results for ALL scanned symbols (no AI cost).
        # AI will create newer records for top N, which the cached endpoint will prefer.
        for opp in opportunities:
            await self.ai_svc.save_heuristic_result(opp["symbol"], opp, opp.get("market_data", {}))

        if deep_analysis and settings and settings.ai_analysis_enabled:
            async def _run_ai(opportunity: dict):
                try:
                    analysis = await self.ai_svc.analyze_market(opportunity["symbol"], opportunity["market_data"])
                    opportunity.update(
                        {
                            "trend": analysis.trend or opportunity["trend"],
                            "sentiment": analysis.sentiment or opportunity["sentiment"],
                            "recommended_action": analysis.recommended_action or opportunity["recommended_action"],
                            "suggested_entry": analysis.suggested_entry or opportunity["suggested_entry"],
                            "suggested_sl": analysis.suggested_sl or opportunity["suggested_sl"],
                            "suggested_tp": analysis.suggested_tp or opportunity["suggested_tp"],
                            "analysis_text": analysis.analysis_text,
                            "confidence": analysis.confidence if analysis.confidence is not None else opportunity["confidence"],
                            "analysis_id": analysis.id,
                            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
                        }
                    )
                except Exception as exc:
                    logger.warning("scanner_ai_analysis_failed", symbol=opportunity["symbol"], error=str(exc))
                    opportunity["analysis_text"] = (
                        f"{opportunity['analysis_text']} AI fallback active because provider failed."
                    )

            ai_limit = 5 if (settings and settings.scan_all_coins) else 3
            await asyncio.gather(*[_run_ai(opp) for opp in opportunities[:ai_limit]])

        if execute_paper and settings and settings.auto_trade:
            for opportunity in opportunities[:5]:
                try:
                    trade = await self._open_paper_trade_if_needed(user_id, settings, opportunity)
                    if trade:
                        opportunity["paper_trade_id"] = trade.id
                except Exception as exc:
                    logger.warning("scanner_paper_trade_failed", symbol=opportunity["symbol"], error=str(exc))

        if (
            settings
            and settings.defi_enabled
            and settings.defi_wallet_address
            and settings.defi_wallet_private_key_encrypted
            and opportunities
        ):
            from app.services.defi_service import DeFiService
            _defi_svc = DeFiService(network=settings.defi_network or "arbitrum")
            traded_opp = None
            for candidate in opportunities[:5]:
                if candidate.get("recommended_action") not in {"BUY", "STRONG_BUY", "SELL", "STRONG_SELL"}:
                    continue
                token_addr = await _defi_svc.get_token_address(candidate["symbol"])
                if not token_addr:
                    logger.info("defi_skip_no_address", symbol=candidate["symbol"])
                    continue
                traded_opp = candidate
                break

            if traded_opp:
                try:
                    defi_result = await asyncio.wait_for(
                        self._execute_defi_trade(user_id, settings, traded_opp),
                        timeout=180,
                    )
                    if defi_result:
                        traded_opp["defi_tx"] = defi_result.get("tx_hash")
                        traded_opp["defi_status"] = defi_result.get("status")
                except asyncio.TimeoutError:
                    logger.warning("defi_trade_timeout", user_id=user_id, symbol=traded_opp["symbol"])
                except Exception as exc:
                    logger.warning("scanner_defi_trade_failed", symbol=traded_opp["symbol"], error=str(exc))

        for opportunity in opportunities:
            opportunity.pop("market_data", None)

        return opportunities
