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
python generate_alert.py           # -> output/alert_YYYY-MM-DD.html (manual)
python generate_alert.py --auto    # scheduler mode: exit 0 = alert generated

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
**Scrapers:** Time Out London, O2 Arena, Royal Albert Hall, Barbican, Southbank Centre, Official London Theatre, KOKO, Roundhouse, Alexandra Palace, Eventim Apollo, DICE, Resident Advisor (in `app/data_sources/scrapers/`). Scrapers extend `BaseScraper` (`app/data_sources/scrapers/base_scraper.py`).

### Event Aggregation & Deduplication

`app/services/event_aggregator.py` fetches from all enabled sources and performs fuzzy duplicate detection using `difflib.SequenceMatcher` (>85% title similarity + >75% venue similarity = duplicate).

### Sellout Detection & Monitoring

`app/services/sellout_detector.py` analyzes ticket availability with thresholds: SOLD_OUT (0 tickets), SELLING_FAST (<10% or <50 tickets remaining), ON_SALE, UPCOMING, CANCELLED. Includes rate-of-sale projections.

`app/services/sellout_monitor.py` checks `availability_history` for recent status transitions and generates alerts when thresholds are met. Runs automatically at 3:30 AM via scheduler.

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
- Sellout alert monitoring at 3:30 AM (checks for status changes, generates alert if thresholds met)
- Weekly generation reminder (configurable day/time)

Newsletter generation is triggered manually via CLI.

### Key Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| API routes | `app/api/events.py` | FastAPI endpoints (events, categories) |
| Data sources | `app/data_sources/` | Plugin-based event fetching |
| Services | `app/services/` | Aggregation, sellout detection, sellout monitoring, AI curation, content generation |
| Models | `app/models/database.py` | SQLAlchemy ORM (events, categories, event_categories, data_sources, availability_history) |
| Schemas | `app/models/schemas.py` | Pydantic request/response validation |
| Config | `app/config.py` | Pydantic-settings from env vars |
| DB setup | `app/database.py` | SQLAlchemy engine & session factory |
| Entry point | `app/main.py` | FastAPI app init, middleware, route mounting |
| CLI | `generate_newsletter.py`, `generate_alert.py`, `manage.py` | Content generation and management |

### Database

PostgreSQL with SQLAlchemy ORM. No Alembic migrations — schema created via `Base.metadata.create_all()`. Tables: events, categories, event_categories, data_sources, availability_history.

## Environment

Copy `.env.example` to `.env`. Required: `DATABASE_URL`. Optional: API keys for Ticketmaster/Eventbrite/SeatGeek enable their respective sources. `ANTHROPIC_API_KEY` enables AI-powered curation (falls back to deterministic selection without it).

## Implementation Status

The project is being restructured from a self-hosted newsletter service into a Substack-focused event aggregation engine. Work is tracked in phases:

### Phase 1: Strip Infrastructure + Build Core Pipeline — DONE
Removed auth, payments, email delivery, subscription infrastructure (~1,100 lines deleted). Added AI curator, content generator, and CLI entry points (~700 lines added). The app now produces Substack-ready HTML via `generate_newsletter.py` and `generate_alert.py`.

### Phase 2: Fix Existing Scrapers — DONE
All 5 scrapers validated against live sites. Eliminated all `datetime.now()` fallbacks, bare `except:` clauses, and guessed CSS selectors. Scrapers now skip events they can't parse cleanly instead of inserting garbage data.

- **O2 Arena** (`o2_arena.py`): Fully working. Uses real selectors (`div.eventItem`, `m-date__day/month/year` spans). Parses dates from O2's structured date spans. Skips Vue.js template items. Returns ~22 events per scrape.
- **Barbican** (`barbican.py`): Fully working. Uses real selectors (`div.search-listing--event`, `h2.listing-title`). Fetches detail pages to extract dates from `<time datetime="">` elements since listing page lacks dates. Returns ~5-15 events per scrape.
- **Time Out London** (`timeout_london.py`): Disabled (`is_enabled=False`). Site serves editorial listicles, not structured event listings — no dates, venues, or prices available on listing pages.
- **Royal Albert Hall** (`royal_albert_hall.py`): Disabled (`is_enabled=False`). Cloudflare "Pardon Our Interruption" blocks all httpx requests.
- **Southbank Centre** (`southbank_centre.py`): Disabled (`is_enabled=False`). Cloudflare 403 blocks all httpx requests.

