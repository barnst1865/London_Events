"""Southbank Centre web scraper."""
import re
from typing import List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class SouthbankCentreScraper(BaseScraper):
    """
    Scraper for Southbank Centre events.
    Website: https://www.southbankcentre.co.uk/whats-on

    Southbank Centre includes multiple venues:
    - Royal Festival Hall
    - Queen Elizabeth Hall
    - Purcell Room
    - Hayward Gallery

    LIMITATION: The Southbank Centre website uses Cloudflare bot
    protection that returns 403 Forbidden for automated requests.

    This scraper is currently disabled until a solution is found
    (e.g., headless browser, or an API endpoint).
    """

    BASE_URL = "https://www.southbankcentre.co.uk"
    EVENTS_URL = f"{BASE_URL}/whats-on"

    @property
    def name(self) -> str:
        return "southbank_centre"

    @property
    def display_name(self) -> str:
        return "Southbank Centre"

    def is_enabled(self) -> bool:
        """
        Disabled: Southbank Centre uses Cloudflare bot protection
        that returns 403 for httpx requests. Returns empty results
        rather than failing silently.
        """
        return False

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Southbank Centre."""
        logger.info(
            "Southbank Centre scraper is disabled: website uses "
            "Cloudflare bot protection (403 Forbidden). "
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
        if any(word in combined for word in ["concert", "music", "orchestra", "classical", "jazz"]):
            return "music"
        elif any(word in combined for word in ["dance", "ballet", "choreography"]):
            return "dance"
        elif any(word in combined for word in ["exhibition", "gallery", "art", "artist"]):
            return "arts"
        elif any(word in combined for word in ["literature", "poetry", "author", "book"]):
            return "literature"
        elif any(word in combined for word in ["talk", "discussion", "lecture", "conversation"]):
            return "talks"
        elif any(word in combined for word in ["family", "kids", "children"]):
            return "family"
        return "arts"

    def get_rate_limit_delay(self) -> float:
        """Be respectful with scraping - 3 seconds between requests."""
        return 3.0
