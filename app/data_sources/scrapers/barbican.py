"""Barbican Centre web scraper."""
import re
from typing import List
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class BarbicanScraper(BaseScraper):
    """
    Scraper for Barbican Centre events.
    Website: https://www.barbican.org.uk/whats-on
    """

    BASE_URL = "https://www.barbican.org.uk"
    EVENTS_URL = f"{BASE_URL}/whats-on"

    @property
    def name(self) -> str:
        return "barbican"

    @property
    def display_name(self) -> str:
        return "Barbican Centre"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Barbican Centre."""
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
            logger.error(f"Barbican scraping error: {e}")
            raise

        # Filter by date range
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"Barbican: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        # Barbican has art form-based listings
        urls = [
            f"{self.EVENTS_URL}",
            f"{self.EVENTS_URL}/music",
            f"{self.EVENTS_URL}/theatre",
            f"{self.EVENTS_URL}/dance",
            f"{self.EVENTS_URL}/film",
            f"{self.EVENTS_URL}/art",
            f"{self.EVENTS_URL}/family",
        ]
        return urls

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        # Barbican uses event cards and listing items
        event_containers = soup.find_all(
            ["div", "article", "li", "a"],
            class_=re.compile(r"event|card|listing|performance|show|tile", re.IGNORECASE)
        )

        # Also look for event links
        if not event_containers:
            event_containers = soup.find_all("a", href=re.compile(r"/whats-on/\d+/"))

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
            # Extract title
            title_elem = card.find(["h1", "h2", "h3", "h4", "h5"], class_=re.compile(r"title|name|heading", re.IGNORECASE))
            if not title_elem:
                title_elem = card.find(["h1", "h2", "h3", "h4", "h5"])
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Extract URL
            link_elem = card.find("a", href=True)
            if not link_elem:
                if card.name == "a" and card.get("href"):
                    link_elem = card
                else:
                    return None

            event_url = link_elem["href"]
            if not event_url.startswith("http"):
                event_url = self.BASE_URL + event_url

            # Skip non-event URLs
            if "/whats-on/" not in event_url:
                return None

            # Generate unique ID from URL
            source_id = event_url.split("/")[-1] or event_url.split("/")[-2]
            source_id = re.sub(r"[?#].*", "", source_id)

            # Extract image
            img_elem = card.find("img")
            image_url = None
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src") or img_elem.get("data-lazy-src")
                if image_url and not image_url.startswith("http"):
                    if image_url.startswith("//"):
                        image_url = "https:" + image_url
                    else:
                        image_url = self.BASE_URL + image_url

            # Extract description
            desc_elem = card.find(["p", "div"], class_=re.compile(r"description|excerpt|summary|content|teaser", re.IGNORECASE))
            description = desc_elem.get_text(strip=True) if desc_elem else None

            # Extract date
            date_elem = card.find(["time", "span", "div"], class_=re.compile(r"date|time|when", re.IGNORECASE))
            start_date = self._parse_date(date_elem.get_text(strip=True) if date_elem else None)

            # Check for datetime attribute
            if date_elem and date_elem.name == "time" and date_elem.get("datetime"):
                try:
                    start_date = datetime.fromisoformat(date_elem["datetime"].replace("Z", "+00:00"))
                except:
                    pass

            # Extract price info
            price_elem = card.find(["span", "div"], class_=re.compile(r"price|cost|ticket|from", re.IGNORECASE))
            price_min, price_max = self._parse_price(price_elem.get_text(strip=True) if price_elem else None)

            # Extract venue (Barbican has multiple venues)
            venue_elem = card.find(["span", "div"], class_=re.compile(r"venue|location|hall", re.IGNORECASE))
            venue_name = venue_elem.get_text(strip=True) if venue_elem else "Barbican Centre"
            # Ensure it includes "Barbican" in the name
            if "barbican" not in venue_name.lower():
                venue_name = f"{venue_name}, Barbican Centre" if venue_name != "Barbican Centre" else venue_name

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
                venue_name=venue_name,
                venue_address="Silk Street, London EC2Y 8DS",
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
        elif "/theatre" in page_url.lower():
            return "theatre"
        elif "/dance" in page_url.lower():
            return "dance"
        elif "/film" in page_url.lower():
            return "film"
        elif "/art" in page_url.lower():
            return "arts"
        elif "/family" in page_url.lower():
            return "family"

        # Check title/description for keywords
        combined = (title + " " + description).lower()
        if any(word in combined for word in ["concert", "music", "orchestra", "classical"]):
            return "music"
        elif any(word in combined for word in ["theatre", "play", "drama"]):
            return "theatre"
        elif any(word in combined for word in ["dance", "ballet"]):
            return "dance"
        elif any(word in combined for word in ["film", "cinema", "screening"]):
            return "film"
        elif any(word in combined for word in ["exhibition", "gallery", "art"]):
            return "arts"
        elif any(word in combined for word in ["family", "kids", "children"]):
            return "family"

        return "arts"

    def get_rate_limit_delay(self) -> float:
        """Be respectful with scraping - 3 seconds between requests."""
        return 3.0
