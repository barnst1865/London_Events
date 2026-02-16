"""Tests for EventAggregator deduplication — uses db_session fixture."""
import pytest
from datetime import datetime

from app.models.database import Event, EventStatus
from app.data_sources.base import EventData
from app.services.event_aggregator import EventAggregator


# --- _similarity ---

class TestSimilarity:
    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.agg = EventAggregator(db_session)

    def test_identical_strings(self):
        assert self.agg._similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert self.agg._similarity("abc", "xyz") < 0.2

    def test_partial_match_above_threshold(self):
        """Slightly different titles should still score > 0.85."""
        sim = self.agg._similarity(
            "taylor swift the eras tour",
            "taylor swift - the eras tour",
        )
        assert sim > 0.85


# --- _find_duplicate ---

class TestFindDuplicate:
    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.db = db_session
        self.agg = EventAggregator(db_session)

    def _add_event(self, title="Test Event", venue="Test Venue", date=None):
        if date is None:
            date = datetime(2026, 3, 15, 19, 30)
        event = Event(
            title=title,
            start_date=date,
            venue_name=venue,
            source_name="existing",
            source_id="exist-1",
            slug="exist-1",
        )
        self.db.add(event)
        self.db.commit()
        return event

    def _make_event_data(self, title="Test Event", venue="Test Venue", date=None):
        if date is None:
            date = datetime(2026, 3, 15, 19, 30)
        return EventData(
            title=title,
            start_date=date,
            source_name="new_source",
            source_id="new-1",
            venue_name=venue,
        )

    def test_exact_match_found(self):
        self._add_event("Taylor Swift Eras Tour", "Wembley Stadium")
        ed = self._make_event_data("Taylor Swift Eras Tour", "Wembley Stadium")
        assert self.agg._find_duplicate(ed) is not None

    def test_fuzzy_title_match_found(self):
        self._add_event("Taylor Swift - The Eras Tour", "Wembley Stadium")
        ed = self._make_event_data("Taylor Swift: The Eras Tour", "Wembley Stadium")
        assert self.agg._find_duplicate(ed) is not None

    def test_different_title_not_found(self):
        self._add_event("Taylor Swift Eras Tour", "Wembley Stadium")
        ed = self._make_event_data("Adele World Tour", "Wembley Stadium")
        assert self.agg._find_duplicate(ed) is None

    def test_different_date_not_found(self):
        self._add_event("Taylor Swift Eras Tour", "Wembley Stadium", datetime(2026, 3, 15))
        ed = self._make_event_data("Taylor Swift Eras Tour", "Wembley Stadium", datetime(2026, 4, 15))
        assert self.agg._find_duplicate(ed) is None

    def test_similar_title_different_venue_not_found(self):
        self._add_event("Jazz Night", "Ronnie Scotts")
        ed = self._make_event_data("Jazz Night", "Royal Albert Hall")
        assert self.agg._find_duplicate(ed) is None

    def test_both_venues_none_duplicate_found(self):
        """Both venues None → venue similarity=1.0 so duplicate found."""
        self._add_event("Same Event", venue=None)
        ed = self._make_event_data("Same Event", venue=None)
        assert self.agg._find_duplicate(ed) is not None


# --- _calculate_availability_percentage ---

class TestCalculateAvailabilityPercentage:
    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.agg = EventAggregator(db_session)

    def test_normal(self):
        result = self.agg._calculate_availability_percentage(200, 1000)
        assert result == pytest.approx(20.0)

    def test_none_tickets_returns_none(self):
        assert self.agg._calculate_availability_percentage(None, 1000) is None

    def test_none_total_returns_none(self):
        assert self.agg._calculate_availability_percentage(200, None) is None

    def test_zero_total_returns_none(self):
        assert self.agg._calculate_availability_percentage(200, 0) is None

    def test_zero_available_returns_none(self):
        """0 is falsy, so `not tickets_available` is True → returns None."""
        assert self.agg._calculate_availability_percentage(0, 1000) is None
