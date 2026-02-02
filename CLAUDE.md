# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

London Events Report is a subscription-based FastAPI service that aggregates events from multiple London sources (APIs + web scrapers), deduplicates them, tracks ticket availability, and delivers automated newsletters with a freemium subscription model.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
uvicorn app.main:app --reload

# Run with Docker
docker-compose up -d
docker-compose run --rm migrate    # first-time DB setup

# Seed event categories
python seed_data.py

# Init DB schema directly
python -c "from app.database import init_db; init_db()"

# Trigger event fetch manually
curl -X POST http://localhost:8000/api/events/fetch

# Tests
pytest

# Formatting & linting
black .
flake8
```

## Architecture

### Plugin-Based Data Source System

All event data sources inherit from `BaseDataSource` (`app/data_sources/base.py`) and must implement `name`, `source_type`, `fetch_events()`, and `is_enabled()`. Sources return standardized `EventData` objects. New sources are registered in the `DATA_SOURCES` list in `app/data_sources/__init__.py`.

**API sources:** Ticketmaster, Eventbrite, SeatGeek (in `app/data_sources/`)
**Scrapers:** Time Out London, O2 Arena, Royal Albert Hall, Barbican, Southbank Centre (in `app/data_sources/scrapers/`). Scrapers extend `BaseScraper` (`app/data_sources/scrapers/base_scraper.py`).

### Event Aggregation & Deduplication

`app/services/event_aggregator.py` fetches from all enabled sources and performs fuzzy duplicate detection using `difflib.SequenceMatcher` (>85% title similarity + >75% venue similarity = duplicate).

### Sellout Detection

`app/services/sellout_detector.py` analyzes ticket availability with thresholds: SOLD_OUT (0 tickets), SELLING_FAST (<10% or <50 tickets remaining), ON_SALE, UPCOMING, CANCELLED. Includes rate-of-sale projections.

### Subscription Tiers & Payments

Three tiers: FREE (5 events), MONTHLY (£4.99), ANNUAL (£49.99). Stripe handles payment with webhook lifecycle in `app/api/subscriptions.py`.

### Automated Scheduling

`app/scheduler.py` runs two APScheduler cron jobs:
- Monthly newsletter generation & sending (configurable day/time)
- Daily event data refresh at 3 AM (next 90 days)

### Key Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| API routes | `app/api/` | FastAPI endpoints (events, auth, subscriptions) |
| Data sources | `app/data_sources/` | Plugin-based event fetching |
| Services | `app/services/` | Business logic (aggregation, email, sellout detection) |
| Models | `app/models/database.py` | SQLAlchemy ORM (9 tables) |
| Schemas | `app/models/schemas.py` | Pydantic request/response validation |
| Config | `app/config.py` | Pydantic-settings from env vars |
| DB setup | `app/database.py` | SQLAlchemy engine & session factory |
| Entry point | `app/main.py` | FastAPI app init, middleware, route mounting |

### Database

PostgreSQL with SQLAlchemy ORM. No Alembic migrations in use — schema created directly via `Base.metadata.create_all()`. Key tables: users, subscriptions, user_preferences, events, categories, event_categories, data_sources, newsletters.

### Auth Pattern

JWT tokens (7-day expiry) via `python-jose`. Password hashing with bcrypt/passlib. Database sessions injected via FastAPI `Depends(get_db)`.

## Environment

Copy `.env.example` to `.env`. Required: `DATABASE_URL`, `SECRET_KEY`. API keys for Ticketmaster/Eventbrite/SeatGeek enable their respective sources. SendGrid and Stripe keys needed for email and payment features.
