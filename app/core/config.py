from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Payment Microservice"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payments_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    PAYMENT_EXCHANGE: str = "payments.exchange"
    PAYMENT_QUEUE: str = "payments.queue"
    DEAD_LETTER_QUEUE: str = "payments.dlq"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Idempotency
    IDEMPOTENCY_TTL_SECONDS: int = 86400  # 24 hours

    # Retry policy
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_SECONDS: float = 2.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()