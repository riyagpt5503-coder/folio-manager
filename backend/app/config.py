from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    risk_free_rate: float = 0.065  # approx. short-term Indian G-Sec / T-bill yield
    cache_ttl_minutes: int = 60
    lookback_years: int = 5
    max_weight: float = 0.40
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
