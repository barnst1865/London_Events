"""Events API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List
from datetime import datetime, timedelta

from ..database import get_db
from ..models.database import Event, Category, EventStatus, event_categories
from ..models import schemas
from ..services.event_aggregator import EventAggregator

router = APIRouter()


@router.get("/", response_model=schemas.EventList)
async def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    start_date_min: Optional[datetime] = None,
    start_date_max: Optional[datetime] = None,
    status: Optional[str] = None,
    price_max: Optional[float] = None,
    search: Optional[str] = None,
    selling_fast_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get list of events with filtering and pagination.

    Args:
        page: Page number
        page_size: Items per page
        category: Filter by category slug
        start_date_min: Minimum start date
        start_date_max: Maximum start date
        status: Filter by status
        price_max: Maximum price
        search: Search in title and description
        selling_fast_only: Only show selling fast events
    """
    query = db.query(Event)

    # Default to future events
    if not start_date_min:
        start_date_min = datetime.utcnow()
    query = query.filter(Event.start_date >= start_date_min)

    # Apply filters
    if start_date_max:
        query = query.filter(Event.start_date <= start_date_max)

    if category:
        query = query.join(Event.categories).filter(Category.slug == category)

    if status:
        try:
            status_enum = EventStatus[status.upper()]
            query = query.filter(Event.status == status_enum)
        except KeyError:
            pass

    if price_max is not None:
        query = query.filter(
            or_(
                Event.price_min <= price_max,
                Event.price_min.is_(None)
            )
        )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Event.title.ilike(search_term),
                Event.description.ilike(search_term),
                Event.venue_name.ilike(search_term)
            )
        )

    if selling_fast_only:
        query = query.filter(Event.status == EventStatus.SELLING_FAST)

    # Get total count
    total = query.count()

    # Paginate
    offset = (page - 1) * page_size
    events = query.order_by(Event.start_date.asc()).offset(offset).limit(page_size).all()

    return {
        "events": events,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (offset + page_size) < total
    }


@router.get("/featured", response_model=List[schemas.Event])
async def list_featured_events(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get featured events."""
    events = db.query(Event).filter(
        and_(
            Event.is_featured == True,
            Event.start_date >= datetime.utcnow()
        )
    ).order_by(Event.start_date.asc()).limit(limit).all()

    return events


@router.get("/selling-fast", response_model=List[schemas.Event])
async def list_selling_fast_events(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get events that are selling fast."""
    events = db.query(Event).filter(
        and_(
            Event.status == EventStatus.SELLING_FAST,
            Event.start_date >= datetime.utcnow()
        )
    ).order_by(Event.availability_percentage.asc()).limit(limit).all()

    return events


@router.get("/on-sale-soon", response_model=List[schemas.Event])
async def list_on_sale_soon_events(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get events going on sale soon."""
    now = datetime.utcnow()
    max_date = now + timedelta(days=days)

    events = db.query(Event).filter(
        and_(
            Event.on_sale_date.isnot(None),
            Event.on_sale_date >= now,
            Event.on_sale_date <= max_date
        )
    ).order_by(Event.on_sale_date.asc()).limit(limit).all()

    return events


@router.get("/sampler", response_model=List[schemas.Event])
async def get_sampler_events(
    db: Session = Depends(get_db)
):
    """
    Get sampler events for free preview.
    Returns a curated selection of events.
    """
    from ..config import settings

    # Get a mix of events: featured, selling fast, and upcoming
    featured = db.query(Event).filter(
        and_(
            Event.is_featured == True,
            Event.start_date >= datetime.utcnow()
        )
    ).limit(2).all()

    selling_fast = db.query(Event).filter(
        and_(
            Event.status == EventStatus.SELLING_FAST,
            Event.start_date >= datetime.utcnow()
        )
    ).limit(2).all()

    upcoming = db.query(Event).filter(
        Event.start_date >= datetime.utcnow()
    ).order_by(Event.start_date.asc()).limit(
        settings.free_events_limit - len(featured) - len(selling_fast)
    ).all()

    # Combine and deduplicate
    event_ids = set()
    sampler = []

    for event_list in [featured, selling_fast, upcoming]:
        for event in event_list:
            if event.id not in event_ids:
                event_ids.add(event.id)
                sampler.append(event)

    return sampler[:settings.free_events_limit]


@router.get("/{event_id}", response_model=schemas.Event)
async def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get single event by ID."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/fetch", status_code=202)
async def fetch_events(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sources: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """
    Trigger event fetching from data sources.
    Admin endpoint - should be protected in production.
    """
    if not start_date:
        start_date = datetime.utcnow()
    if not end_date:
        # Default to next 90 days
        end_date = start_date + timedelta(days=90)

    aggregator = EventAggregator(db)
    results = aggregator.fetch_all_events(start_date, end_date, force_sources=sources)

    return {
        "status": "completed",
        "start_date": start_date,
        "end_date": end_date,
        "results": results
    }


@router.get("/categories/", response_model=List[schemas.Category])
async def list_categories(db: Session = Depends(get_db)):
    """Get all event categories."""
    categories = db.query(Category).order_by(Category.name).all()
    return categories
