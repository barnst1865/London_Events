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


class SubscriptionTier(str, enum.Enum):
    """Subscription tier levels."""
    FREE = "free"
    MONTHLY = "monthly"
    ANNUAL = "annual"


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


class User(Base):
    """User model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)


class Subscription(Base):
    """User subscription model."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    stripe_customer_id = Column(String(255), unique=True)
    stripe_subscription_id = Column(String(255), unique=True)
    status = Column(String(50), default="active")  # active, cancelled, past_due
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscription")


class UserPreferences(Base):
    """User event preferences."""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    preferred_categories = Column(JSON)  # List of category IDs
    exclude_sold_out = Column(Boolean, default=False)
    notify_on_sale = Column(Boolean, default=True)
    newsletter_frequency = Column(String(20), default="monthly")  # monthly, weekly
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="preferences")


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
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    categories = relationship("Category", secondary=event_categories, back_populates="events")

    # Unique constraint on source
    __table_args__ = (
        # Ensure we don't duplicate events from the same source
        # UniqueConstraint('source_name', 'source_id', name='uix_source_event'),
    )


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
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Newsletter(Base):
    """Newsletter generation tracking."""
    __tablename__ = "newsletters"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    generation_date = Column(DateTime, nullable=False)
    events_count = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    open_rate = Column(Float)
    click_rate = Column(Float)
    status = Column(String(50), default="draft")  # draft, sending, sent
    html_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # One newsletter per month
        # UniqueConstraint('month', 'year', name='uix_newsletter_month'),
    )
