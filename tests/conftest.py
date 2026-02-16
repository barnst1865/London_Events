"""Shared test fixtures."""
import os

# Set env vars BEFORE any app imports so Settings() doesn't fail
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Event, Category, EventStatus


@pytest.fixture
def db_session():
    """In-memory SQLite session. Creates tables, yields session, cleans up."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def make_event():
    """Factory for Event ORM objects with sensible defaults."""
    _counter = 0

    def _make(
        title="Test Event",
        start_date=None,
        venue_name="Test Venue",
        source_name="test_source",
        source_id=None,
        slug=None,
        status=EventStatus.UPCOMING,
        price_min=None,
        price_max=None,
        currency="GBP",
        ticket_url=None,
        tickets_available=None,
        total_tickets=None,
        availability_percentage=None,
        is_featured=False,
        popularity_score=0.0,
        first_seen_at=None,
        **kwargs,
    ):
        nonlocal _counter
        _counter += 1
        if start_date is None:
            start_date = datetime(2026, 3, 15, 19, 30)
        if source_id is None:
            source_id = f"test-{_counter}"
        if slug is None:
            slug = f"test-event-{_counter}"

        return Event(
            id=_counter,
            title=title,
            start_date=start_date,
            venue_name=venue_name,
            source_name=source_name,
            source_id=source_id,
            slug=slug,
            status=status,
            price_min=price_min,
            price_max=price_max,
            currency=currency,
            ticket_url=ticket_url,
            tickets_available=tickets_available,
            total_tickets=total_tickets,
            availability_percentage=availability_percentage,
            is_featured=is_featured,
            popularity_score=popularity_score,
            first_seen_at=first_seen_at,
            **kwargs,
        )

    return _make


@pytest.fixture
def make_category():
    """Factory for Category ORM objects."""
    _counter = 0

    def _make(name="Music", slug=None):
        nonlocal _counter
        _counter += 1
        if slug is None:
            slug = name.lower().replace(" ", "-")
        return Category(id=_counter, name=name, slug=slug)

    return _make
