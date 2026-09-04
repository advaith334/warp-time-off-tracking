"""Application configuration, loaded and validated from the environment."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str = "postgresql+psycopg://warp:warp@localhost:5433/timeoff"

    # Where the browser app is served from. Hardcoding this made the API
    # undeployable anywhere but a laptop.
    cors_origins: list[str] = ["http://localhost:5173"]

    log_level: str = "INFO"

    # The single demo company. Everything is keyed by company_id for
    # multi-tenancy; the MVP just never creates a second one.
    demo_company_id: str = "cmp_warp_demo"


settings = Settings()

# Module-level aliases, so the ~15 existing import sites keep working and this
# change stays a configuration change rather than a rename touching everything.
DATABASE_URL = settings.database_url
DEMO_COMPANY_ID = settings.demo_company_id
