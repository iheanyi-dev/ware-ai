from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central place for all configuration. Values are loaded from environment
    variables (or a local .env file). Nothing else in the app should read
    os.environ directly — import get_settings() instead, so config stays
    typed, validated, and traceable to one source.
    """

    # Tells pydantic-settings to also read from a .env file if present,
    # and to silently ignore any extra env vars it doesn't recognize
    # (so a stray var in your .env doesn't crash the app on startup).
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "eduplatform-ai-service"
    environment: str = "development"
    port: int = 8000

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    DATABASE_URL: str

    # --- Database (used starting Phase 1) ---
    #database_url: str = "postgresql+psycopg://{eduplatform}:change-this-password@localhost:5432/eduplatform"

    # --- Anthropic API (used starting Phase 5) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # --- Internal service-to-service auth (used starting Phase 4) ---
    internal_api_key: str = ""

    @property
    def database_url(self):
        return self.DATABASE_URL



@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance so we only parse environment
    variables once per process, not on every single function call.

    Usage anywhere in the app:
        from app.core.config import get_settings
        settings = get_settings()
    """
    return Settings()