"""Barbican Centre web scraper."""
import re
from typing import List, Optional, Tuple
from datetime import datetime
import logging
from bs4 import BeautifulSoup, Tag
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class BarbicanScraper(BaseScraper):
    """
    Scraper for Barbican Centre events.
    Website: https://www.barbican.org.uk/whats-on

    The Barbican listing page uses div.search-listing--event cards.
    Dates are NOT on the listing page — they require fetching each
    event's detail page, which has <time datetime="..."> elements.
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
            logger.error(f"Barbican scraping error: {e}")
            raise

        # Filter by date range and validate
        filtered_events = []
        seen_ids = set()
        for event in events:
            if event.source_id in seen_ids:
                continue
            seen_ids.add(event.source_id)
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"Barbican: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        return [self.EVENTS_URL]

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page and fetch detail pages for dates."""
        events = []

        listings = soup.find_all("div", class_="search-listing--event")
        logger.debug(f"Found {len(listings)} search-listing--event elements on {page_url}")

        for listing in listings:
            try:
                event = self._parse_listing_card(listing, page_url)
                if event:
                    events.append(event)
            except ValueError as e:
                logger.debug(f"Skipping Barbican listing: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error parsing Barbican listing: {e}")

        return events

    def _parse_listing_card(self, card: Tag, page_url: str) -> Optional[EventData]:
        """Parse a search-listing card and fetch detail page for date."""
        # Extract title
        title_elem = card.find("h2", class_="listing-title")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if not title:
            return None

        # Extract URL
        link_elem = card.find("a", class_="search-listing__link")
        if not link_elem or not link_elem.get("href"):
            return None
        event_url = link_elem["href"]
        if not event_url.startswith("http"):
            event_url = self.BASE_URL + event_url

        # Generate source ID from URL path
        source_id = event_url.rstrip("/").split("/")[-1]
        source_id = re.sub(r"[?#].*", "", source_id)
        if not source_id:
            return None

        # Extract description from listing
        intro_elem = card.find("div", class_="search-listing__intro")
        description = intro_elem.get_text(strip=True) if intro_elem else None

        # Extract image
        image_url = None
        img_elem = card.find("img")
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src")
            if image_url and not image_url.startswith("http"):
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
                else:
                    image_url = self.BASE_URL + image_url

        # Extract category tags
        categories = []
        tags_div = card.find("div", class_="tags")
        if tags_div:
            for tag_span in tags_div.find_all("span", class_="tag__plain"):
                tag_text = tag_span.get_text(strip=True).lower()
                mapped = self._map_category(tag_text)
                if mapped and mapped not in categories:
                    categories.append(mapped)
        if not categories:
            categories = [self._determine_category(page_url, title, description or "")]

        # Extract price label (e.g., "Free")
        price_min, price_max = None, None
        label_elem = card.find("div", class_="search-listing__label")
        if label_elem:
            label_text = label_elem.get_text(strip=True).lower()
            if "free" in label_text:
                price_min, price_max = 0.0, 0.0

        # Fetch detail page for date
        start_date = self._fetch_detail_date(event_url)
        if start_date is None:
            logger.debug(f"Skipping '{title}': no parseable date from detail page")
            return None

        # Extract venue from detail page URL pattern or default
        venue_name = "Barbican Centre"

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

    def _fetch_detail_date(self, detail_url: str) -> Optional[datetime]:
        """Fetch an event detail page and extract the start date."""
        response = self._make_request(detail_url)
        if not response:
            return None

        soup = self._parse_html(response.text)
        if not soup:
            return None

        # Try <time> elements with datetime attribute (most reliable)
        time_elements = soup.find_all("time", attrs={"datetime": True})
        if time_elements:
            try:
                dt_str = time_elements[0]["datetime"]
                # Handle ISO format: 2026-01-30T11:00:00Z
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse <time> datetime '{dt_str}': {e}")

        # Try event-byline__date span
        byline_date = soup.find("span", class_="event-byline__date")
        if byline_date:
            date_range = byline_date.find("span", class_="date-range")
            if date_range:
                return self._parse_date_range_text(date_range.get_text(strip=True))

        return None

    def _parse_date_range_text(self, text: str) -> Optional[datetime]:
        """
        Parse date range text like 'Fri 30 Jan – Sun 19 Apr 2026'.
        Returns the start date.
        """
        if not text:
            return None

        # Split on dash/en-dash to get start date
        parts = re.split(r"[–\-]", text, maxsplit=1)
        start_text = parts[0].strip()
        # If start doesn't have year, get year from end part
        year = None
        if len(parts) > 1:
            year_match = re.search(r"(\d{4})", parts[1])
            if year_match:
                year = int(year_match.group(1))

        # Parse "Fri 30 Jan" or "30 Jan 2026"
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
                    year = datetime.now().year
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

    def _map_category(self, tag_text: str) -> Optional[str]:
        """Map Barbican tag text to standardized category."""
        mapping = {
            "music": "music",
            "classical music": "classical",
            "contemporary music": "music",
            "theatre": "theatre",
            "dance": "dance",
            "film": "film",
            "cinema": "film",
            "art & design": "arts",
            "art": "arts",
            "visual arts": "arts",
            "family": "family",
            "talks & events": "talks",
            "talks": "talks",
            "comedy": "comedy",
            "library": "arts",
            "tours & public spaces": "arts",
        }
        return mapping.get(tag_text.lower())

    def _determine_category(self, page_url: str, title: str, description: str) -> str:
        """Determine event category from URL and content."""
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
