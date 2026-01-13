"""Time Out London web scraper."""
import re
from typing import List
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
    """

    BASE_URL = "https://www.timeout.com"
    EVENTS_URL = f"{BASE_URL}/london/things-to-do"

    @property
    def name(self) -> str:
        return "timeout_london"

    @property
    def display_name(self) -> str:
        return "Time Out London"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Time Out London."""
        events = []

        try:
            # Get listing page URLs
            listing_urls = self._get_listing_urls(start_date, end_date)

            for url in listing_urls:
                logger.info(f"Scraping {url}")
                response = self._make_request(url)
                if not response:
                    continue

                soup = self._parse_html(response.text)
                if not soup:
                    continue

                # Parse events from listing page
                page_events = self._parse_listing_page(soup, url)
                events.extend(page_events)

        except Exception as e:
            logger.error(f"Time Out London scraping error: {e}")
            raise

        # Filter by date range
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"Time Out London: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        # Time Out has various category pages
        categories = [
            "things-to-do",
            "music",
            "theatre",
            "comedy",
            "food-and-drink",
            "film",
            "art",
            "clubs",
        ]

        urls = []
        for category in categories:
            urls.append(f"{self.BASE_URL}/london/{category}")

        return urls

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        # Time Out uses various article/card structures
        # Look for event cards/articles
        event_cards = soup.find_all(["article", "div"], class_=re.compile(r"card|event|listing"))

        for card in event_cards:
            try:
                event = self._parse_event_card(card, page_url)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Error parsing event card: {e}")
                continue

        return events

    def _parse_event_card(self, card, page_url: str) -> EventData:
        """Parse individual event card."""
        try:
            # Extract title
            title_elem = card.find(["h2", "h3", "h4"], class_=re.compile(r"title|name|heading"))
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Extract URL
            link_elem = card.find("a", href=True)
            if not link_elem:
                return None
            event_url = link_elem["href"]
            if not event_url.startswith("http"):
                event_url = self.BASE_URL + event_url

            # Generate unique ID from URL
            source_id = event_url.split("/")[-1] or event_url.split("/")[-2]

            # Extract image
            img_elem = card.find("img")
            image_url = None
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")

            # Extract description
            desc_elem = card.find(["p", "div"], class_=re.compile(r"description|excerpt|summary"))
            description = desc_elem.get_text(strip=True) if desc_elem else None

            # Extract venue (if available)
            venue_elem = card.find(["span", "div"], class_=re.compile(r"venue|location"))
            venue_name = venue_elem.get_text(strip=True) if venue_elem else None

            # Extract date (Time Out doesn't always show specific dates on listings)
            # Default to current date - will need detail page scraping for accurate dates
            start_date = datetime.now()

            # Extract price info
            price_elem = card.find(["span", "div"], class_=re.compile(r"price"))
            price_min = None
            price_max = None
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                if "free" in price_text.lower():
                    price_min = 0.0
                    price_max = 0.0
                else:
                    # Try to extract numbers
                    prices = re.findall(r"£(\d+(?:\.\d+)?)", price_text)
                    if prices:
                        prices = [float(p) for p in prices]
                        price_min = min(prices)
                        price_max = max(prices)

            # Determine category from page URL
            categories = []
            category_match = re.search(r"/london/([^/]+)", page_url)
            if category_match:
                category = category_match.group(1).replace("-", " ")
                categories.append(self.transform_category(category))

            return EventData(
                title=title,
                description=description,
                start_date=start_date,
                source_name=self.name,
                source_id=source_id,
                source_url=event_url,
                venue_name=venue_name,
                ticket_url=event_url,
                price_min=price_min,
                price_max=price_max,
                image_url=image_url,
                categories=categories,
            )

        except Exception as e:
            logger.debug(f"Error parsing event card: {e}")
            return None

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
