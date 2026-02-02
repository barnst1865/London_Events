"""Pydantic schemas for API validation."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


# Enums
class EventStatusSchema(str, Enum):
    UPCOMING = "upcoming"
    ON_SALE = "on_sale"
    SELLING_FAST = "selling_fast"
    SOLD_OUT = "sold_out"
    CANCELLED = "cancelled"


# Category Schemas
class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Event Schemas
class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    ticket_url: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None


class EventCreate(EventBase):
    source_name: str
    source_id: str
    source_url: Optional[str] = None
    on_sale_date: Optional[datetime] = None
    image_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Event(EventBase):
    id: int
    slug: Optional[str]
    status: EventStatusSchema
    on_sale_date: Optional[datetime]
    on_sale_status: Optional[str]
    tickets_available: Optional[int]
    availability_percentage: Optional[float]
    source_name: str
    image_url: Optional[str]
    categories: List[Category] = []
    is_featured: bool
    popularity_score: float
    first_seen_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventList(BaseModel):
    """Paginated event list response."""
    events: List[Event]
    total: int
    page: int
    page_size: int
    has_more: bool


# Data Source Schemas
class DataSourceBase(BaseModel):
    name: str
    source_type: str
    is_enabled: bool = True


class DataSource(DataSourceBase):
    id: int
    last_successful_fetch: Optional[datetime]
    last_fetch_attempt: Optional[datetime]
    last_error: Optional[str]
    events_fetched_count: int
    success_rate: float
    created_at: datetime

    class Config:
        from_attributes = True


# Event Filter Schemas
class EventFilters(BaseModel):
    """Query filters for events."""
    category: Optional[str] = None
    start_date_min: Optional[datetime] = None
    start_date_max: Optional[datetime] = None
    status: Optional[EventStatusSchema] = None
    price_max: Optional[float] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
