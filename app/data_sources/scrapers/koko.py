"""KOKO venue scraper via __NEXT_DATA__ JSON extraction."""
import json
import re
from typing import List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class KokoScraper(BaseScraper):
    """
    Scraper for KOKO (koko.co.uk).

    The site is a Next.js app with Emotion CSS (hashed class names).
    All event data is embedded in a <script id="__NEXT_DATA__"> tag
    as structured JSON — no CSS selectors needed.
    """

    BASE_URL = "https://koko.co.uk"
    EVENTS_URL = f"{BASE_URL}/whats-on"

    # Genre name -> standardized category
    GENRE_MAP = {
        "electronic": "music",
        "rock": "music",
        "jazz": "music",
        "alternative/indie": "music",
        "pop": "music",
        "hip hop": "music",
        "r&b": "music",
        "soul": "music",
        "funk": "music",
        "metal": "music",
        "punk": "music",
        "folk": "music",
        "classical": "classical",
        "comedy": "comedy",
        "dance": "dance",
        "theatre": "theatre",
    }

    @property
    def name(self) -> str:
        return "koko"

    @property
    def display_name(self) -> str:
        return "KOKO"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from KOKO."""
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
            logger.error(f"KOKO scraping error: {e}")
            raise

        # Filter by date range and validate
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"KOKO: Scraped {len(filtered_events)} events")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Single page contains all events."""
        return [self.EVENTS_URL]

    def _parse_listing_page(self, soup: BeautifulSoup, page_url: str) -> list:
        """Extract events from __NEXT_DATA__ JSON."""
        events = []

        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag or not script_tag.string:
            logger.warning("KOKO: No __NEXT_DATA__ script tag found")
            return events

        try:
            next_data = json.loads(script_tag.string)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"KOKO: Failed to parse __NEXT_DATA__ JSON: {e}")
            return events

        # Navigate to events list
        try:
            nodes = (
                next_data["props"]["pageProps"]["data"]["events"]["nodes"]
            )
        except (KeyError, TypeError) as e:
            logger.warning(f"KOKO: Unexpected JSON structure: {e}")
            return events

        logger.debug(f"KOKO: Found {len(nodes)} event nodes")

        for node in nodes:
            try:
                event = self._parse_event_node(node)
                if event:
                    events.append(event)
            except Exception as e:
                title = node.get("title", "unknown")
                logger.debug(f"Skipping KOKO event '{title}': {e}")

        return events

    def _parse_event_node(self, node: dict) -> Optional[EventData]:
        """Parse a single event node from the __NEXT_DATA__ JSON."""
        # Title
        title = node.get("title", "").strip()
        if not title:
            return None

        # Source ID
        database_id = node.get("databaseId")
        if not database_id:
            return None
        source_id = str(database_id)

        # Event URL
        uri = node.get("uri", "")
        source_url = f"{self.BASE_URL}{uri}" if uri else self.EVENTS_URL

        # Event info
        event_info = node.get("event", {}).get("eventinfo", {})

        # Date — REQUIRED
        start_date = self._parse_event_date(event_info.get("startdate"))
        if start_date is None:
            logger.debug(f"Skipping KOKO '{title}': no parseable date")
            return None

        # Door time
        door_time = event_info.get("doorsopen")
        if door_time and start_date:
            parsed_time = self._parse_door_time(door_time)
            if parsed_time:
                start_date = start_date.replace(
                    hour=parsed_time[0], minute=parsed_time[1]
                )

        # Description
        description = event_info.get("eventStrapline")

        # Sold out status
        event_status = event_info.get("eventstatus")
        on_sale_status = None
        if event_status == "soldout":
            on_sale_status = "sold_out"
        else:
            on_sale_status = "on_sale"

        # Ticket URL
        tickets_info = node.get("event", {}).get("tickets", {})
        ticket_url = tickets_info.get("ticketLink") if tickets_info else None

        # Image
        artist_info = node.get("event", {}).get("artist", {})
        image_url = None
        if artist_info:
            img_data = artist_info.get("artistimagesquare")
            if img_data and isinstance(img_data, dict):
                image_url = img_data.get("sourceUrl")

        # Genres -> categories
        categories = []
        genre_info = node.get("event", {}).get("genre", {})
        if genre_info:
            genre_list = genre_info.get("eventgenres", [])
            if genre_list:
                for genre in genre_list:
                    genre_name = genre.get("name", "").lower()
                    mapped = self.GENRE_MAP.get(genre_name, "music")
                    if mapped not in categories:
                        categories.append(mapped)
        if not categories:
            categories = ["music"]

        return EventData(
            title=title,
            description=description,
            start_date=start_date,
            source_name=self.name,
            source_id=source_id,
            source_url=source_url,
            venue_name="KOKO",
            venue_address="1A Camden High St, London NW1 7JE",
            ticket_url=ticket_url,
            image_url=image_url,
            categories=categories,
            on_sale_status=on_sale_status,
        )

    def _parse_event_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date like 'February 14, 2026'. Returns None on failure."""
        if not date_str or not isinstance(date_str, str):
            return None
        date_str = date_str.strip()
        try:
            return datetime.strptime(date_str, "%B %d, %Y")
        except ValueError:
            pass
        # Try alternate format: "14 February 2026"
        try:
            return datetime.strptime(date_str, "%d %B %Y")
        except ValueError:
            pass
        logger.debug(f"KOKO: Could not parse date '{date_str}'")
        return None

    def _parse_door_time(self, time_str: str) -> Optional[tuple]:
        """Parse door time like '10:00 pm'. Returns (hour, minute) or None."""
        if not time_str:
            return None
        match = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str.strip(), re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            period = match.group(3).lower()
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            return (hour, minute)
        return None

    def get_rate_limit_delay(self) -> float:
        """3 seconds between requests."""
        return 3.0
