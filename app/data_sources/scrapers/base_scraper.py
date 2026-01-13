"""Base class for web scraping data sources."""
import time
import logging
from abc import abstractmethod
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from ..base import BaseDataSource
from ...config import settings

logger = logging.getLogger(__name__)


class BaseScraper(BaseDataSource):
    """
    Base class for web scraping data sources.

    Provides common functionality for HTTP requests, rate limiting,
    and HTML parsing. All scrapers should inherit from this class.
    """

    @property
    def source_type(self) -> str:
        """All scrapers return 'scraper' type."""
        return "scraper"

    def _make_request(self, url: str, **kwargs) -> Optional[httpx.Response]:
        """
        Make HTTP request with proper headers and error handling.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments for httpx.get()

        Returns:
            Response object or None if failed
        """
        headers = {
            "User-Agent": settings.scraping_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        # Merge with any custom headers
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        try:
            # Rate limiting
            time.sleep(self.get_rate_limit_delay())

            response = httpx.get(
                url,
                headers=headers,
                timeout=settings.scraping_timeout,
                follow_redirects=True,
                **kwargs
            )
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    def _parse_html(self, html: str) -> Optional[BeautifulSoup]:
        """
        Parse HTML content into BeautifulSoup object.

        Args:
            html: HTML content string

        Returns:
            BeautifulSoup object or None if parsing failed
        """
        try:
            return BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return None

    def get_rate_limit_delay(self) -> float:
        """
        Get delay between requests.
        Scrapers should be more conservative than APIs.
        """
        return float(settings.scraping_delay)

    @abstractmethod
    def _get_listing_urls(self, start_date, end_date) -> list:
        """
        Get URLs of event listing pages to scrape.

        Args:
            start_date: Start date for events
            end_date: End date for events

        Returns:
            List of URLs to scrape
        """
        pass

    @abstractmethod
    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """
        Parse an event listing page and extract event URLs or data.

        Args:
            soup: BeautifulSoup object of the page
            page_url: URL of the page being parsed

        Returns:
            List of event URLs or event data
        """
        pass
