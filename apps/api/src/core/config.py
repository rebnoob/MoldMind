from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://moldmind:moldmind_dev@localhost:5432/moldmind"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object Storage
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "moldmind"
    s3_secret_key: str = "moldmind_dev"
    s3_bucket: str = "moldmind-files"
    s3_region: str = "us-east-1"

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # App
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
