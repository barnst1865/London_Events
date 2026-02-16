"""SQLAlchemy database models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean,
    Text, Float, ForeignKey, Table, JSON, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class EventStatus(str, enum.Enum):
    """Event status."""
    UPCOMING = "upcoming"
    ON_SALE = "on_sale"
    SELLING_FAST = "selling_fast"
    SOLD_OUT = "sold_out"
    CANCELLED = "cancelled"


# Association table for event categories
event_categories = Table(
    'event_categories',
    Base.metadata,
    Column('event_id', Integer, ForeignKey('events.id')),
    Column('category_id', Integer, ForeignKey('categories.id'))
)


class Category(Base):
    """Event category model."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    icon = Column(String(50))  # Icon class or emoji
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    events = relationship("Event", secondary=event_categories, back_populates="categories")


class Event(Base):
    """Event model."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    # Basic Info
    title = Column(String(500), nullable=False)
    description = Column(Text)
    slug = Column(String(500), index=True)

    # Date & Time
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime)
    timezone = Column(String(50), default="Europe/London")

    # Location
    venue_name = Column(String(255))
    venue_address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)

    # Ticketing
    ticket_url = Column(String(1000))
    price_min = Column(Float)
    price_max = Column(Float)
    currency = Column(String(3), default="GBP")
    on_sale_date = Column(DateTime, index=True)
    on_sale_status = Column(String(50))  # onsale, offsale, presale

    # Availability
    status = Column(SQLEnum(EventStatus), default=EventStatus.UPCOMING)
    tickets_available = Column(Integer)
    total_tickets = Column(Integer)
    availability_percentage = Column(Float)
    last_availability_check = Column(DateTime)

    # Status tracking
    previous_status = Column(SQLEnum(EventStatus))

    # Source Tracking
    source_name = Column(String(100), nullable=False, index=True)
    source_id = Column(String(255), nullable=False)
    source_url = Column(String(1000))
    raw_data = Column(JSON)  # Store original API response

    # Media
    image_url = Column(String(1000))
    images = Column(JSON)  # Multiple images

    # Metadata
    is_featured = Column(Boolean, default=False)
    popularity_score = Column(Float, default=0.0)
    first_seen_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    categories = relationship("Category", secondary=event_categories, back_populates="events")


class AvailabilityHistory(Base):
    """Tracks status changes for sellout monitoring."""
    __tablename__ = "availability_history"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    previous_status = Column(SQLEnum(EventStatus))
    new_status = Column(SQLEnum(EventStatus), nullable=False)
    tickets_available = Column(Integer)
    total_tickets = Column(Integer)
    availability_percentage = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    event = relationship("Event")


class DataSource(Base):
    """Data source tracking for monitoring and health checks."""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    source_type = Column(String(50), nullable=False)  # api, scraper
    is_enabled = Column(Boolean, default=True)
    last_successful_fetch = Column(DateTime)
    last_fetch_attempt = Column(DateTime)
    last_error = Column(Text)
    events_fetched_count = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)
    average_fetch_time = Column(Float)  # Seconds
    source_metadata = Column("metadata", JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
