"""Ticketmaster Discovery API data source."""
import httpx
from typing import List
from datetime import datetime
import logging
from .base import BaseDataSource, EventData
from ..config import settings

logger = logging.getLogger(__name__)


class TicketmasterSource(BaseDataSource):
    """
    Ticketmaster Discovery API integration.
    API Docs: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
    """

    BASE_URL = "https://app.ticketmaster.com/discovery/v2"
    LONDON_DMA_ID = "602"  # London DMA (Designated Market Area) ID
    CITY = "London"
    COUNTRY_CODE = "GB"

    @property
    def name(self) -> str:
        return "ticketmaster"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self) -> bool:
        """Check if API key is configured."""
        return bool(settings.ticketmaster_api_key)

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Ticketmaster API."""
        if not self.is_enabled():
            logger.warning("Ticketmaster API key not configured")
            return []

        events = []
        page = 0
        total_pages = 1

        try:
            while page < total_pages:
                params = {
                    "apikey": settings.ticketmaster_api_key,
                    "city": self.CITY,
                    "countryCode": self.COUNTRY_CODE,
                    "startDateTime": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "endDateTime": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "size": 200,  # Max per page
                    "page": page,
                    "sort": "date,asc",
                }

                response = httpx.get(
                    f"{self.BASE_URL}/events.json",
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                # Parse pagination
                if "_embedded" in data and "events" in data["_embedded"]:
                    for event_data in data["_embedded"]["events"]:
                        event = self._parse_event(event_data)
                        if event and self.validate_event(event):
                            events.append(event)

                # Check if more pages
                page_info = data.get("page", {})
                total_pages = page_info.get("totalPages", 1)
                page += 1

                logger.info(f"Ticketmaster: Fetched page {page}/{total_pages}")

        except Exception as e:
            logger.error(f"Ticketmaster API error: {e}")
            raise

        logger.info(f"Ticketmaster: Fetched {len(events)} events")
        return events

    def _parse_event(self, data: dict) -> EventData:
        """Parse Ticketmaster event data to EventData."""
        try:
            # Basic info
            event_id = data["id"]
            title = data["name"]
            url = data.get("url")

            # Dates
            dates = data.get("dates", {})
            start = dates.get("start", {})
            start_date = self._parse_date(start.get("dateTime") or start.get("localDate"))

            # Sales info
            sales = data.get("sales", {})
            public_sale = sales.get("public", {})
            on_sale_date = self._parse_date(public_sale.get("startDateTime"))
            status = dates.get("status", {}).get("code", "").lower()

            # Venue info
            venue = None
            venue_name = None
            address = None
            lat = None
            lon = None

            if "_embedded" in data and "venues" in data["_embedded"]:
                venue = data["_embedded"]["venues"][0]
                venue_name = venue.get("name")

                if "address" in venue:
                    addr = venue["address"]
                    address = f"{addr.get('line1', '')}, {venue.get('city', {}).get('name', '')}, {addr.get('postalCode', '')}"

                if "location" in venue:
                    loc = venue["location"]
                    lat = float(loc.get("latitude", 0)) or None
                    lon = float(loc.get("longitude", 0)) or None

            # Pricing
            price_ranges = data.get("priceRanges", [])
            price_min = None
            price_max = None
            currency = "GBP"

            if price_ranges:
                price_min = price_ranges[0].get("min")
                price_max = price_ranges[0].get("max")
                currency = price_ranges[0].get("currency", "GBP")

            # Images
            images = data.get("images", [])
            image_url = images[0]["url"] if images else None

            # Categories
            classifications = data.get("classifications", [])
            categories = []
            if classifications:
                segment = classifications[0].get("segment", {}).get("name")
                genre = classifications[0].get("genre", {}).get("name")
                if segment:
                    categories.append(self.transform_category(segment))
                if genre and genre != segment:
                    categories.append(self.transform_category(genre))

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
                on_sale_date=on_sale_date,
                on_sale_status=status,
                image_url=image_url,
                images=[img["url"] for img in images[:5]],
                categories=categories,
                raw_data=data,
            )

        except Exception as e:
            logger.error(f"Error parsing Ticketmaster event: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse ISO date string to datetime."""
        if not date_str:
            return None
        try:
            # Handle both full datetime and date-only formats
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return None

    def get_rate_limit_delay(self) -> float:
        """Ticketmaster allows 5 requests per second."""
        return 0.2

    def transform_category(self, source_category: str) -> str:
        """Map Ticketmaster categories to standardized ones."""
        category_map = {
            "music": "music",
            "sports": "sports",
            "arts & theatre": "theatre",
            "film": "film",
            "miscellaneous": "other",
            "family": "family",
        }
        return category_map.get(source_category.lower(), source_category.lower())
