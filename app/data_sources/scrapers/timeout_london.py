"""Time Out London web scraper."""
import re
from typing import List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class TimeOutLondonScraper(BaseScraper):
    """
    Scraper for Time Out London events.
    Website: https://www.timeout.com/london/things-to-do

    LIMITATION: Time Out London's listing pages are editorial content
    (listicles like "The 15 best gigs in London this February"), not
    structured event listings. Individual event data (dates, venues,
    prices) is not available on these pages.

    This scraper is currently disabled until a workable approach is
    found (e.g., scraping individual article pages for event links,
    or finding a Time Out API/feed).
    """

    BASE_URL = "https://www.timeout.com"
    EVENTS_URL = f"{BASE_URL}/london/things-to-do"

    @property
    def name(self) -> str:
        return "timeout_london"

    @property
    def display_name(self) -> str:
        return "Time Out London"

    def is_enabled(self) -> bool:
        """
        Disabled: Time Out listing pages are editorial content, not
        structured event data. Returns empty results rather than
        inserting events with fabricated dates.
        """
        return False

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Time Out London."""
        logger.info(
            "Time Out London scraper is disabled: listing pages contain "
            "editorial articles, not structured event data. No events "
            "will be returned."
        )
        return []

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        return []

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        return []

    def get_rate_limit_delay(self) -> float:
        """Be respectful with scraping - 3 seconds between requests."""
        return 3.0

    def transform_category(self, source_category: str) -> str:
        """Map Time Out categories to standardized ones."""
        category_map = {
            "things to do": "events",
            "music": "music",
            "theatre": "theatre",
            "comedy": "comedy",
            "food and drink": "food",
            "film": "film",
            "art": "arts",
            "clubs": "nightlife",
        }
        return category_map.get(source_category.lower(), source_category.lower())
