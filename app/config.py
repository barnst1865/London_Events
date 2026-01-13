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
    secret_key: str

    # Database
    database_url: str

    # API Keys - Event Sources
    ticketmaster_api_key: Optional[str] = None
    eventbrite_api_key: Optional[str] = None
    seatgeek_client_id: Optional[str] = None
    songkick_api_key: Optional[str] = None

    # Email Service
    sendgrid_api_key: Optional[str] = None
    from_email: str = "newsletter@londonevents.com"
    from_name: str = "London Events Report"

    # Stripe
    stripe_api_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    # Subscription Pricing
    free_events_limit: int = 5
    monthly_price_id: Optional[str] = None
    annual_price_id: Optional[str] = None

    # Scheduling
    report_generation_day: int = 1
    report_generation_hour: int = 9
    report_generation_timezone: str = "Europe/London"

    # Sellout Detection
    sellout_threshold_percentage: int = 10
    low_availability_threshold: int = 50

    # Web Scraping
    scraping_user_agent: str = "Mozilla/5.0 (compatible; LondonEventsBot/1.0)"
    scraping_delay: int = 2
    scraping_timeout: int = 30

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"


settings = Settings()
