"""The O2 Arena web scraper."""
import re
from typing import List, Optional, Tuple
from datetime import datetime
import logging
from bs4 import BeautifulSoup, Tag
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class O2ArenaScraper(BaseScraper):
    """
    Scraper for The O2 Arena events.
    Website: https://www.theo2.co.uk/events

    The O2 events page uses server-rendered HTML with Vue.js hydration.
    The first eventItem is a Vue template (has :href bindings); real
    events start from the second eventItem onward.
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
            logger.error(f"O2 Arena scraping error: {e}")
            raise

        # Filter by date range and validate
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"O2 Arena: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Get event listing URLs to scrape."""
        return [self.EVENTS_URL]

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Parse event listing page."""
        events = []

        event_items = soup.find_all("div", class_="eventItem")
        logger.debug(f"Found {len(event_items)} eventItem elements on {page_url}")

        for item in event_items:
            # Skip Vue.js template items (they use :href instead of href)
            if item.find(attrs={":href": True}):
                continue

            try:
                event = self._parse_event_card(item)
                if event:
                    events.append(event)
            except ValueError as e:
                logger.debug(f"Skipping event card: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error parsing O2 event card: {e}")

        return events

    def _parse_event_card(self, card: Tag) -> Optional[EventData]:
        """Parse individual event card from an eventItem div."""
        # Extract title
        title_elem = card.find(["h3", "div"], class_="title")
        if not title_elem:
            return None
        title_link = title_elem.find("a")
        title = title_elem.get_text(strip=True)
        if not title:
            return None

        # Extract detail URL
        event_url = None
        more_link = card.find("a", class_="more")
        if more_link and more_link.get("href"):
            event_url = more_link["href"]
        elif title_link and title_link.get("href"):
            event_url = title_link["href"]

        if not event_url:
            return None
        if not event_url.startswith("http"):
            event_url = self.BASE_URL + event_url

        # Generate source ID from URL
        source_id = event_url.rstrip("/").split("/")[-1]
        source_id = re.sub(r"[?#].*", "", source_id)
        if not source_id:
            return None

        # Extract date - REQUIRED, skip if missing
        date_div = card.find("div", class_="date")
        start_date = self._parse_date(date_div)
        if start_date is None:
            logger.debug(f"Skipping '{title}': no parseable date")
            return None

        # Extract venue
        venue_div = card.find("div", class_="location-search")
        venue_name = venue_div.get_text(strip=True) if venue_div else "The O2"
        if not venue_name:
            venue_name = "The O2"

        # Extract ticket URL and availability info
        ticket_link = card.find("a", class_="tickets")
        ticket_url = None
        on_sale_status = None
        if ticket_link:
            ticket_url = ticket_link.get("href")
            ticket_classes = ticket_link.get("class", [])
            if "onsalenow" in ticket_classes:
                on_sale_status = "on_sale"
            elif "soldout" in ticket_classes:
                on_sale_status = "sold_out"

        # Extract tagline (e.g., "Postponed")
        tagline = card.find("h4", class_="tagline")
        description = tagline.get_text(strip=True) if tagline else None
        if description and description.lower() == "postponed":
            on_sale_status = "postponed"

        # Extract image
        img_elem = card.find("img")
        image_url = None
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src")
            if image_url and not image_url.startswith("http"):
                image_url = self.BASE_URL + image_url

        # Determine category from title/description
        categories = [self._determine_category(title, description or "")]

        return EventData(
            title=title,
            description=description,
            start_date=start_date,
            source_name=self.name,
            source_id=source_id,
            source_url=event_url,
            venue_name=venue_name,
            venue_address="Peninsula Square, London SE10 0DX",
            ticket_url=ticket_url,
            image_url=image_url,
            categories=categories,
            on_sale_status=on_sale_status,
        )

    def _parse_date(self, date_div: Optional[Tag]) -> Optional[datetime]:
        """
        Parse date from O2's date div structure.

        O2 uses spans with classes like:
        - m-date__singleDate > m-date__day, m-date__month, m-date__year
        - m-date__rangeFirst > m-date__day, m-date__month (start of range)
        - m-date__rangeLast > m-date__day, m-date__month, m-date__year (end of range)

        Returns None if date cannot be parsed (never returns datetime.now()).
        """
        if not date_div:
            return None

        try:
            # Try single date first
            single = date_div.find("span", class_="m-date__singleDate")
            if single:
                return self._extract_date_from_spans(single)

            # Try range - use the first date
            range_first = date_div.find("span", class_="m-date__rangeFirst")
            if range_first:
                # Range first might not have year, get it from rangeLast
                range_last = date_div.find("span", class_="m-date__rangeLast")
                year_span = None
                if range_last:
                    year_span = range_last.find("span", class_="m-date__year")
                return self._extract_date_from_spans(range_first, fallback_year_span=year_span)

            # Fallback: try to parse the entire date text
            date_text = date_div.get_text(strip=True)
            if date_text:
                return self._parse_date_text(date_text)

        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not parse O2 date: {e}")

        return None

    def _extract_date_from_spans(
        self, container: Tag, fallback_year_span: Optional[Tag] = None
    ) -> Optional[datetime]:
        """Extract date from day/month/year spans within a container."""
        day_span = container.find("span", class_="m-date__day")
        month_span = container.find("span", class_="m-date__month")
        year_span = container.find("span", class_="m-date__year")

        if not year_span and fallback_year_span:
            year_span = fallback_year_span

        if not day_span or not month_span:
            return None

        day_text = day_span.get_text(strip=True)
        month_text = month_span.get_text(strip=True)
        year_text = year_span.get_text(strip=True) if year_span else str(datetime.now().year)

        try:
            day = int(day_text)
            month = self._month_to_int(month_text)
            year = int(year_text)
            if month is None:
                return None
            return datetime(year, month, day)
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to construct date from day={day_text} month={month_text} year={year_text}: {e}")
            return None

    def _month_to_int(self, month_text: str) -> Optional[int]:
        """Convert month abbreviation to integer."""
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        return months.get(month_text.lower().strip()[:3])

    def _parse_date_text(self, date_text: str) -> Optional[datetime]:
        """Parse a date string like '13 Feb 2026' or '13Feb2026'."""
        # Try pattern: day month year (with or without spaces)
        match = re.search(
            r"(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*(\d{4})",
            date_text,
            re.IGNORECASE,
        )
        if match:
            try:
                day = int(match.group(1))
                month = self._month_to_int(match.group(2))
                year = int(match.group(3))
                if month:
                    return datetime(year, month, day)
            except (ValueError, TypeError):
                pass
        return None

    def _parse_price(self, price_text: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        """Parse price from text. Returns (min_price, max_price)."""
        if not price_text:
            return None, None

        try:
            text_lower = price_text.lower()
            if "free" in text_lower:
                return 0.0, 0.0

            # Only match prices with £ sign to avoid matching random numbers
            prices = re.findall(r"£(\d+(?:\.\d{2})?)", price_text)
            if prices:
                float_prices = [float(p) for p in prices]
                return min(float_prices), max(float_prices)
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse price '{price_text}': {e}")

        return None, None

    def _determine_category(self, title: str, description: str) -> str:
        """Determine event category from title and description."""
        combined = (title + " " + description).lower()
        if any(word in combined for word in ["concert", "tour", "music", "band", "singer", "live"]):
            return "music"
        elif any(word in combined for word in ["comedy", "comedian", "stand-up", "stand up"]):
            return "comedy"
        elif any(word in combined for word in ["sport", "football", "basketball", "tennis", "boxing", "wrestling"]):
            return "sports"
        elif any(word in combined for word in ["family", "kids", "children", "disney"]):
            return "family"
        elif any(word in combined for word in ["dance", "dancing", "strictly"]):
            return "dance"
        return "entertainment"

    def get_rate_limit_delay(self) -> float:
        """Be respectful with scraping - 3 seconds between requests."""
        return 3.0
