"""Eventbrite API data source."""
import httpx
from typing import List
from datetime import datetime
import logging
from .base import BaseDataSource, EventData
from ..config import settings

logger = logging.getLogger(__name__)


class EventbriteSource(BaseDataSource):
    """
    Eventbrite API integration.
    API Docs: https://www.eventbrite.com/platform/api
    """

    BASE_URL = "https://www.eventbriteapi.com/v3"
    LONDON_LOCATION = "London, United Kingdom"

    @property
    def name(self) -> str:
        return "eventbrite"

    @property
    def source_type(self) -> str:
        return "api"

    def is_enabled(self) -> bool:
        """Check if API key is configured."""
        return bool(settings.eventbrite_api_key)

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """Fetch events from Eventbrite API."""
        if not self.is_enabled():
            logger.warning("Eventbrite API key not configured")
            return []

        events = []
        continuation = None
        has_more = True

        try:
            while has_more:
                params = {
                    "location.address": self.LONDON_LOCATION,
                    "location.within": "25mi",  # 25 mile radius
                    "start_date.range_start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "start_date.range_end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "expand": "venue,ticket_availability,category",
                }

                if continuation:
                    params["continuation"] = continuation

                headers = {
                    "Authorization": f"Bearer {settings.eventbrite_api_key}"
                }

                response = httpx.get(
                    f"{self.BASE_URL}/events/search/",
                    params=params,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                # Parse events
                for event_data in data.get("events", []):
                    event = self._parse_event(event_data)
                    if event and self.validate_event(event):
                        events.append(event)

                # Check pagination
                pagination = data.get("pagination", {})
                has_more = pagination.get("has_more_items", False)
                continuation = pagination.get("continuation")

                logger.info(f"Eventbrite: Fetched {len(data.get('events', []))} events")

        except Exception as e:
            logger.error(f"Eventbrite API error: {e}")
            raise

        logger.info(f"Eventbrite: Fetched {len(events)} events total")
        return events

    def _parse_event(self, data: dict) -> EventData:
        """Parse Eventbrite event data to EventData."""
        try:
            # Basic info
            event_id = data["id"]
            title = data["name"]["text"]
            description = data.get("description", {}).get("text")
            url = data.get("url")

            # Dates
            start_date = self._parse_date(data["start"]["utc"])
            end_date = self._parse_date(data["end"]["utc"])

            # Venue info
            venue = data.get("venue")
            venue_name = None
            address = None
            lat = None
            lon = None

            if venue:
                venue_name = venue.get("name")
                addr = venue.get("address", {})
                address = f"{addr.get('address_1', '')}, {addr.get('city', '')}, {addr.get('postal_code', '')}"
                lat = float(venue.get("latitude", 0)) or None
                lon = float(venue.get("longitude", 0)) or None

            # Pricing
            price_min = None
            price_max = None
            currency = "GBP"

            if data.get("is_free"):
                price_min = 0.0
                price_max = 0.0
            elif "ticket_availability" in data:
                # Try to get pricing from ticket classes
                pass  # Eventbrite doesn't always provide price in search results

            # Availability
            tickets_available = None
            total_tickets = None
            on_sale_status = None

            if "ticket_availability" in data:
                avail = data["ticket_availability"]
                on_sale_status = "onsale" if avail.get("is_sold_out") == False else "offsale"
                if avail.get("is_sold_out"):
                    tickets_available = 0

            # Images
            image_url = data.get("logo", {}).get("url")

            # Categories
            categories = []
            if "category" in data and data["category"]:
                cat_name = data["category"].get("name", "")
                if cat_name:
                    categories.append(self.transform_category(cat_name))

            return EventData(
                title=title,
                description=description,
                start_date=start_date,
                end_date=end_date,
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
                on_sale_status=on_sale_status,
                tickets_available=tickets_available,
                total_tickets=total_tickets,
                image_url=image_url,
                categories=categories,
                raw_data=data,
            )

        except Exception as e:
            logger.error(f"Error parsing Eventbrite event: {e}")
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
        return 0.5

    def transform_category(self, source_category: str) -> str:
        """Map Eventbrite categories to standardized ones."""
        category_map = {
            "music": "music",
            "business & professional": "business",
            "food & drink": "food",
            "community & culture": "community",
            "performing & visual arts": "arts",
            "film, media & entertainment": "entertainment",
            "sports & fitness": "sports",
            "health & wellness": "wellness",
            "science & technology": "tech",
            "travel & outdoor": "outdoor",
            "charity & causes": "charity",
            "religion & spirituality": "spirituality",
            "family & education": "family",
            "seasonal & holiday": "holiday",
            "government & politics": "politics",
            "fashion & beauty": "fashion",
            "home & lifestyle": "lifestyle",
            "auto, boat & air": "automotive",
            "hobbies & special interest": "hobbies",
            "other": "other",
        }
        return category_map.get(source_category.lower(), "other")
