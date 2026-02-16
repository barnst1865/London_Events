"""Official London Theatre (West End) scraper via WordPress REST API."""
import html
import re
import json
from typing import List, Optional, Dict
from datetime import datetime
import logging
from .base_scraper import BaseScraper
from ..base import EventData

logger = logging.getLogger(__name__)


class OfficialLondonTheatreScraper(BaseScraper):
    """
    Scraper for Official London Theatre (officiallondontheatre.com).

    Uses the WordPress REST API to fetch structured JSON show data.
    No HTML parsing needed — all data comes from /wp-json/wp/v2/show.
    """

    BASE_URL = "https://officiallondontheatre.com"
    API_BASE = f"{BASE_URL}/wp-json/wp/v2"
    SHOWS_ENDPOINT = f"{API_BASE}/show"
    VENUE_ENDPOINT = f"{API_BASE}/venue"
    GENRE_ENDPOINT = f"{API_BASE}/genre"

    # Genre ID -> standardized category mapping
    GENRE_MAP = {
        54: "theatre",       # Musical
        1771: "theatre",     # Drama
        1770: "comedy",      # Comedy
        38: "dance",         # Dance
        61: "arts",          # Opera
        58354: "family",     # Family
        42: "entertainment", # Entertainment
        29927: "family",     # Children's
    }

    @property
    def name(self) -> str:
        return "official_london_theatre"

    @property
    def display_name(self) -> str:
        return "Official London Theatre"

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch shows from Official London Theatre API."""
        events = []
        venue_cache: Dict[int, str] = {}

        try:
            # Fetch all shows (paginated, up to 200)
            shows = self._fetch_all_shows()
            logger.info(f"OLT API returned {len(shows)} shows")

            for show in shows:
                try:
                    event = self._parse_show(show, venue_cache, start_date, end_date)
                    if event and self.validate_event(event):
                        events.append(event)
                except Exception as e:
                    title = show.get("title", {}).get("rendered", "unknown")
                    logger.debug(f"Skipping OLT show '{title}': {e}")

        except Exception as e:
            logger.error(f"OLT scraping error: {e}")
            raise

        logger.info(f"Official London Theatre: {len(events)} events")
        return events

    def _fetch_all_shows(self) -> list:
        """Fetch all shows across paginated API responses."""
        all_shows = []
        for page in range(1, 5):  # Up to 4 pages (400 shows max)
            url = f"{self.SHOWS_ENDPOINT}?per_page=100&page={page}"
            response = self._make_request(url, headers={
                "Accept": "application/json",
            })
            if not response:
                break

            try:
                shows = response.json()
            except (json.JSONDecodeError, ValueError):
                logger.error(f"OLT: Invalid JSON from page {page}")
                break

            if not shows:
                break

            all_shows.extend(shows)

            # Check if there are more pages
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break

        return all_shows

    def _parse_show(
        self,
        show: dict,
        venue_cache: Dict[int, str],
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[EventData]:
        """Parse a single show from the API response."""
        # Skip mothballed shows
        acf = show.get("acf", {})
        if acf.get("show_mothballed"):
            return None

        # Title
        title = show.get("title", {}).get("rendered", "")
        if not title:
            return None
        title = html.unescape(title).strip()
        if not title:
            return None

        # Source ID and URL
        source_id = str(show.get("id", ""))
        if not source_id:
            return None
        source_url = show.get("link", "")

        # Dates — parse YYYYMMDD format
        show_start = self._parse_acf_date(acf.get("show_opening_night"))
        show_end = self._parse_acf_date(acf.get("show_booking_until")) or \
                   self._parse_acf_date(acf.get("show_closing_night"))

        if show_start is None:
            logger.debug(f"Skipping '{title}': no opening night date")
            return None

        # Filter: show must overlap with requested date range
        # A show is relevant if it hasn't ended before start_date
        # and hasn't started after end_date
        if show_end and show_end < start_date:
            return None
        if show_start > end_date:
            return None

        # Venue
        venue_ids = acf.get("show_linked_venue", [])
        venue_name = "West End Theatre"
        if venue_ids:
            venue_id = venue_ids[0] if isinstance(venue_ids, list) else venue_ids
            venue_name = self._resolve_venue(int(venue_id), venue_cache)

        # Price
        price_min = None
        min_price_raw = acf.get("minimum_price")
        if min_price_raw is not None:
            try:
                price_min = float(min_price_raw)
            except (ValueError, TypeError):
                pass

        # Ticket URL
        ticket_url = None
        ticket_urls = acf.get("show_ticket_urls", [])
        if ticket_urls and isinstance(ticket_urls, list):
            first_ticket = ticket_urls[0] if ticket_urls else {}
            if isinstance(first_ticket, dict):
                ticket_url = first_ticket.get("show_ticket_url")

        # Categories from genre taxonomy
        categories = []
        genre_ids = show.get("genre", [])
        for gid in genre_ids:
            mapped = self.GENRE_MAP.get(gid)
            if mapped and mapped not in categories:
                categories.append(mapped)
        if not categories:
            categories = ["theatre"]

        # Description
        description = None
        duration = acf.get("show_duration_label")
        age = acf.get("show_age_suitability")
        parts = []
        if duration:
            parts.append(f"Duration: {duration}")
        if age:
            parts.append(f"Ages: {age}+")
        if parts:
            description = ". ".join(parts)

        return EventData(
            title=title,
            description=description,
            start_date=show_start,
            end_date=show_end,
            source_name=self.name,
            source_id=source_id,
            source_url=source_url,
            venue_name=venue_name,
            ticket_url=ticket_url,
            price_min=price_min,
            image_url=None,
            categories=categories,
        )

    def _resolve_venue(self, venue_id: int, cache: Dict[int, str]) -> str:
        """Resolve venue ID to name, with caching."""
        if venue_id in cache:
            return cache[venue_id]

        url = f"{self.VENUE_ENDPOINT}/{venue_id}?_fields=id,title"
        response = self._make_request(url, headers={
            "Accept": "application/json",
        })
        if response:
            try:
                data = response.json()
                name = html.unescape(data.get("title", {}).get("rendered", "West End Theatre"))
                cache[venue_id] = name
                return name
            except (json.JSONDecodeError, ValueError):
                pass

        cache[venue_id] = "West End Theatre"
        return "West End Theatre"

    def _parse_acf_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ACF date in YYYYMMDD format. Returns None on failure."""
        if not date_str or not isinstance(date_str, str):
            return None
        date_str = date_str.strip()
        if len(date_str) != 8:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return None

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Not used — API-based scraper overrides fetch_events directly."""
        return []

    def _parse_listing_page(self, soup, page_url) -> list:
        """Not used — API-based scraper overrides fetch_events directly."""
        return []

    def get_rate_limit_delay(self) -> float:
        """1 second between API requests."""
        return 1.0
