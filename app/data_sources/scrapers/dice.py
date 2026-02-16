"""DICE event scraper via __NEXT_DATA__ JSON extraction."""
import json
import re
from typing import List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class DiceScraper(BaseScraper):
    """
    Scraper for DICE (dice.fm).

    The site is a Next.js app. All event data is embedded in a
    <script id="__NEXT_DATA__"> tag as structured JSON. Each category
    page returns up to ~30 events. Events are deduplicated across
    categories using their unique DICE event ID.
    """

    BASE_URL = "https://dice.fm"
    BROWSE_URL = f"{BASE_URL}/browse/london-54d8a23438fe5d27d500001c"

    # Category URL suffixes and their standardized category mappings
    CATEGORIES = {
        "music/gig": "music",
        "music/dj": "music",
        "music/party": "music",
        "culture/comedy": "comedy",
        "culture/theatre": "theatre",
        "culture/art": "arts",
        "culture/talks": "arts",
        "culture/film": "film",
        "culture/social": "arts",
    }

    @property
    def name(self) -> str:
        return "dice"

    @property
    def display_name(self) -> str:
        return "DICE"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from DICE across all category pages."""
        seen_ids = set()
        events = []

        for category_path, category_name in self.CATEGORIES.items():
            url = f"{self.BROWSE_URL}/{category_path}"
            logger.info(f"DICE: Scraping {url}")

            response = self._make_request(url)
            if not response:
                continue

            soup = self._parse_html(response.text)
            if not soup:
                continue

            page_events = self._parse_listing_page(
                soup, url, category_name, seen_ids
            )
            events.extend(page_events)

        # Filter by date range and validate
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"DICE: Scraped {len(filtered_events)} events "
                     f"({len(seen_ids)} unique across categories)")
        return filtered_events

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Not used — fetch_events iterates categories directly."""
        return []

    def _parse_listing_page(
        self,
        soup: BeautifulSoup,
        page_url: str,
        category_name: str = "music",
        seen_ids: Optional[set] = None,
    ) -> list:
        """Extract events from __NEXT_DATA__ JSON."""
        events = []

        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag or not script_tag.string:
            logger.warning(f"DICE: No __NEXT_DATA__ script tag found on {page_url}")
            return events

        try:
            next_data = json.loads(script_tag.string)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"DICE: Failed to parse __NEXT_DATA__ JSON: {e}")
            return events

        # Navigate to event list — structure may vary, try common paths
        event_list = self._extract_event_list(next_data)
        if not event_list:
            logger.warning(f"DICE: No events found in JSON on {page_url}")
            return events

        logger.debug(f"DICE: Found {len(event_list)} events on {page_url}")

        for event_data in event_list:
            try:
                event = self._parse_event(event_data, category_name, seen_ids)
                if event:
                    events.append(event)
            except Exception as e:
                title = event_data.get("name", "unknown")
                logger.debug(f"DICE: Skipping event '{title}': {e}")

        return events

    def _extract_event_list(self, next_data: dict) -> Optional[list]:
        """Extract event list from __NEXT_DATA__ JSON structure."""
        # Try common Next.js data paths
        try:
            page_props = next_data.get("props", {}).get("pageProps", {})

            # Path 1: Direct event list
            if "events" in page_props:
                events = page_props["events"]
                if isinstance(events, list):
                    return events

            # Path 2: Nested data structure
            if "data" in page_props:
                data = page_props["data"]
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    for key in ("events", "items", "results", "listings"):
                        if key in data and isinstance(data[key], list):
                            return data[key]

            # Path 3: Initial state / dehydrated state
            for key in ("initialData", "dehydratedState"):
                if key in page_props:
                    state = page_props[key]
                    if isinstance(state, dict):
                        queries = state.get("queries", [])
                        for query in queries:
                            query_data = query.get("state", {}).get("data", {})
                            if isinstance(query_data, list):
                                return query_data
                            if isinstance(query_data, dict):
                                for sub_key in ("data", "events", "items"):
                                    if sub_key in query_data and isinstance(query_data[sub_key], list):
                                        return query_data[sub_key]

            # Path 4: Walk top-level pageProps for any list of dicts with 'name' and 'date_unix'
            for key, value in page_props.items():
                if isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict) and "date_unix" in value[0]:
                        return value

        except (KeyError, TypeError, IndexError) as e:
            logger.debug(f"DICE: Error navigating JSON structure: {e}")

        return None

    def _parse_event(
        self,
        data: dict,
        category_name: str,
        seen_ids: Optional[set] = None,
    ) -> Optional[EventData]:
        """Parse a single event from the DICE JSON data."""
        # Event ID — required for deduplication
        event_id = data.get("id")
        if not event_id:
            return None
        event_id = str(event_id)

        # Deduplicate across categories
        if seen_ids is not None:
            if event_id in seen_ids:
                return None
            seen_ids.add(event_id)

        # Title — required
        title = (data.get("name") or "").strip()
        if not title:
            return None

        # Date — required (Unix timestamp)
        date_unix = data.get("date_unix")
        if not date_unix or not isinstance(date_unix, (int, float)):
            logger.debug(f"DICE: Skipping '{title}': no date_unix")
            return None

        try:
            start_date = datetime.fromtimestamp(int(date_unix))
        except (ValueError, OSError, OverflowError):
            logger.debug(f"DICE: Skipping '{title}': invalid timestamp {date_unix}")
            return None

        # Event URL
        perm_name = data.get("perm_name", "")
        source_url = f"{self.BASE_URL}/event/{perm_name}" if perm_name else None

        # Venue
        venue_name = None
        venue_address = None
        venues = data.get("venues", [])
        if venues and isinstance(venues, list) and isinstance(venues[0], dict):
            venue_name = venues[0].get("name")
            venue_address = venues[0].get("address")

        # Price (in pence)
        price_min = None
        price_data = data.get("price", {})
        if isinstance(price_data, dict):
            amount_from = price_data.get("amount_from")
            if isinstance(amount_from, (int, float)) and amount_from > 0:
                price_min = amount_from / 100.0

        # Status mapping
        status = data.get("status", "")
        on_sale_status = None
        if status == "sold-out":
            on_sale_status = "sold_out"
        elif status == "on-sale":
            on_sale_status = "on_sale"
        elif status:
            on_sale_status = status.replace("-", "_")

        # Image
        image_url = None
        images_data = data.get("images", {})
        if isinstance(images_data, dict):
            for img_key in ("square", "landscape", "wide"):
                img = images_data.get(img_key, {})
                if isinstance(img, dict) and img.get("url"):
                    image_url = img["url"]
                    break

        # Description from lineup
        description = None
        lineup = data.get("summary_lineup")
        if isinstance(lineup, dict):
            artists = lineup.get("names", [])
            if artists:
                description = "Lineup: " + ", ".join(artists)

        return EventData(
            title=title,
            description=description,
            start_date=start_date,
            source_name=self.name,
            source_id=event_id,
            source_url=source_url,
            venue_name=venue_name,
            venue_address=venue_address,
            price_min=price_min,
            on_sale_status=on_sale_status,
            image_url=image_url,
            categories=[category_name],
        )

    def get_rate_limit_delay(self) -> float:
        """3 seconds between category page requests."""
        return 3.0
