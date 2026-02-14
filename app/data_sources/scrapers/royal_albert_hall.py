"""Royal Albert Hall web scraper."""
import re
from typing import List, Optional, Tuple
from datetime import datetime
import logging
from bs4 import BeautifulSoup, Tag
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class RoyalAlbertHallScraper(BaseScraper):
    """
    Scraper for Royal Albert Hall events.
    Website: https://www.royalalberthall.com/tickets/events

    LIMITATION: The Royal Albert Hall website uses Cloudflare bot
    protection that blocks requests from httpx/requests. All pages
    return "Pardon Our Interruption" instead of content.

    This scraper is currently disabled until a solution is found
    (e.g., headless browser, or an API endpoint).
    """

    BASE_URL = "https://www.royalalberthall.com"
    EVENTS_URL = f"{BASE_URL}/tickets/events"

    @property
    def name(self) -> str:
        return "royal_albert_hall"

    @property
    def display_name(self) -> str:
        return "Royal Albert Hall"

    def is_enabled(self) -> bool:
        """
        Disabled: Royal Albert Hall uses Cloudflare bot protection
        that blocks httpx requests. Returns empty results rather
        than failing silently.
        """
        return False

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Royal Albert Hall."""
        logger.info(
            "Royal Albert Hall scraper is disabled: website uses "
            "Cloudflare bot protection that blocks automated requests. "
            "No events will be returned."
        )
        return []

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        return []

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        return []

    def _determine_category(self, page_url: str, title: str, description: str) -> str:
        """Determine event category."""
        combined = (title + " " + description).lower()
        if any(word in combined for word in ["classical", "orchestra", "symphony", "concerto"]):
            return "classical"
        elif any(word in combined for word in ["jazz", "blues"]):
            return "jazz"
        elif any(word in combined for word in ["ballet", "dance"]):
            return "dance"
        elif any(word in combined for word in ["film", "cinema", "movie"]):
            return "film"
        elif any(word in combined for word in ["comedy", "comedian"]):
            return "comedy"
        elif any(word in combined for word in ["rock", "pop", "concert", "tour"]):
            return "music"
        return "arts"

    def get_rate_limit_delay(self) -> float:
        """Be respectful with scraping - 3 seconds between requests."""
        return 3.0
