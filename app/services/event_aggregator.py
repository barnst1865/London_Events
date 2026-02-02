"""Event aggregation service - fetches and deduplicates events from all sources."""
import logging
from typing import List, Dict
from datetime import datetime
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..data_sources import get_enabled_sources
from ..data_sources.base import EventData
from ..models.database import Event, DataSource, EventStatus
from ..config import settings
from .sellout_detector import SelloutDetector

logger = logging.getLogger(__name__)


class EventAggregator:
    """
    Aggregates events from multiple data sources.

    Features:
    - Fetches from all enabled sources
    - Deduplicates events across sources
    - Updates existing events with new data
    - Tracks data source health
    """

    def __init__(self, db: Session):
        self.db = db
        self.sellout_detector = SelloutDetector()

    def fetch_all_events(
        self,
        start_date: datetime,
        end_date: datetime,
        force_sources: List[str] = None
    ) -> Dict[str, int]:
        """
        Fetch events from all enabled data sources.

        Args:
            start_date: Start of date range
            end_date: End of date range
            force_sources: If provided, only fetch from these sources

        Returns:
            Dict with source names and event counts
        """
        sources = get_enabled_sources()

        if force_sources:
            sources = [s for s in sources if s.name in force_sources]

        results = {}

        for source in sources:
            logger.info(f"Fetching from {source.display_name}...")
            try:
                fetch_start = datetime.now()

                # Fetch events from source
                events = source.fetch_events(start_date, end_date)

                fetch_duration = (datetime.now() - fetch_start).total_seconds()

                # Process and save events
                saved_count = self._process_events(events, source.name)

                # Update data source tracking
                self._update_source_tracking(
                    source.name,
                    source.source_type,
                    success=True,
                    events_count=len(events),
                    fetch_duration=fetch_duration
                )

                results[source.name] = saved_count
                logger.info(f"{source.display_name}: Saved {saved_count}/{len(events)} events")

            except Exception as e:
                logger.error(f"Error fetching from {source.display_name}: {e}")
                self._update_source_tracking(
                    source.name,
                    source.source_type,
                    success=False,
                    error=str(e)
                )
                results[source.name] = 0

        return results

    def _process_events(self, events: List[EventData], source_name: str) -> int:
        """
        Process and save events to database.

        Args:
            events: List of EventData objects
            source_name: Name of the source

        Returns:
            Number of events saved
        """
        saved_count = 0

        for event_data in events:
            try:
                # Check if event already exists from this source
                existing = self.db.query(Event).filter(
                    and_(
                        Event.source_name == source_name,
                        Event.source_id == event_data.source_id
                    )
                ).first()

                if existing:
                    # Update existing event
                    self._update_event(existing, event_data)
                else:
                    # Check for duplicate from other sources
                    duplicate = self._find_duplicate(event_data)
                    if duplicate:
                        logger.debug(f"Duplicate event found: {event_data.title}")
                        continue

                    # Create new event
                    self._create_event(event_data)

                saved_count += 1

            except Exception as e:
                logger.error(f"Error processing event {event_data.title}: {e}")
                continue

        self.db.commit()
        return saved_count

    def _create_event(self, event_data: EventData) -> Event:
        """Create new event in database."""
        from slugify import slugify

        # Determine status
        status = self.sellout_detector.determine_status(
            tickets_available=event_data.tickets_available,
            total_tickets=event_data.total_tickets,
            on_sale_status=event_data.on_sale_status
        )

        event = Event(
            title=event_data.title,
            slug=slugify(event_data.title),
            description=event_data.description,
            start_date=event_data.start_date,
            end_date=event_data.end_date,
            venue_name=event_data.venue_name,
            venue_address=event_data.venue_address,
            latitude=event_data.latitude,
            longitude=event_data.longitude,
            ticket_url=event_data.ticket_url,
            price_min=event_data.price_min,
            price_max=event_data.price_max,
            currency=event_data.currency,
            on_sale_date=event_data.on_sale_date,
            on_sale_status=event_data.on_sale_status,
            status=status,
            tickets_available=event_data.tickets_available,
            total_tickets=event_data.total_tickets,
            availability_percentage=self._calculate_availability_percentage(
                event_data.tickets_available,
                event_data.total_tickets
            ),
            last_availability_check=datetime.utcnow(),
            source_name=event_data.source_name,
            source_id=event_data.source_id,
            source_url=event_data.source_url,
            image_url=event_data.image_url,
            images=event_data.images,
            raw_data=event_data.raw_data,
        )

        self.db.add(event)
        return event

    def _update_event(self, event: Event, event_data: EventData):
        """Update existing event with new data."""
        # Update fields that might change
        event.title = event_data.title
        event.description = event_data.description or event.description
        event.start_date = event_data.start_date
        event.end_date = event_data.end_date
        event.venue_name = event_data.venue_name or event.venue_name
        event.venue_address = event_data.venue_address or event.venue_address
        event.ticket_url = event_data.ticket_url or event.ticket_url
        event.price_min = event_data.price_min or event.price_min
        event.price_max = event_data.price_max or event.price_max
        event.on_sale_date = event_data.on_sale_date or event.on_sale_date
        event.on_sale_status = event_data.on_sale_status or event.on_sale_status
        event.image_url = event_data.image_url or event.image_url

        # Update availability data
        if event_data.tickets_available is not None:
            event.tickets_available = event_data.tickets_available
            event.total_tickets = event_data.total_tickets or event.total_tickets
            event.availability_percentage = self._calculate_availability_percentage(
                event_data.tickets_available,
                event.total_tickets
            )
            event.last_availability_check = datetime.utcnow()

            # Update status based on availability
            event.status = self.sellout_detector.determine_status(
                tickets_available=event_data.tickets_available,
                total_tickets=event.total_tickets,
                on_sale_status=event_data.on_sale_status
            )

        event.raw_data = event_data.raw_data
        event.updated_at = datetime.utcnow()

    def _find_duplicate(self, event_data: EventData) -> Event:
        """
        Find duplicate events across different sources.

        Uses fuzzy matching on title, date, and venue to identify duplicates.

        Args:
            event_data: Event to check for duplicates

        Returns:
            Existing event if duplicate found, None otherwise
        """
        # Query events on the same date
        same_date_events = self.db.query(Event).filter(
            Event.start_date == event_data.start_date
        ).all()

        for existing in same_date_events:
            # Check title similarity
            title_similarity = self._similarity(
                event_data.title.lower(),
                existing.title.lower()
            )

            # Check venue similarity if both have venues
            venue_similarity = 1.0
            if event_data.venue_name and existing.venue_name:
                venue_similarity = self._similarity(
                    event_data.venue_name.lower(),
                    existing.venue_name.lower()
                )

            # Consider it a duplicate if both title and venue are very similar
            if title_similarity > 0.85 and venue_similarity > 0.75:
                return existing

        return None

    def _similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two strings."""
        return SequenceMatcher(None, a, b).ratio()

    def _calculate_availability_percentage(
        self,
        tickets_available: int,
        total_tickets: int
    ) -> float:
        """Calculate availability percentage."""
        if not tickets_available or not total_tickets:
            return None
        if total_tickets == 0:
            return 0.0
        return (tickets_available / total_tickets) * 100

    def _update_source_tracking(
        self,
        source_name: str,
        source_type: str,
        success: bool,
        events_count: int = 0,
        fetch_duration: float = 0,
        error: str = None
    ):
        """Update data source tracking."""
        source = self.db.query(DataSource).filter(
            DataSource.name == source_name
        ).first()

        if not source:
            source = DataSource(
                name=source_name,
                source_type=source_type,
                is_enabled=True
            )
            self.db.add(source)

        source.last_fetch_attempt = datetime.utcnow()

        if success:
            source.last_successful_fetch = datetime.utcnow()
            source.events_fetched_count = (source.events_fetched_count or 0) + events_count
            source.last_error = None

            # Update average fetch time
            if source.average_fetch_time:
                source.average_fetch_time = (source.average_fetch_time + fetch_duration) / 2
            else:
                source.average_fetch_time = fetch_duration
        else:
            source.last_error = error

        self.db.commit()
