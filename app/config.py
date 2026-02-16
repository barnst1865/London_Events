"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Application
    app_name: str = "London Events Report"
    app_env: str = "development"
    debug: bool = True

    # Database
    database_url: str

    # API Keys - Event Sources
    ticketmaster_api_key: Optional[str] = None
    eventbrite_api_key: Optional[str] = None
    seatgeek_client_id: Optional[str] = None
    songkick_api_key: Optional[str] = None

    # AI Curation
    anthropic_api_key: Optional[str] = None

    # Scheduling
    report_generation_day_of_week: str = "mon"  # Day of week for weekly generation
    report_generation_hour: int = 9
    report_generation_timezone: str = "Europe/London"

    # Sellout Detection
    sellout_threshold_percentage: int = 10
    low_availability_threshold: int = 50

    # Sellout Alert System
    sellout_alert_min_selling_fast: int = 1
    sellout_alert_min_sold_out: int = 3
    sellout_monitor_enabled: bool = True

    # Web Scraping
    scraping_user_agent: str = "Mozilla/5.0 (compatible; LondonEventsBot/1.0)"
    scraping_delay: int = 2
    scraping_timeout: int = 30

    # Output
    output_dir: str = "output"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"


settings = Settings()
