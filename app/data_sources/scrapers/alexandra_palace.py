"""Alexandra Palace venue scraper."""
import re
from typing import List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup, Tag
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class AlexandraPalaceScraper(BaseScraper):
    """
    Scraper for Alexandra Palace (alexandrapalace.com).

    Server-rendered HTML. Events are listed as .event_card elements
    (note: underscore, not hyphen) on the /whats-on page.
    """

    BASE_URL = "https://www.alexandrapalace.com"
    EVENTS_URL = f"{BASE_URL}/whats-on/"

    @property
    def name(self) -> str:
        return "alexandra_palace"

    @property
    def display_name(self) -> str:
        return "Alexandra Palace"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Alexandra Palace."""
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
            logger.error(f"Alexandra Palace scraping error: {e}")
            raise

        # Filter by date range and validate
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"Alexandra Palace: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs."""
        return [self.EVENTS_URL]

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        # Alexandra Palace uses .event_card (underscore)
        cards = soup.find_all(class_="event_card")
        logger.debug(f"Alexandra Palace: Found {len(cards)} event_card elements")

        for card in cards:
            try:
                event = self._parse_event_card(card)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"Skipping Alexandra Palace event card: {e}")

        return events

    def _parse_event_card(self, card: Tag) -> Optional[EventData]:
        """Parse a single event card."""
        # Title — look in .event_details or any heading
        title = None
        details = card.find(class_="event_details")
        if details:
            heading = details.find(["h2", "h3", "h4"])
            if heading:
                title = heading.get_text(strip=True)
        if not title:
            heading = card.find(["h2", "h3", "h4"])
            if heading:
                title = heading.get_text(strip=True)
        if not title:
            return None

        # Link
        link_elem = card.find("a", class_="event_target") or card.find("a")
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

        # Date from .date-panel or similar
        start_date = None
        date_elem = card.find(class_="date-panel")
        if date_elem:
            start_date = self._parse_date_text(date_elem.get_text(strip=True))
        # Fallback: look for any date-like text in the card
        if start_date is None:
            for elem in card.find_all(class_=re.compile(r"date", re.IGNORECASE)):
                start_date = self._parse_date_text(elem.get_text(strip=True))
                if start_date:
                    break

        if start_date is None:
            logger.debug(f"Skipping Alexandra Palace '{title}': no parseable date")
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

        # Price
        price_min, price_max = self._parse_price(card)

        # Category
        categories = [self._determine_category(title)]

        return EventData(
            title=title,
            start_date=start_date,
            source_name=self.name,
            source_id=source_id,
            source_url=event_url,
            venue_name="Alexandra Palace",
            venue_address="Alexandra Palace Way, London N22 7AY",
            ticket_url=event_url,
            price_min=price_min,
            price_max=price_max,
            image_url=image_url,
            categories=categories,
        )

    def _parse_date_text(self, text: str) -> Optional[datetime]:
        """
        Parse date text like '14 Feb 2026', '14 February 2026',
        'Sat 14 Feb 2026', '14 Feb – 16 Feb 2026', etc.
        Returns the start date. Never returns datetime.now().
        """
        if not text:
            return None

        # Split on dash/en-dash to handle ranges
        parts = re.split(r"[–\-]", text, maxsplit=1)
        start_text = parts[0].strip()

        # Get year from end part if start doesn't have it
        year = None
        if len(parts) > 1:
            year_match = re.search(r"(\d{4})", parts[1])
            if year_match:
                year = int(year_match.group(1))

        match = re.search(
            r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*(?:\s+(\d{4}))?",
            start_text,
            re.IGNORECASE,
        )
        if match:
            try:
                day = int(match.group(1))
                month = self._month_to_int(match.group(2))
                if match.group(3):
                    year = int(match.group(3))
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

    def _determine_category(self, title: str) -> str:
        """Determine event category from title."""
        title_lower = title.lower()
        if any(w in title_lower for w in ["concert", "music", "band", "singer", "live", "dj", "festival"]):
            return "music"
        elif any(w in title_lower for w in ["comedy", "comedian", "stand-up"]):
            return "comedy"
        elif any(w in title_lower for w in ["theatre", "play", "drama", "musical"]):
            return "theatre"
        elif any(w in title_lower for w in ["darts", "sport", "snooker", "boxing", "wrestling"]):
            return "sports"
        elif any(w in title_lower for w in ["family", "kids", "children"]):
            return "family"
        elif any(w in title_lower for w in ["exhibition", "art", "gallery"]):
            return "arts"
        return "entertainment"

    def get_rate_limit_delay(self) -> float:
        """3 seconds between requests."""
        return 3.0
