# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

London Events Report is an **event aggregation + AI-curated content generation engine** that powers a Substack newsletter. It aggregates events from multiple London sources (APIs + web scrapers), deduplicates them, tracks ticket availability, and generates Substack-ready HTML content with AI-powered editorial curation. Substack handles subscribers, payments, email delivery, and the landing page.

**Publishing cadence:** Weekly main edition + ad-hoc "selling fast" alert posts.

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

# Fetch events
python manage.py fetch
python manage.py fetch --days 60 --sources ticketmaster,eventbrite

# Generate weekly newsletter
python generate_newsletter.py      # -> output/newsletter_YYYY-MM-DD.html

# Generate selling-fast alert
python generate_alert.py           # -> output/alert_YYYY-MM-DD.html

# Trigger event fetch via API
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

### AI Curation

`app/services/ai_curator.py` uses the Anthropic API (Claude) during content generation (not during event fetching) to:
- Select editor's picks based on uniqueness, venue prestige, sellout velocity
- Generate editorial descriptions ("why this matters")
- Write section intros with seasonal/topical awareness

Falls back to deterministic scoring when no API key is configured.

### Content Generation

`app/services/content_generator.py` produces Substack-compatible HTML with:
- **Free section** (above `<!-- PAYWALL -->` marker): Editor's Picks, Selling Fast alerts
- **Paid section** (below paywall): Just Announced, full listings by category, price-tiered sections

### CLI-First Interface

- `generate_newsletter.py` — weekly edition (query DB → AI curation → HTML → `output/`)
- `generate_alert.py` — ad-hoc selling-fast alerts
- `manage.py` — DB init, event fetching, source listing, stats

### Automated Scheduling

`app/scheduler.py` runs APScheduler cron jobs:
- Daily event data refresh at 3 AM (next 90 days)
- Weekly generation reminder (configurable day/time)

Newsletter generation is triggered manually via CLI.

### Key Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| API routes | `app/api/events.py` | FastAPI endpoints (events, categories) |
| Data sources | `app/data_sources/` | Plugin-based event fetching |
| Services | `app/services/` | Aggregation, sellout detection, AI curation, content generation |
| Models | `app/models/database.py` | SQLAlchemy ORM (events, categories, event_categories, data_sources) |
| Schemas | `app/models/schemas.py` | Pydantic request/response validation |
| Config | `app/config.py` | Pydantic-settings from env vars |
| DB setup | `app/database.py` | SQLAlchemy engine & session factory |
| Entry point | `app/main.py` | FastAPI app init, middleware, route mounting |
| CLI | `generate_newsletter.py`, `generate_alert.py`, `manage.py` | Content generation and management |

### Database

PostgreSQL with SQLAlchemy ORM. No Alembic migrations — schema created via `Base.metadata.create_all()`. Tables: events, categories, event_categories, data_sources.

## Environment

Copy `.env.example` to `.env`. Required: `DATABASE_URL`. Optional: API keys for Ticketmaster/Eventbrite/SeatGeek enable their respective sources. `ANTHROPIC_API_KEY` enables AI-powered curation (falls back to deterministic selection without it).
