"""Base class for all event data sources."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EventData:
    """
    Standardized event data structure.
    All data sources must return events in this format.
    """

    def __init__(
        self,
        title: str,
        start_date: datetime,
        source_name: str,
        source_id: str,
        description: Optional[str] = None,
        end_date: Optional[datetime] = None,
        venue_name: Optional[str] = None,
        venue_address: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        ticket_url: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        currency: str = "GBP",
        on_sale_date: Optional[datetime] = None,
        on_sale_status: Optional[str] = None,
        tickets_available: Optional[int] = None,
        total_tickets: Optional[int] = None,
        image_url: Optional[str] = None,
        images: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        source_url: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ):
        self.title = title
        self.description = description
        self.start_date = start_date
        self.end_date = end_date
        self.venue_name = venue_name
        self.venue_address = venue_address
        self.latitude = latitude
        self.longitude = longitude
        self.ticket_url = ticket_url
        self.price_min = price_min
        self.price_max = price_max
        self.currency = currency
        self.on_sale_date = on_sale_date
        self.on_sale_status = on_sale_status
        self.tickets_available = tickets_available
        self.total_tickets = total_tickets
        self.image_url = image_url
        self.images = images or []
        self.categories = categories or []
        self.source_name = source_name
        self.source_id = source_id
        self.source_url = source_url
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "title": self.title,
            "description": self.description,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "venue_name": self.venue_name,
            "venue_address": self.venue_address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "ticket_url": self.ticket_url,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "currency": self.currency,
            "on_sale_date": self.on_sale_date,
            "on_sale_status": self.on_sale_status,
            "tickets_available": self.tickets_available,
            "total_tickets": self.total_tickets,
            "image_url": self.image_url,
            "images": self.images,
            "source_name": self.source_name,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "raw_data": self.raw_data,
        }


class BaseDataSource(ABC):
    """
    Abstract base class for all event data sources.

    To add a new data source:
    1. Create a new class that inherits from BaseDataSource
    2. Implement all abstract methods
    3. Add the class to DATA_SOURCES in __init__.py

    Example:
        class NewSource(BaseDataSource):
            @property
            def name(self) -> str:
                return "new_source"

            @property
            def source_type(self) -> str:
                return "api"  # or "scraper"

            def fetch_events(self, start_date, end_date) -> List[EventData]:
                # Implementation
                pass
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this data source.
        Used for tracking and deduplication.
        """
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """
        Type of data source: 'api' or 'scraper'.
        """
        pass

    @property
    def display_name(self) -> str:
        """
        Human-readable name for this data source.
        Defaults to capitalized name.
        """
        return self.name.replace("_", " ").title()

    @abstractmethod
    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[EventData]:
        """
        Fetch events from this data source.

        Args:
            start_date: Start of date range to fetch
            end_date: End of date range to fetch
            **kwargs: Additional source-specific parameters

        Returns:
            List of EventData objects

        Raises:
            Exception: If fetch fails (will be caught and logged by aggregator)
        """
        pass

    def is_enabled(self) -> bool:
        """
        Check if this data source is enabled and configured.
        Override to add custom enable/disable logic.

        Returns:
            True if source should be used, False otherwise
        """
        return True

    def validate_event(self, event: EventData) -> bool:
        """
        Validate that event data meets minimum requirements.
        Override to add source-specific validation.

        Args:
            event: Event to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = [
            event.title,
            event.start_date,
            event.source_name,
            event.source_id,
        ]
        return all(field is not None for field in required_fields)

    def get_rate_limit_delay(self) -> float:
        """
        Get delay between requests in seconds.
        Override for source-specific rate limiting.

        Returns:
            Delay in seconds
        """
        return 0.0

    def transform_category(self, source_category: str) -> str:
        """
        Transform source-specific category to standardized category.
        Override to map categories to your taxonomy.

        Args:
            source_category: Category from the data source

        Returns:
            Standardized category name
        """
        return source_category.lower()

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.__class__.__name__}(name='{self.name}', type='{self.source_type}')>"
