import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

_RETRYABLE_STATUSES = {429, 503}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUSES
    return False


def http_retry(logger):
    """3 retries with exponential backoff 1s/2s/4s on 429, 503, or timeout."""
    def _log_before_sleep(retry_state):
        exc = retry_state.outcome.exception()
        logger.warning(
            "http_retry_attempt",
            attempt=retry_state.attempt_number,
            error=str(exc),
        )

    return retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception(_is_retryable),
        before_sleep=_log_before_sleep,
        reraise=True,
    )
