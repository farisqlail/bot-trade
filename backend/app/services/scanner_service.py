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

    async def _execute_defi_trade(self, user_id: int, settings: Settings, opportunity: dict, network: str | None = None) -> dict | None:
        from app.services.defi_service import DeFiService

        symbol = opportunity["symbol"]
        action = opportunity.get("recommended_action")
        is_buy = action in {"BUY", "STRONG_BUY"}
        is_sell = action in {"SELL", "STRONG_SELL"}
        if not is_buy and not is_sell:
            return None

        effective_network = network or settings.defi_network or "arbitrum"
        service = DeFiService(network=effective_network)
        token_address = await service.get_token_address(symbol)
        if not token_address:
            return None

        token_fee = service.get_token_fee(symbol)

        from app.services.telegram_service import TelegramService as _TG

        try:
            token_raw, _ = await service.get_token_balance(settings.defi_wallet_address, token_address)
        except Exception as exc:
            logger.warning("defi_balance_check_failed", symbol=symbol, error=str(exc))
            await _TG().send_message(
                f"⚠️ <b>DeFi Skip</b> <code>{symbol}</code>\nBalance check failed: <code>{exc}</code>"
            )
            return None

        in_position = token_raw > 0
        result = None

        if is_buy and in_position:
            logger.info("defi_skip_already_in_position", symbol=symbol)
            current_price = opportunity.get("price_at_analysis", 0)
            tp_price = opportunity.get("suggested_tp", 0)
            await _TG().send_message_with_keyboard(
                f"ℹ️ <b>DeFi Skip BUY</b> <code>{symbol}</code>\n"
                f"Already holding token — in position, skip buy.\n"
                f"Current: <code>${current_price:,.6g}</code>  🎯 TP ref: <code>${tp_price:,.6g}</code>",
                inline_keyboard=[[
                    {"text": "💰 Take Profit (Sell Now)", "callback_data": f"defi_tp_{symbol}"}
                ]]
            )
            return None

        if is_sell and not in_position:
            logger.info("defi_skip_no_position_to_sell", symbol=symbol)
            return None

        try:
            if is_buy:
                balance_info = await service.get_balance(settings.defi_wallet_address)
                usdc_available = balance_info["usdc_balance"]
                active_usdc = balance_info.get("active_usdc_address")
                trade_amount = round(usdc_available * (settings.defi_trade_percent / 100), 2)
                if trade_amount < 0.5:
                    logger.info("defi_skip_buy_low_usdc", user_id=user_id, symbol=symbol, usdc=usdc_available)
                    await _TG().send_message(
                        f"⚠️ <b>DeFi Skip BUY</b> <code>{symbol}</code>\n"
                        f"USDC available: <code>${usdc_available:.2f}</code> — trade amount <code>${trade_amount:.2f}</code> < $0.50\n"
                        f"Top-up USDC or increase defi_trade_percent."
                    )
                    return None
                result = await service.swap_usdc_to_token(
                    settings.defi_wallet_private_key_encrypted,
                    token_address,
                    trade_amount,
                    slippage=settings.defi_slippage / 100,
                    fee=token_fee,
                    usdc_address=active_usdc,
                )
            elif is_sell:
                result = await service.sell_all_to_usdc(
                    settings.defi_wallet_private_key_encrypted,
                    token_address,
                    slippage=settings.defi_slippage / 100,
                    fee=token_fee,
                )
        except Exception as exc:
            logger.error("defi_swap_failed", user_id=user_id, symbol=symbol, action=action, error=str(exc))
            await _TG().send_message(
                f"⚠️ <b>DeFi Swap Failed</b> <code>{symbol}</code> {action}\n<code>{exc}</code>"
            )
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

            entry_prices = dict(settings.defi_entry_prices)
            if is_buy:
                entry_price = float(opportunity.get("price_at_analysis") or 0.0)
                if entry_price > 0:
                    entry_prices[symbol] = entry_price
                    logger.info("defi_entry_price_stored", symbol=symbol, entry_price=entry_price)
            else:
                entry_prices.pop(symbol, None)
            settings.defi_entry_prices = entry_prices
            await self.db.commit()

        return result

    async def _execute_gmx_trade(self, user_id: int, settings: Settings, opportunity: dict) -> dict | None:
        from app.services.gmx_service import GMXService
        from app.services.telegram_service import TelegramService as _TG

        symbol = opportunity["symbol"]
        action = opportunity.get("recommended_action")
        is_buy = action in {"BUY", "STRONG_BUY"}
        is_sell = action in {"SELL", "STRONG_SELL"}
        if not is_buy and not is_sell:
            return None

        svc = GMXService()
        if not svc.supports_symbol(symbol):
            return None

        is_long = is_buy  # BUY = LONG, SELL = SHORT
        current_price = float(opportunity.get("price_at_analysis") or 0.0)

        open_positions = dict(settings.gmx_open_positions)
        existing = open_positions.get(symbol)

        # Skip if same direction already open
        if existing and existing.get("is_long") == is_long:
            logger.info("gmx_skip_same_position", symbol=symbol, direction="LONG" if is_long else "SHORT")
            return None

        # Close opposite direction position first
        if existing and existing.get("is_long") != is_long:
            close_result = await svc.close_position(
                settings.defi_wallet_private_key_encrypted,
                symbol,
                existing["is_long"],
                existing.get("size_usd", 0.0),
                current_price=current_price,
            )
            if close_result.get("status") == "success":
                open_positions.pop(symbol, None)
                settings.gmx_open_positions = open_positions
                await self.db.commit()
                await _TG().send_message(
                    f"🔄 <b>GMX Position Closed</b> <code>{symbol}</code>\n"
                    f"Direction: {'LONG' if existing['is_long'] else 'SHORT'} → closing before flip\n"
                    f"Tx: <code>{close_result.get('tx_hash')}</code>"
                )
            else:
                logger.error("gmx_close_for_flip_failed", symbol=symbol, error=close_result.get("error"))
                return None

        # Get USDC balance for collateral calc
        try:
            from app.services.defi_service import DeFiService
            balance_info = await DeFiService(network="arbitrum").get_balance(settings.defi_wallet_address)
            usdc_available = balance_info["usdc_balance"]
        except Exception as exc:
            logger.error("gmx_balance_check_failed", symbol=symbol, error=str(exc))
            from app.services.telegram_service import TelegramService as _TG
            await _TG().send_message(
                f"⚠️ <b>GMX Skip</b> <code>{symbol}</code>\n"
                f"Balance check failed: <code>{exc}</code>\n"
                f"Pastikan Alchemy/RPC tersedia dan wallet address benar."
            )
            return None

        collateral_usdc = round(usdc_available * (settings.gmx_collateral_percent / 100), 2)
        if collateral_usdc < 1.0:
            await _TG().send_message(
                f"⚠️ <b>GMX Skip</b> <code>{symbol}</code>\n"
                f"USDC too low: ${usdc_available:.2f} (collateral: ${collateral_usdc:.2f} < $1.00)"
            )
            return None

        result = await svc.open_position(
            settings.defi_wallet_private_key_encrypted,
            symbol,
            is_long=is_long,
            collateral_usdc=collateral_usdc,
            leverage=settings.gmx_leverage,
            current_price=current_price,
        )

        if result.get("status") == "success":
            emoji = "🟢📈" if is_long else "🔴📉"
            await _TG().send_message(
                f"⚡ <b>GMX Futures Opened</b>\n\n"
                f"Pair: <code>{symbol}</code>\n"
                f"Direction: {emoji} {'LONG' if is_long else 'SHORT'}\n"
                f"Collateral: <code>${collateral_usdc:.2f} USDC</code>\n"
                f"Size: <code>${result.get('size_usd', 0):.2f}</code> ({settings.gmx_leverage}x)\n"
                f"Entry: <code>${current_price:,.6g}</code>\n"
                f"Tx: <code>{result.get('tx_hash')}</code>\n"
                f"⚠️ Order pending keeper execution (~1-10 sec)"
            )
            open_positions[symbol] = {
                "is_long": is_long,
                "entry_price": current_price,
                "size_usd": result.get("size_usd", 0.0),
                "collateral_usdc": collateral_usdc,
            }
            settings.gmx_open_positions = open_positions
            await self.db.commit()
            logger.info("gmx_trade_success", user_id=user_id, symbol=symbol, direction="LONG" if is_long else "SHORT", tx=result.get("tx_hash"))
        elif result.get("status") == "error":
            logger.error("gmx_trade_failed", symbol=symbol, error=result.get("error"))
            await _TG().send_message(
                f"⚠️ <b>GMX Trade Failed</b> <code>{symbol}</code>\n<code>{result.get('error')}</code>"
            )

        return result

    async def _execute_real_trade(self, user_id: int, settings: Settings, opportunity: dict) -> dict | None:
        from app.services.bybit_order_service import BybitOrderService
        from app.services.telegram_service import TelegramService

        api_key = settings.polymarket_api_key
        api_secret = settings.polymarket_api_secret
        if not api_key or not api_secret:
            logger.warning("real_trade_skip_no_api_key", user_id=user_id)
            return None

        symbol = opportunity["symbol"]
        action = opportunity.get("recommended_action")
        is_long = action in {"BUY", "STRONG_BUY"}
        is_short = action in {"SELL", "STRONG_SELL"}
        if not is_long and not is_short:
            return None

        side = "Buy" if is_long else "Sell"
        direction = TradeDirection.LONG if is_long else TradeDirection.SHORT
        testnet = settings.use_public_data_only
        order_svc = BybitOrderService(api_key=api_key, api_secret=api_secret, testnet=testnet)

        # Skip if position already open for this symbol
        try:
            positions = await order_svc.get_positions(symbol=symbol)
            for pos in positions:
                if pos.get("symbol") == symbol and float(pos.get("size", 0)) > 0:
                    logger.info("real_trade_skip_position_exists", user_id=user_id, symbol=symbol)
                    return None
        except Exception as exc:
            logger.warning("real_trade_position_check_failed", symbol=symbol, error=str(exc))
            return None

        try:
            balance = await order_svc.get_wallet_balance(coin="USDT")
        except Exception as exc:
            logger.warning("real_trade_balance_failed", user_id=user_id, error=str(exc))
            return None

        if balance < 1.0:
            logger.info("real_trade_skip_low_balance", user_id=user_id, balance=balance)
            return None

        entry_price = opportunity.get("suggested_entry") or 0.0
        if not entry_price:
            return None

        risk_amount = balance * (settings.risk_percent / 100)
        raw_qty = risk_amount / entry_price
        qty_str = f"{raw_qty:.3f}"

        try:
            await order_svc.set_leverage(symbol, settings.leverage)
        except Exception as exc:
            logger.warning("real_trade_set_leverage_failed", symbol=symbol, error=str(exc))

        try:
            result = await order_svc.place_order(
                symbol=symbol,
                side=side,
                qty=qty_str,
                stop_loss=opportunity.get("suggested_sl"),
                take_profit=opportunity.get("suggested_tp"),
            )
        except Exception as exc:
            logger.error("real_trade_order_failed", user_id=user_id, symbol=symbol, side=side, error=str(exc))
            return None

        order_id = result.get("orderId")
        avg_price = float(result.get("avgPrice") or entry_price or 0) or entry_price

        trade = Trade(
            user_id=user_id,
            exchange_order_id=order_id,
            symbol=symbol,
            direction=direction,
            status=TradeStatus.OPEN,
            entry_price=avg_price,
            stop_loss=opportunity["suggested_sl"],
            take_profit=opportunity["suggested_tp"],
            quantity=raw_qty,
            leverage=settings.leverage,
            risk_amount=risk_amount,
            risk_percent=settings.risk_percent,
            notes=f"real_trade:auto:{action}",
            opened_at=datetime.now(timezone.utc),
        )
        self.db.add(trade)
        await self.db.flush()

        emoji = "🟢" if is_long else "🔴"
        await TelegramService().send_message(
            f"⚡ <b>Real Trade Executed</b>\n\n"
            f"Pair: <code>{symbol}</code>\n"
            f"Direction: {emoji} {action}\n"
            f"Entry: <code>${avg_price:,.4f}</code>\n"
            f"SL: <code>${opportunity['suggested_sl']:,.4f}</code>\n"
            f"TP: <code>${opportunity['suggested_tp']:,.4f}</code>\n"
            f"Qty: <code>{qty_str}</code> | Leverage: {settings.leverage}x\n"
            f"Order ID: <code>{order_id}</code>"
        )
        logger.info("real_trade_success", user_id=user_id, symbol=symbol, side=side, order_id=order_id)
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

            ai_limit = 2 if (settings and settings.scan_all_coins) else 1
            await asyncio.gather(*[_run_ai(opp) for opp in opportunities[:ai_limit]])

        if execute_paper and settings:
            for opportunity in opportunities[:5]:
                try:
                    trade = await self._open_paper_trade_if_needed(user_id, settings, opportunity)
                    if trade:
                        opportunity["paper_trade_id"] = trade.id
                except Exception as exc:
                    logger.warning("scanner_paper_trade_failed", symbol=opportunity["symbol"], error=str(exc))

        if (
            settings
            and settings.real_trade_enabled
            and settings.auto_trade
            and settings.polymarket_api_key
            and settings.polymarket_api_secret
            and opportunities
        ):
            for candidate in opportunities[:3]:
                if candidate.get("recommended_action") not in {"BUY", "STRONG_BUY", "SELL", "STRONG_SELL"}:
                    continue
                try:
                    real_result = await asyncio.wait_for(
                        self._execute_real_trade(user_id, settings, candidate),
                        timeout=30,
                    )
                    if real_result:
                        candidate["real_order_id"] = real_result.get("orderId")
                        break
                except asyncio.TimeoutError:
                    logger.warning("real_trade_timeout", user_id=user_id, symbol=candidate["symbol"])
                except Exception as exc:
                    logger.warning("real_trade_failed", symbol=candidate["symbol"], error=str(exc))

        if (
            settings
            and settings.defi_enabled
            and settings.defi_wallet_address
            and settings.defi_wallet_private_key_encrypted
            and opportunities
        ):
            from app.services.defi_service import DeFiService
            buy_opps = [c for c in opportunities if c.get("recommended_action") in {"BUY", "STRONG_BUY"}]
            sell_opps = [c for c in opportunities if c.get("recommended_action") in {"SELL", "STRONG_SELL"}]

            async def _try_defi(candidate: dict, network: str) -> None:
                _svc = DeFiService(network=network)
                token_addr = await _svc.get_token_address(candidate["symbol"])
                if not token_addr:
                    logger.info("defi_skip_no_address", symbol=candidate["symbol"], network=network)
                    return
                try:
                    defi_result = await asyncio.wait_for(
                        self._execute_defi_trade(user_id, settings, candidate, network=network),
                        timeout=180,
                    )
                    if defi_result:
                        candidate["defi_tx"] = defi_result.get("tx_hash")
                        candidate["defi_status"] = defi_result.get("status")
                except asyncio.TimeoutError:
                    logger.warning("defi_trade_timeout", user_id=user_id, symbol=candidate["symbol"], network=network)
                    from app.services.telegram_service import TelegramService
                    await TelegramService().send_message(
                        f"⚠️ <b>DeFi Trade Timeout</b>\n<code>{candidate['symbol']}</code> [{network}] — transaction took >180s, skipped."
                    )
                except Exception as exc:
                    logger.warning("scanner_defi_trade_failed", symbol=candidate["symbol"], network=network, error=str(exc))
                    from app.services.telegram_service import TelegramService
                    await TelegramService().send_message(
                        f"⚠️ <b>DeFi Trade Error</b>\n<code>{candidate['symbol']}</code> [{network}]\n<code>{exc}</code>"
                    )

            for network in settings.defi_networks:
                # Execute all SELL signals on this network (closes held positions)
                for candidate in sell_opps:
                    await _try_defi(candidate, network)

                # Execute at most one BUY per network (needs USDC on that network)
                _net_svc = DeFiService(network=network)
                buy_executed = False
                skipped_buy_symbols = []
                for candidate in buy_opps:
                    token_addr = await _net_svc.get_token_address(candidate["symbol"])
                    if token_addr:
                        await _try_defi(candidate, network)
                        buy_executed = True
                        break
                    else:
                        skipped_buy_symbols.append(candidate["symbol"])

                if not buy_executed and skipped_buy_symbols:
                    from app.services.telegram_service import TelegramService as _TG2

                    # Auto-fallback to Bybit for skipped DeFi symbols
                    bybit_fallback_done = False
                    if (
                        settings.real_trade_enabled
                        and settings.auto_trade
                        and settings.polymarket_api_key
                        and settings.polymarket_api_secret
                    ):
                        for sym in skipped_buy_symbols:
                            # Find the candidate and check if Bybit already traded it
                            skipped_candidate = next(
                                (c for c in buy_opps if c["symbol"] == sym), None
                            )
                            if skipped_candidate and not skipped_candidate.get("real_order_id"):
                                try:
                                    real_result = await asyncio.wait_for(
                                        self._execute_real_trade(user_id, settings, skipped_candidate),
                                        timeout=30,
                                    )
                                    if real_result:
                                        skipped_candidate["real_order_id"] = real_result.get("orderId")
                                        bybit_fallback_done = True
                                        logger.info(
                                            "defi_skip_bybit_fallback_success",
                                            symbol=sym, order_id=real_result.get("orderId"),
                                        )
                                        break
                                except Exception as exc:
                                    logger.warning("defi_skip_bybit_fallback_failed", symbol=sym, error=str(exc))

                    sym_list = ", ".join(f"<code>{s}</code>" for s in skipped_buy_symbols[:5])
                    if bybit_fallback_done:
                        await _TG2().send_message(
                            f"ℹ️ <b>DeFi BUY Skipped → Bybit Fallback</b> [{network}]\n"
                            f"Token: {sym_list}\n"
                            f"Tidak tersedia di DeFi {network} — trade dialihkan ke Bybit ✅"
                        )
                    else:
                        await _TG2().send_message(
                            f"⚠️ <b>DeFi BUY Skipped</b> [{network}]\n"
                            f"Signal BUY untuk: {sym_list}\n"
                            f"Token tidak tersedia di DeFi {network}.\n"
                            f"Bybit: {'tidak dikonfigurasi' if not settings.real_trade_enabled else 'sudah dicoba sebelumnya'}"
                        )

        if (
            settings
            and settings.gmx_enabled
            and settings.auto_trade
            and settings.defi_wallet_address
            and settings.defi_wallet_private_key_encrypted
            and opportunities
        ):
            for candidate in opportunities[:3]:
                action = candidate.get("recommended_action")
                if action not in {"BUY", "STRONG_BUY", "SELL", "STRONG_SELL"}:
                    continue
                try:
                    gmx_result = await asyncio.wait_for(
                        self._execute_gmx_trade(user_id, settings, candidate),
                        timeout=180,
                    )
                    if gmx_result and gmx_result.get("status") == "success":
                        candidate["gmx_tx"] = gmx_result.get("tx_hash")
                        candidate["gmx_direction"] = gmx_result.get("direction")
                except asyncio.TimeoutError:
                    logger.warning("gmx_trade_timeout", user_id=user_id, symbol=candidate["symbol"])
                    from app.services.telegram_service import TelegramService as _TGMX
                    await _TGMX().send_message(
                        f"⚠️ <b>GMX Trade Timeout</b> <code>{candidate['symbol']}</code>\nTransaction took >180s."
                    )
                except Exception as exc:
                    logger.warning("gmx_trade_failed", symbol=candidate["symbol"], error=str(exc))
                    from app.services.telegram_service import TelegramService as _TGMX
                    await _TGMX().send_message(
                        f"⚠️ <b>GMX Trade Error</b> <code>{candidate['symbol']}</code>\n<code>{exc}</code>"
                    )

        for opportunity in opportunities:
            opportunity.pop("market_data", None)

        return opportunities

    async def scan_specific_symbols(
        self,
        user_id: int,
        symbols: list[str],
        deep_analysis: bool = True,
        execute_defi: bool = True,
    ) -> list[dict]:
        """Scan specific symbols immediately and optionally execute DeFi trade."""
        settings = await self._get_settings(user_id)
        symbols = list(dict.fromkeys(s.upper() for s in symbols))

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

        fetch_results = await asyncio.gather(*[_fetch_symbol(s) for s in symbols])
        opportunities = [
            self._heuristic_signal(symbol, market_data)
            for symbol, market_data in fetch_results
            if market_data is not None
        ]

        if not opportunities:
            return []

        opportunities.sort(key=lambda item: abs(item["score"]), reverse=True)

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

            await asyncio.gather(*[_run_ai(opp) for opp in opportunities])

        if (
            execute_defi
            and settings
            and settings.defi_enabled
            and settings.defi_wallet_address
            and settings.defi_wallet_private_key_encrypted
            and opportunities
        ):
            from app.services.defi_service import DeFiService
            buy_candidates = [c for c in opportunities if c.get("recommended_action") in {"BUY", "STRONG_BUY"}]
            sell_candidates = [c for c in opportunities if c.get("recommended_action") in {"SELL", "STRONG_SELL"}]

            for network in settings.defi_networks:
                _net_svc = DeFiService(network=network)
                # Execute all SELL signals first, then one BUY per network
                for candidate in sell_candidates + buy_candidates[:1]:
                    token_addr = await _net_svc.get_token_address(candidate["symbol"])
                    if not token_addr:
                        continue
                    try:
                        defi_result = await asyncio.wait_for(
                            self._execute_defi_trade(user_id, settings, candidate, network=network),
                            timeout=180,
                        )
                        if defi_result:
                            candidate["defi_tx"] = defi_result.get("tx_hash")
                            candidate["defi_status"] = defi_result.get("status")
                    except asyncio.TimeoutError:
                        logger.warning("defi_trade_timeout", user_id=user_id, symbol=candidate["symbol"], network=network)
                    except Exception as exc:
                        logger.warning("scanner_defi_trade_failed", symbol=candidate["symbol"], network=network, error=str(exc))

        if (
            settings
            and settings.real_trade_enabled
            and settings.auto_trade
            and settings.polymarket_api_key
            and settings.polymarket_api_secret
            and opportunities
        ):
            for candidate in opportunities:
                if candidate.get("recommended_action") not in {"BUY", "STRONG_BUY", "SELL", "STRONG_SELL"}:
                    continue
                try:
                    real_result = await asyncio.wait_for(
                        self._execute_real_trade(user_id, settings, candidate),
                        timeout=30,
                    )
                    if real_result:
                        candidate["real_order_id"] = real_result.get("orderId")
                        break
                except asyncio.TimeoutError:
                    logger.warning("real_trade_timeout", user_id=user_id, symbol=candidate["symbol"])
                except Exception as exc:
                    logger.warning("real_trade_failed", symbol=candidate["symbol"], error=str(exc))

        for opportunity in opportunities:
            opportunity.pop("market_data", None)

        return opportunities
