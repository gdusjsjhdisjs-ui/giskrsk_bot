"""Application settings via Pydantic BaseSettings (v2)."""

from __future__ import annotations

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=False,
    )

    # --- Telegram ---
    BOT_TOKEN: str
    APP_BASE_URL: str = "http://localhost:8000"

    # --- PostgreSQL ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "webgis_bot"
    POSTGRES_USER: str = "webgis"
    POSTGRES_PASSWORD: str

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- NextGIS Web ---
    NEXTGIS_BASE_URL: str = "https://zimin-maplive0000.nextgis.com"
    NEXTGIS_LOGIN: str = "admin"
    NEXTGIS_PASSWORD: str = "changeme"
    NEXTGIS_BEARER_TOKEN: str
    NEXTGIS_PARCELS_RESOURCE_ID: int
    NEXTGIS_PZZ_RESOURCE_ID: int

    # --- YooKassa ---
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    YOOKASSA_RETURN_URL: str = "https://t.me/giskrsk_bot"

    # Фоновые задачи (планировщик, напоминания, автобэкап) в основном процессе.
    # Поставьте false, только если запускаете отдельный worker: python -m app.worker_entry
    RUN_BACKGROUND_TASKS: bool = True

    # --- Admin / limits ---
    ADMIN_IDS: list[int] = Field(default_factory=list)

    DAILY_LIMIT_FREE: int = 3
    DAILY_LIMIT_BASIC: int = 30
    DAILY_LIMIT_PRO: int = 100

    # --- Tariff prices ---
    TARIFF_BASIC_30D_PRICE: int = 2990
    TARIFF_PRO_30D_PRICE: int = 4990
    TARIFF_PRO_90D_PRICE: int = 9900
    TARIFF_YEAR_PRICE: int = 24900

    # --- DeepSeek AI ---
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # --- Workers ---
    MONITOR_CHECK_INTERVAL_MINUTES: int = 60

    # --- PDF ---
    PDF_OUTPUT_DIR: str = "/tmp/webgis_pdfs"

    # --- Магазин георесурсов ---
    SHOP_CARD_NUMBER: str = "0000 0000 0000 0000"  # номер карты для переводов
    SHOP_FILES_DIR: str = "shop_files"

    # --- Mini App ---
    WEBAPP_URL: str = ""

    # --- Клиппинг по области ---
    CLIP_PRICE_PER_KM2: int = 200       # ₽ за км²
    CLIP_MIN_PRICE: int = 990           # минимальная цена клипа
    CLIP_MIN_MULTIPLIER: float = 2.0    # клип >= цена_магаз * коэфф

    # --- Поддержка ---
    SUPPORT_USERNAME: str = ""          # ник в Telegram без @

    # --- Dev mode ---
    USE_SQLITE: bool = False

    # --- Logging ---
    LOG_LEVEL: str = "INFO"


settings = Settings()
