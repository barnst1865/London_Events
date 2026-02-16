"""Roundhouse venue scraper."""
import re
from typing import List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup, Tag
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class RoundhouseScraper(BaseScraper):
    """
    Scraper for Roundhouse (roundhouse.org.uk).

    Server-rendered HTML with clean CSS selectors.
    Events are listed as .event-card elements on the /whats-on page.
    """

    BASE_URL = "https://www.roundhouse.org.uk"
    EVENTS_URL = f"{BASE_URL}/whats-on/"

    @property
    def name(self) -> str:
        return "roundhouse"

    @property
    def display_name(self) -> str:
        return "Roundhouse"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Roundhouse."""
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
            logger.error(f"Roundhouse scraping error: {e}")
            raise

        # Filter by date range and validate
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"Roundhouse: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs."""
        return [self.EVENTS_URL]

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        cards = soup.find_all(class_="event-card")
        logger.debug(f"Roundhouse: Found {len(cards)} event-card elements")

        for card in cards:
            try:
                event = self._parse_event_card(card)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Skipping Roundhouse event card: {e}")

        return events

    def _parse_event_card(self, card: Tag) -> Optional[EventData]:
        """Parse a single event card."""
        # Title
        title_elem = card.find(class_="event-card__title")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if not title:
            return None

        # Link
        link_elem = card.find("a", class_="event-card__link") or card.find("a")
        event_url = None
        if link_elem and link_elem.get("href"):
            href = link_elem["href"]
            event_url = href if href.startswith("http") else self.BASE_URL + href

        if not event_url:
            return None

        # Source ID from URL slug
        source_id = event_url.rstrip("/").split("/")[-1]
        source_id = re.sub(r"[?#].*", "", source_id)
        if not source_id:
            return None

        # Date
        date_elem = card.find(class_="event-card__date")
        start_date = None
        if date_elem:
            start_date = self._parse_date_text(date_elem.get_text(strip=True))
        if start_date is None:
            logger.debug(f"Skipping Roundhouse '{title}': no parseable date")
            return None

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

        # Category
        categories = [self._determine_category(title)]

        return EventData(
            title=title,
            start_date=start_date,
            source_name=self.name,
            source_id=source_id,
            source_url=event_url,
            venue_name="Roundhouse",
            venue_address="Chalk Farm Road, London NW1 8EH",
            ticket_url=event_url,
            image_url=image_url,
            categories=categories,
        )

    def _parse_date_text(self, text: str) -> Optional[datetime]:
        """
        Parse Roundhouse date formats. Examples from live site:
        - "Fri 20 February"
        - "Mon 16-Wed 18 February"
        - "Tue 17 Feb 26" (2-digit year)
        - "Mondays, 2 February-27 April"
        - "Tue 17 Feb 26\u2013Wed 18 Feb 26" (en-dash separator)

        Returns the start date. Never returns datetime.now().
        """
        if not text:
            return None

        # Split on dash/en-dash/special chars to handle ranges — take start
        parts = re.split(r"[\u2013\-]", text, maxsplit=1)
        start_text = parts[0].strip()
        end_text = parts[1].strip() if len(parts) > 1 else ""

        # Try to find year (2 or 4 digit) in start text first, then end text
        year = None
        for search_text in [start_text, end_text]:
            # 4-digit year
            y4 = re.search(r"(\d{4})", search_text)
            if y4:
                year = int(y4.group(1))
                break
            # 2-digit year (e.g., "Feb 26")
            y2 = re.search(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{2})\b", search_text, re.IGNORECASE)
            if y2:
                year = 2000 + int(y2.group(1))
                break

        # Try to find month in start text first, then end text
        month = None
        for search_text in [start_text, end_text]:
            m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*", search_text, re.IGNORECASE)
            if m:
                month = self._month_to_int(m.group(1))
                break

        # Find day number in start text
        day_match = re.search(r"(\d{1,2})", start_text)
        if not day_match or not month:
            return None
        day = int(day_match.group(1))

        # If no year found anywhere, use current year
        # The date range filter in fetch_events() handles out-of-range dates
        if year is None:
            year = datetime.now().year

        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def _month_to_int(self, month_text: str) -> Optional[int]:
        """Convert month abbreviation to integer."""
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        return months.get(month_text.lower().strip()[:3])

    def _determine_category(self, title: str) -> str:
        """Determine event category from title."""
        title_lower = title.lower()
        if any(w in title_lower for w in ["concert", "music", "band", "singer", "live", "dj"]):
            return "music"
        elif any(w in title_lower for w in ["comedy", "comedian", "stand-up"]):
            return "comedy"
        elif any(w in title_lower for w in ["theatre", "play", "drama", "musical"]):
            return "theatre"
        elif any(w in title_lower for w in ["dance", "ballet"]):
            return "dance"
        elif any(w in title_lower for w in ["circus", "cabaret"]):
            return "entertainment"
        elif any(w in title_lower for w in ["family", "kids", "children"]):
            return "family"
        return "arts"

    def get_rate_limit_delay(self) -> float:
        """3 seconds between requests."""
        return 3.0
