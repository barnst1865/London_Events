"""The O2 Arena web scraper."""
import re
from typing import List
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class O2ArenaScraper(BaseScraper):
    """
    Scraper for The O2 Arena events.
    Website: https://www.theo2.co.uk/events
    """

    BASE_URL = "https://www.theo2.co.uk"
    EVENTS_URL = f"{BASE_URL}/events"

    @property
    def name(self) -> str:
        return "o2_arena"

    @property
    def display_name(self) -> str:
        return "The O2 Arena"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from The O2 Arena."""
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
            logger.error(f"O2 Arena scraping error: {e}")
            raise

        # Filter by date range
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"O2 Arena: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        # O2 typically has an events listing page and category pages
        urls = [
            f"{self.EVENTS_URL}",
            f"{self.EVENTS_URL}/music",
            f"{self.EVENTS_URL}/comedy",
            f"{self.EVENTS_URL}/sport",
            f"{self.EVENTS_URL}/family",
        ]
        return urls

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        # O2 uses event cards with various structures
        # Look for common event container patterns
        event_containers = soup.find_all(
            ["div", "article", "li"],
            class_=re.compile(r"event|card|listing|item", re.IGNORECASE)
        )

        # Also try finding event links directly
        if not event_containers:
            event_containers = soup.find_all("a", href=re.compile(r"/events?/"))

        for container in event_containers:
            try:
                event = self._parse_event_card(container, page_url)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Error parsing event card: {e}")
                continue

        return events

    def _parse_event_card(self, card, page_url: str) -> EventData:
        """Parse individual event card."""
        try:
            # Extract title - try multiple selectors
            title_elem = card.find(["h1", "h2", "h3", "h4", "h5"], class_=re.compile(r"title|name|heading|event", re.IGNORECASE))
            if not title_elem:
                # Try finding any heading
                title_elem = card.find(["h1", "h2", "h3", "h4", "h5"])
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Extract URL
            link_elem = card.find("a", href=True)
            if not link_elem:
                # If card itself is an anchor
                if card.name == "a" and card.get("href"):
                    link_elem = card
                else:
                    return None

            event_url = link_elem["href"]
            if not event_url.startswith("http"):
                event_url = self.BASE_URL + event_url

            # Skip non-event URLs
            if "/events" not in event_url:
                return None

            # Generate unique ID from URL
            source_id = event_url.split("/")[-1] or event_url.split("/")[-2]
            source_id = re.sub(r"[?#].*", "", source_id)  # Remove query params

            # Extract image
            img_elem = card.find("img")
            image_url = None
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src") or img_elem.get("data-lazy-src")
                if image_url and not image_url.startswith("http"):
                    image_url = self.BASE_URL + image_url

            # Extract description
            desc_elem = card.find(["p", "div"], class_=re.compile(r"description|excerpt|summary|content", re.IGNORECASE))
            description = desc_elem.get_text(strip=True) if desc_elem else None

            # Extract date
            date_elem = card.find(["time", "span", "div"], class_=re.compile(r"date|time|when", re.IGNORECASE))
            start_date = self._parse_date(date_elem.get_text(strip=True) if date_elem else None)

            # Extract price info
            price_elem = card.find(["span", "div"], class_=re.compile(r"price|cost|ticket", re.IGNORECASE))
            price_min, price_max = self._parse_price(price_elem.get_text(strip=True) if price_elem else None)

            # Determine category
            categories = []
            category = self._determine_category(page_url, title, description or "")
            if category:
                categories.append(category)

            return EventData(
                title=title,
                description=description,
                start_date=start_date,
                source_name=self.name,
                source_id=source_id,
                source_url=event_url,
                venue_name="The O2 Arena",
                venue_address="Peninsula Square, London SE10 0DX",
                ticket_url=event_url,
                price_min=price_min,
                price_max=price_max,
                image_url=image_url,
                categories=categories,
            )

        except Exception as e:
            logger.debug(f"Error parsing event card: {e}")
            return None

    def _parse_date(self, date_text: str) -> datetime:
        """Parse date from text."""
        if not date_text:
            return datetime.now()

        try:
            # Try common date formats
            date_patterns = [
                r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})",
                r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
                r"(\d{4})-(\d{2})-(\d{2})",
            ]

            for pattern in date_patterns:
                match = re.search(pattern, date_text, re.IGNORECASE)
                if match:
                    # Try to parse the matched date
                    try:
                        from dateutil import parser
                        return parser.parse(match.group(0))
                    except:
                        pass

            # Fallback: try parsing the whole text
            from dateutil import parser
            return parser.parse(date_text, fuzzy=True)
        except:
            return datetime.now()

    def _parse_price(self, price_text: str) -> tuple:
        """Parse price from text. Returns (min_price, max_price)."""
        if not price_text:
            return None, None

        try:
            price_text = price_text.lower()
            if "free" in price_text:
                return 0.0, 0.0

            # Extract all numbers that look like prices
            prices = re.findall(r"£?(\d+(?:\.\d{2})?)", price_text)
            if prices:
                prices = [float(p) for p in prices]
                return min(prices), max(prices)
        except:
            pass

        return None, None

    def _determine_category(self, page_url: str, title: str, description: str) -> str:
        """Determine event category."""
        # Check URL first
        if "/music" in page_url.lower():
            return "music"
        elif "/comedy" in page_url.lower():
            return "comedy"
        elif "/sport" in page_url.lower():
            return "sports"
        elif "/family" in page_url.lower():
            return "family"

        # Check title/description for keywords
        combined = (title + " " + description).lower()
        if any(word in combined for word in ["concert", "tour", "music", "band", "singer"]):
            return "music"
        elif any(word in combined for word in ["comedy", "comedian", "stand-up"]):
            return "comedy"
        elif any(word in combined for word in ["sport", "football", "basketball", "tennis"]):
            return "sports"
        elif any(word in combined for word in ["family", "kids", "children"]):
            return "family"

        return "entertainment"

    def get_rate_limit_delay(self) -> float:
        """Be respectful with scraping - 3 seconds between requests."""
        return 3.0
