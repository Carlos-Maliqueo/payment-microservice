from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()


class PaymentException(Exception):
    def __init__(self, message: str, status_code: int = 400, error_code: str = "PAYMENT_ERROR"):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class PaymentNotFoundException(PaymentException):
    def __init__(self, payment_id: str):
        super().__init__(
            message=f"Payment {payment_id} not found",
            status_code=404,
            error_code="PAYMENT_NOT_FOUND",
        )


class DuplicateIdempotencyKeyException(PaymentException):
    def __init__(self, key: str):
        super().__init__(
            message=f"Idempotency key '{key}' already used",
            status_code=409,
            error_code="DUPLICATE_IDEMPOTENCY_KEY",
        )


class InvalidPaymentStateException(PaymentException):
    def __init__(self, payment_id: str, current_state: str, expected_state: str):
        super().__init__(
            message=f"Payment {payment_id} is in state '{current_state}', expected '{expected_state}'",
            status_code=422,
            error_code="INVALID_PAYMENT_STATE",
        )


class InsufficientFundsException(PaymentException):
    def __init__(self):
        super().__init__(
            message="Insufficient funds for this transaction",
            status_code=402,
            error_code="INSUFFICIENT_FUNDS",
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PaymentException)
    async def payment_exception_handler(request: Request, exc: PaymentException):
        logger.error(
            "payment_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            },
        )