The 3 disabled scrapers need headless browser support (Phase 4 consideration) or alternative data sources.

### Phase 3: Expand Data Sources — West End & Large Venues — DONE
Added 5 new scrapers covering West End theatre and major London venues.

- **Official London Theatre** (`official_london_theatre.py`): Fully working. Uses WordPress REST API (`/wp-json/wp/v2/show`) — structured JSON, no HTML parsing. Caches venue name lookups. Maps genre taxonomy to categories. Returns ~164 West End shows.
- **KOKO** (`koko.py`): Fully working. Parses `<script id="__NEXT_DATA__">` JSON from Next.js app (CSS classes are Emotion-hashed, unusable). Extracts events from `props.pageProps.data.events.nodes[]`. Returns ~70+ events.
- **Roundhouse** (`roundhouse.py`): Fully working. Server-rendered HTML with `.event-card` selectors. Parses date ranges from `.event-card__date` text. Returns ~20-40 events.
- **Alexandra Palace** (`alexandra_palace.py`): Fully working. Server-rendered HTML with `.event_card` selectors (underscore). Parses dates from `.date-panel` elements. Returns ~20-40 events.
- **Eventim Apollo** (`eventim_apollo.py`): Fully working. Server-rendered HTML with `.card` selectors. Parses dates from `.date` elements. Returns ~20-40 events.
- **Brixton Academy**: Skipped — React SPA needs headless browser, events already covered by Ticketmaster API.

### Phase 4: Expand Data Sources — DICE & Resident Advisor — DONE
Added 2 new sources covering indie/alternative and electronic/club scenes.

- **DICE** (`dice.py`): Fully working. Next.js app — extracts `__NEXT_DATA__` JSON from category pages (same pattern as KOKO). Iterates 9 category URLs (music/gig, music/dj, music/party, culture/comedy, etc.), deduplicates by event ID across categories. Parses `date_unix` timestamps, prices in pence, sold-out status. Returns ~200 events per scrape.
- **Resident Advisor** (`resident_advisor.py`): Fully working. Uses open GraphQL API at `ra.co/graphql` (no auth). Introspects Event type on first call to discover `startTime` field dynamically. Queries POPULAR, TODAY, and PICKS event types. Parses ISO 8601 dates, `£` prices from cost strings, venue names/addresses. Returns ~50 events per scrape. Will self-disable if introspection fails to find a date field.

### Phase 5: Sellout Alert System — DONE
Automated availability monitoring with status change tracking, threshold-based alert flagging, and scheduler-triggered alert generation.

- **AvailabilityHistory table** (`database.py`): Tracks every status transition (previous_status → new_status) with timestamps, ticket counts, and availability percentages. `Event.previous_status` column added for quick lookups.
- **Status update fix** (`event_aggregator.py`): `_update_event()` now always recalculates status — covers both ticket-count and `on_sale_status` paths. Previously, scrapers providing only `on_sale_status` (DICE, O2, KOKO, etc.) never got status updates on re-fetch. Status changes are recorded in `availability_history`.
- **Sellout detector fix** (`sellout_detector.py`): Now recognizes `"sold_out"` and `"sold-out"` strings alongside `"soldout"`.
- **SelloutMonitor** (`sellout_monitor.py`): New service that queries `availability_history` for recent transitions, groups into newly-selling-fast and newly-sold-out, and generates alerts when thresholds are met (configurable: ≥1 selling-fast OR ≥3 sold-out).
- **Scheduler integration** (`scheduler.py`): Sellout monitoring job runs at 3:30 AM daily (30 min after fetch). Configurable via `SELLOUT_MONITOR_ENABLED` env var.
- **Alert CLI** (`generate_alert.py`): Added `--auto` flag for scheduler-triggered runs (exit 0 = alert generated, exit 1 = no alert). Manual mode now includes recently sold-out events alongside selling-fast.

### Phase 6: Tests — TODO
Test suite for deduplication, sellout detection, content generation, AI curator (mocked), and scraper date parsing.
