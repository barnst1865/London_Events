"""SeatGeek API data source."""
import httpx
from typing import List
from datetime import datetime
import logging
from .base import BaseDataSource, EventData
from ..config import settings

logger = logging.getLogger(__name__)


class SeatGeekSource(BaseDataSource):
    """
    SeatGeek API integration.
    API Docs: https://platform.seatgeek.com/
    """

    BASE_URL = "https://api.seatgeek.com/2"
    LONDON_METRO_CODE = "333"  # London metro code

    @property
    def name(self) -> str:
        return "seatgeek"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self) -> bool:
        """Check if API credentials are configured."""
        return bool(settings.seatgeek_client_id)

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from SeatGeek API."""
        if not self.is_enabled():
            logger.warning("SeatGeek client ID not configured")
            return []

        events = []
        page = 1
        per_page = 100

        try:
            while True:
                params = {
                    "client_id": settings.seatgeek_client_id,
                    "venue.city": "London",
                    "venue.country": "GB",
                    "datetime_local.gte": start_date.strftime("%Y-%m-%d"),
                    "datetime_local.lte": end_date.strftime("%Y-%m-%d"),
                    "per_page": per_page,
                    "page": page,
                }

                response = httpx.get(
                    f"{self.BASE_URL}/events",
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                # Parse events
                current_events = data.get("events", [])
                if not current_events:
                    break

                for event_data in current_events:
                    event = self._parse_event(event_data)
                    if event and self.validate_event(event):
                        events.append(event)

                # Check if more pages
                meta = data.get("meta", {})
                total = meta.get("total", 0)
                if page * per_page >= total:
                    break

                page += 1
                logger.info(f"SeatGeek: Fetched page {page}")

        except Exception as e:
            logger.error(f"SeatGeek API error: {e}")
            raise

        logger.info(f"SeatGeek: Fetched {len(events)} events")
        return events

    def _parse_event(self, data: dict) -> EventData:
        """Parse SeatGeek event data to EventData."""
        try:
            # Basic info
            event_id = str(data["id"])
            title = data["title"]
            url = data.get("url")

            # Dates
            start_date = self._parse_date(data["datetime_local"])

            # Announced date (might indicate on-sale)
            announced_date = self._parse_date(data.get("announce_date"))

            # Venue info
            venue = data.get("venue", {})
            venue_name = venue.get("name")
            address = venue.get("address")
            lat = venue.get("location", {}).get("lat")
            lon = venue.get("location", {}).get("lon")

            # Pricing
            stats = data.get("stats", {})
            price_min = stats.get("lowest_price")
            price_max = stats.get("highest_price")

            # SeatGeek prices can be in different currencies
            currency = "GBP"  # Assume GBP for London

            # Availability
            tickets_available = stats.get("listing_count")

            # Images
            performers = data.get("performers", [])
            image_url = None
            if performers:
                image_url = performers[0].get("image")

            # Categories
            categories = []
            event_type = data.get("type")
            if event_type:
                categories.append(self.transform_category(event_type))

            # Add taxonomies (genre/subgenre)
            for taxonomy in data.get("taxonomies", []):
                if taxonomy.get("name"):
                    categories.append(self.transform_category(taxonomy["name"]))

            return EventData(
                title=title,
                start_date=start_date,
                source_name=self.name,
                source_id=event_id,
                source_url=url,
                venue_name=venue_name,
                venue_address=address,
                latitude=lat,
                longitude=lon,
                ticket_url=url,
                price_min=price_min,
                price_max=price_max,
                currency=currency,
                on_sale_date=announced_date,
                tickets_available=tickets_available,
                image_url=image_url,
                categories=list(set(categories))[:5],  # Dedupe and limit
                raw_data=data,
            )

        except Exception as e:
            logger.error(f"Error parsing SeatGeek event: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse ISO date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def get_rate_limit_delay(self) -> float:
        """Conservative rate limiting."""
        return 0.3

    def transform_category(self, source_category: str) -> str:
        """Map SeatGeek categories to standardized ones."""
        category_map = {
            "concert": "music",
            "sports": "sports",
            "theater": "theatre",
            "comedy": "comedy",
            "festival": "festival",
            "family": "family",
            "classical": "classical",
            "broadway": "theatre",
            "nba": "sports",
            "nfl": "sports",
            "mlb": "sports",
            "nhl": "sports",
            "soccer": "sports",
            "mls": "sports",
        }
        return category_map.get(source_category.lower(), source_category.lower())
