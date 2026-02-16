"""Eventim Apollo venue scraper."""
import re
from typing import List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup, Tag
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class EventimApolloScraper(BaseScraper):
    """
    Scraper for Eventim Apollo (eventimapollo.com).

    Server-rendered HTML. Events are listed as .card elements
    on the /events page.
    """

    BASE_URL = "https://www.eventimapollo.com"
    EVENTS_URL = f"{BASE_URL}/events/"

    @property
    def name(self) -> str:
        return "eventim_apollo"

    @property
    def display_name(self) -> str:
        return "Eventim Apollo"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Eventim Apollo."""
        events = []

        try:
            listing_urls = self._get_listing_urls(start_date, end_date)

            for url in listing_urls:
                logger.info(f"Scraping {url}")
                response = self._make_request(url)
                if not response:
                    continue

                soup = self._parse_html(response.text)
                if not soup:
                    continue

                page_events = self._parse_listing_page(soup, url)
                events.extend(page_events)

        except Exception as e:
            logger.error(f"Eventim Apollo scraping error: {e}")
            raise

        # Filter by date range and validate
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"Eventim Apollo: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs."""
        return [self.EVENTS_URL]

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        cards = soup.find_all(class_="card")
        logger.debug(f"Eventim Apollo: Found {len(cards)} card elements")

        for card in cards:
            try:
                event = self._parse_event_card(card)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Skipping Eventim Apollo event card: {e}")

        return events

    def _parse_event_card(self, card: Tag) -> Optional[EventData]:
        """Parse a single event card."""
        # Title
        title_elem = card.find(class_="card__title")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if not title:
            return None

        # Link — Eventim Apollo cards link to eventim.co.uk ticket pages
        link_elem = card.find("a")
        event_url = None
        ticket_url_from_link = None
        if link_elem and link_elem.get("href"):
            href = link_elem["href"]
            if href.startswith("http"):
                ticket_url_from_link = href
                event_url = href
            else:
                event_url = self.BASE_URL + href

        if not event_url:
            return None

        # Source ID from URL path (strip query params first)
        clean_url = re.sub(r"[?#].*", "", event_url)
        source_id = clean_url.rstrip("/").split("/")[-1]
        if not source_id:
            return None

        # Date
        start_date = None
        date_elem = card.find(class_="date")
        if date_elem:
            start_date = self._parse_date_text(date_elem.get_text(strip=True))
        if start_date is None:
            logger.debug(f"Skipping Eventim Apollo '{title}': no parseable date")
            return None

        # Info text
        info_elem = card.find(class_="card__info")
        description = info_elem.get_text(strip=True) if info_elem else None

        # Image
        image_url = None
        img_elem = card.find("img")
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src")
            if image_url and not image_url.startswith("http"):
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
                else:
                    image_url = self.BASE_URL + image_url

        # Ticket URL — the main link already points to eventim.co.uk tickets
        ticket_url = ticket_url_from_link or event_url

        # Price
        price_min, price_max = self._parse_price(card)

        # Category
        categories = [self._determine_category(title, description or "")]

        return EventData(
            title=title,
            description=description,
            start_date=start_date,
            source_name=self.name,
            source_id=source_id,
            source_url=event_url,
            venue_name="Eventim Apollo",
            venue_address="45 Queen Caroline St, London W6 9QH",
            ticket_url=ticket_url,
            price_min=price_min,
            price_max=price_max,
            image_url=image_url,
            categories=categories,
        )

    def _parse_date_text(self, text: str) -> Optional[datetime]:
        """
        Parse Eventim Apollo date formats. Examples from live site:
        - "Friday 20th February 2026"
        - "Saturday 21st February 2026"
        - "Feb 26th - Feb 27th 2026"
        - "Mar 3rd - Mar 16th 2026"
        Returns the start date. Never returns datetime.now().
        """
        if not text:
            return None

        # Strip ordinal suffixes (st, nd, rd, th) from numbers
        cleaned = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", text)

        # Split on dash/en-dash to handle ranges
        parts = re.split(r"[\u2013\-]", cleaned, maxsplit=1)
        start_text = parts[0].strip()
        end_text = parts[1].strip() if len(parts) > 1 else ""

        # Get year from end part if start doesn't have it
        year = None
        for search_text in [start_text, end_text]:
            year_match = re.search(r"(\d{4})", search_text)
            if year_match:
                year = int(year_match.group(1))
                break

        # Try "day month" pattern: "20 February" or "Friday 20 February"
        match = re.search(
            r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*",
            start_text,
            re.IGNORECASE,
        )
        # Try "month day" pattern: "Feb 26" or "Mar 3"
        if not match:
            match = re.search(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2})",
                start_text,
                re.IGNORECASE,
            )
            if match:
                month = self._month_to_int(match.group(1))
                day = int(match.group(2))
                if year is None:
                    return None
                if month:
                    try:
                        return datetime(year, month, day)
                    except ValueError:
                        return None
                return None

        if match:
            try:
                day = int(match.group(1))
                month = self._month_to_int(match.group(2))
                if year is None:
                    return None
                if month:
                    return datetime(year, month, day)
            except (ValueError, TypeError):
                pass

        return None

    def _month_to_int(self, month_text: str) -> Optional[int]:
        """Convert month abbreviation to integer."""
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        return months.get(month_text.lower().strip()[:3])

    def _parse_price(self, card: Tag) -> tuple:
        """Extract price from card. Returns (min_price, max_price)."""
        text = card.get_text()
        if "free" in text.lower():
            return 0.0, 0.0
        prices = re.findall(r"£(\d+(?:\.\d{2})?)", text)
        if prices:
            float_prices = [float(p) for p in prices]
            return min(float_prices), max(float_prices)
        return None, None

    def _determine_category(self, title: str, description: str) -> str:
        """Determine event category from title and description."""
        combined = (title + " " + description).lower()
        if any(w in combined for w in ["concert", "music", "band", "singer", "tour", "live"]):
            return "music"
        elif any(w in combined for w in ["comedy", "comedian", "stand-up", "stand up"]):
            return "comedy"
        elif any(w in combined for w in ["theatre", "play", "drama", "musical"]):
            return "theatre"
        elif any(w in combined for w in ["dance", "ballet"]):
            return "dance"
        elif any(w in combined for w in ["family", "kids", "children"]):
            return "family"
        return "music"  # Eventim Apollo is primarily a music venue

    def get_rate_limit_delay(self) -> float:
        """3 seconds between requests."""
        return 3.0
