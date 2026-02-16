"""Resident Advisor event source via GraphQL API."""
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import httpx
from .base_scraper import BaseScraper
from ..base import EventData
from ...config import settings

logger = logging.getLogger(__name__)


class ResidentAdvisorScraper(BaseScraper):
    """
    Event source for Resident Advisor (ra.co) using their GraphQL API.

    The HTML site is protected by DataDome (403), but the GraphQL
    endpoint at /graphql is open with no auth required.

    On first use, introspects the Event type to discover the date
    field name. If no usable date field is found, disables itself.
    """

    GRAPHQL_URL = "https://ra.co/graphql"

    # Query types that work without auth
    QUERY_TYPES = ["POPULAR", "TODAY", "PICKS"]

    # Fields known from introspection (always request these)
    BASE_FIELDS = "id title cost isTicketed contentUrl"

    # Candidate date field names to look for during introspection (ordered by priority)
    DATE_FIELD_CANDIDATES = [
        "startTime", "startDate", "start", "dateTime", "eventDate",
        "date", "startsAt", "starts_at", "start_time", "starttime",
        "time", "endTime", "endDate",
    ]

    def __init__(self):
        super().__init__()
        self._date_field: Optional[str] = None
        self._venue_field: Optional[str] = None
        self._introspected = False
        self._enabled = True

    @property
    def name(self) -> str:
        return "resident_advisor"

    @property
    def display_name(self) -> str:
        return "Resident Advisor"

    def is_enabled(self) -> bool:
        """Enabled unless introspection found no date field."""
        return self._enabled

    def _graphql_request(self, query: str, variables: Optional[dict] = None) -> Optional[dict]:
        """POST a GraphQL query and return the JSON response."""
        headers = {
            "User-Agent": settings.scraping_user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "https://ra.co/events",
        }

        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            import time
            time.sleep(self.get_rate_limit_delay())

            response = httpx.post(
                self.GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=settings.scraping_timeout,
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                logger.warning(f"RA GraphQL errors: {result['errors']}")

            return result.get("data")

        except httpx.HTTPStatusError as e:
            logger.error(f"RA GraphQL HTTP error {e.response.status_code}: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"RA GraphQL request error: {e}")
            return None
        except Exception as e:
            logger.error(f"RA GraphQL unexpected error: {e}")
            return None

    def _introspect_event_type(self) -> None:
        """Introspect the Event type to discover date and venue fields."""
        self._introspected = True

        query = """
        {
          __type(name: "Event") {
            fields { name type { name kind ofType { name } } }
          }
        }
        """
        data = self._graphql_request(query)
        if not data or not data.get("__type"):
            logger.error("RA: Introspection failed — could not read Event type")
            self._enabled = False
            return

        fields = data["__type"].get("fields", [])
        field_names = {f["name"] for f in fields}
        logger.info(f"RA: Event type has {len(field_names)} fields: "
                     f"{sorted(field_names)}")

        # Find date field
        for candidate in self.DATE_FIELD_CANDIDATES:
            if candidate in field_names:
                self._date_field = candidate
                logger.info(f"RA: Found date field: '{candidate}'")
                break

        if not self._date_field:
            # Also check for any field containing "date" or "time" in its name
            for fname in sorted(field_names):
                lower = fname.lower()
                if any(kw in lower for kw in ("date", "time", "start", "when")):
                    self._date_field = fname
                    logger.info(f"RA: Found likely date field: '{fname}'")
                    break

        if not self._date_field:
            logger.warning(
                "RA: No date field found on Event type. "
                "Disabling scraper — events without dates are unusable. "
                f"Available fields: {sorted(field_names)}"
            )
            self._enabled = False
            return

        # Find venue/area field
        for candidate in ("venue", "area", "location", "place"):
            if candidate in field_names:
                self._venue_field = candidate
                logger.info(f"RA: Found venue field: '{candidate}'")
                break

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Resident Advisor GraphQL API."""
        # Introspect on first call
        if not self._introspected:
            self._introspect_event_type()

        if not self._enabled or not self._date_field:
            return []

        seen_ids = set()
        events = []

        for query_type in self.QUERY_TYPES:
            logger.info(f"RA: Querying {query_type} events")
            page_events = self._fetch_events_by_type(
                query_type, seen_ids
            )
            events.extend(page_events)

        # Filter by date range and validate
        filtered_events = []
        for event in events:
            if event.start_date and start_date <= event.start_date <= end_date:
                if self.validate_event(event):
                    filtered_events.append(event)

        logger.info(f"RA: Fetched {len(filtered_events)} events "
                     f"({len(seen_ids)} unique across query types)")
        return filtered_events

    def _fetch_events_by_type(
        self, query_type: str, seen_ids: set
    ) -> List[EventData]:
        """Fetch events for a specific query type."""
        # Build venue sub-query if we found a venue field
        venue_fragment = ""
        if self._venue_field == "venue":
            venue_fragment = "venue { id name address }"
        elif self._venue_field == "area":
            venue_fragment = "area { id name }"
        elif self._venue_field:
            venue_fragment = self._venue_field

        query = f"""
        {{
          events(type: {query_type}, limit: 30) {{
            {self.BASE_FIELDS}
            {self._date_field}
            {venue_fragment}
          }}
        }}
        """

        data = self._graphql_request(query)
        if not data or not data.get("events"):
            return []

        events = []
        for event_data in data["events"]:
            try:
                event = self._parse_event(event_data, seen_ids)
                if event:
                    events.append(event)
            except Exception as e:
                title = event_data.get("title", "unknown")
                logger.debug(f"RA: Skipping event '{title}': {e}")

        return events

    def _parse_event(
        self, data: dict, seen_ids: set
    ) -> Optional[EventData]:
        """Parse a single RA event from GraphQL response."""
        # ID — required
        event_id = data.get("id")
        if not event_id:
            return None
        event_id = str(event_id)

        if event_id in seen_ids:
            return None
        seen_ids.add(event_id)

        # Title — required
        title = (data.get("title") or "").strip()
        if not title:
            return None

        # Date — required
        date_value = data.get(self._date_field)
        start_date = self._parse_date(date_value)
        if not start_date:
            logger.debug(f"RA: Skipping '{title}': unparseable date '{date_value}'")
            return None

        # Venue
        venue_name = None
        venue_address = None
        if self._venue_field == "venue":
            venue_data = data.get("venue", {})
            if isinstance(venue_data, dict):
                venue_name = venue_data.get("name")
                venue_address = venue_data.get("address")
        elif self._venue_field == "area":
            area_data = data.get("area", {})
            if isinstance(area_data, dict):
                venue_name = area_data.get("name")

        # Price from cost string (e.g. "£3 - £8")
        price_min = None
        price_max = None
        cost = data.get("cost", "")
        if cost and isinstance(cost, str):
            prices = re.findall(r"£(\d+(?:\.\d{2})?)", cost)
            if prices:
                price_min = float(prices[0])
                if len(prices) > 1:
                    price_max = float(prices[-1])

        # URL
        content_url = data.get("contentUrl", "")
        source_url = f"https://ra.co{content_url}" if content_url else None

        return EventData(
            title=title,
            start_date=start_date,
            source_name=self.name,
            source_id=event_id,
            source_url=source_url,
            venue_name=venue_name,
            venue_address=venue_address,
            price_min=price_min,
            price_max=price_max,
            categories=["music"],
        )

    def _parse_date(self, value) -> Optional[datetime]:
        """Parse a date value from the GraphQL response."""
        if not value:
            return None

        # Unix timestamp (int or float)
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except (ValueError, OSError, OverflowError):
                return None

        if not isinstance(value, str):
            return None

        value = value.strip()

        # ISO 8601 format (e.g. "2026-02-14T22:00:00.000")
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        # Unix timestamp as string
        try:
            ts = int(value)
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError, OverflowError):
            pass

        logger.debug(f"RA: Could not parse date '{value}'")
        return None

    def _get_listing_urls(self, start_date, end_date) -> list:
        """Not used — this source uses GraphQL, not HTML pages."""
        return []

    def _parse_listing_page(self, soup, page_url: str) -> list:
        """Not used — this source uses GraphQL, not HTML pages."""
        return []

    def get_rate_limit_delay(self) -> float:
        """1 second between API requests."""
        return 1.0
