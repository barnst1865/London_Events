"""Southbank Centre web scraper."""
import re
from typing import List
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
    """

    BASE_URL = "https://www.southbankcentre.co.uk"
    EVENTS_URL = f"{BASE_URL}/whats-on"

    @property
    def name(self) -> str:
        return "southbank_centre"

    @property
    def display_name(self) -> str:
        return "Southbank Centre"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Southbank Centre."""
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
            logger.error(f"Southbank Centre scraping error: {e}")
            raise

        # Filter by date range
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"Southbank Centre: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        # Southbank Centre has category and venue-based listings
        urls = [
            f"{self.EVENTS_URL}",
            f"{self.EVENTS_URL}/music",
            f"{self.EVENTS_URL}/classical",
            f"{self.EVENTS_URL}/contemporary",
            f"{self.EVENTS_URL}/dance",
            f"{self.EVENTS_URL}/art",
            f"{self.EVENTS_URL}/literature",
            f"{self.EVENTS_URL}/talks",
            f"{self.EVENTS_URL}/family",
        ]
        return urls

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        # Southbank Centre uses event cards and grid layouts
        event_containers = soup.find_all(
            ["div", "article", "li", "a"],
            class_=re.compile(r"event|card|listing|performance|show|item|tile", re.IGNORECASE)
        )

        # Also look for event links
        if not event_containers:
            event_containers = soup.find_all("a", href=re.compile(r"/(whats-on|events?)/"))

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
            if not any(path in event_url for path in ["/whats-on/", "/events/"]):
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
            desc_elem = card.find(["p", "div"], class_=re.compile(r"description|excerpt|summary|content|teaser|intro", re.IGNORECASE))
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

            # Extract specific venue within Southbank Centre
            venue_elem = card.find(["span", "div"], class_=re.compile(r"venue|location|hall|space", re.IGNORECASE))
            venue_name = venue_elem.get_text(strip=True) if venue_elem else "Southbank Centre"

            # Map to specific venues if found
            venue_name_lower = venue_name.lower()
            if "royal festival hall" in venue_name_lower or "rfh" in venue_name_lower:
                venue_name = "Royal Festival Hall, Southbank Centre"
            elif "queen elizabeth hall" in venue_name_lower or "qeh" in venue_name_lower:
                venue_name = "Queen Elizabeth Hall, Southbank Centre"
            elif "purcell room" in venue_name_lower:
                venue_name = "Purcell Room, Southbank Centre"
            elif "hayward" in venue_name_lower:
                venue_name = "Hayward Gallery, Southbank Centre"
            elif "southbank" not in venue_name_lower:
                venue_name = "Southbank Centre"

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
                venue_address="Belvedere Road, London SE1 8XX",
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
        if "/music" in page_url.lower() or "/classical" in page_url.lower():
            return "music"
        elif "/contemporary" in page_url.lower():
            return "contemporary"
        elif "/dance" in page_url.lower():
            return "dance"
        elif "/art" in page_url.lower():
            return "arts"
        elif "/literature" in page_url.lower():
            return "literature"
        elif "/talks" in page_url.lower():
            return "talks"
        elif "/family" in page_url.lower():
            return "family"

        # Check title/description for keywords
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
