from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TradingBotException(Exception):
    def __init__(self, message: str, status_code: int = 400, detail: dict = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(message)


class InsufficientBalanceError(TradingBotException):
    def __init__(self, required: float, available: float):
        super().__init__(
            f"Insufficient balance. Required: {required}, Available: {available}",
            status_code=422,
            detail={"required": required, "available": available},
        )


class RiskLimitExceededError(TradingBotException):
    def __init__(self, risk_percent: float, max_risk: float):
        super().__init__(
            f"Risk {risk_percent}% exceeds max allowed {max_risk}%",
            status_code=422,
            detail={"risk_percent": risk_percent, "max_risk": max_risk},
        )


class MaxTradesExceededError(TradingBotException):
    def __init__(self, current: int, maximum: int):
        super().__init__(
            f"Max open trades reached: {current}/{maximum}",
            status_code=429,
            detail={"current": current, "maximum": maximum},
        )


class ExchangeConnectionError(TradingBotException):
    def __init__(self, detail: str = "Exchange API connection failed"):
        super().__init__(detail, status_code=503)


async def trading_bot_exception_handler(request: Request, exc: TradingBotException):
    logger.error("trading_bot_error", message=exc.message, detail=exc.detail, path=str(request.url))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation_error", errors=exc.errors(), path=str(request.url))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation failed", "detail": exc.errors()},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"},
    )
