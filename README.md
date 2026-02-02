# London Events Report

An event aggregation engine that powers a Substack newsletter for London. Collects events from multiple APIs and venue websites, deduplicates them, tracks ticket availability, and generates AI-curated Substack-ready HTML content.

**Publishing model:** Weekly main edition + ad-hoc "selling fast" alert posts, published via Substack. Substack handles subscribers, payments, email delivery, and the landing page. This app handles the hard part — sourcing, deduplicating, and curating events at scale.

## Features

- **Multi-Source Event Aggregation**: Ticketmaster, Eventbrite, SeatGeek APIs + venue website scrapers
- **Intelligent Deduplication**: Fuzzy matching across sources (title + venue similarity)
- **Sellout Detection**: Tracks ticket availability, flags selling-fast events, projects sellout timelines
- **AI-Powered Curation**: Claude selects editor's picks, writes editorial notes, generates section intros
- **Substack-Ready Output**: HTML with `<!-- PAYWALL -->` marker for free/paid content split
- **CLI-First Workflow**: `generate_newsletter.py` and `generate_alert.py` produce ready-to-paste content
- **REST API**: FastAPI endpoints for event browsing and data management
- **Expandable Architecture**: Plugin-based data source system — add new sources in one file

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL
- Docker & Docker Compose (optional)

### Installation

```bash
git clone https://github.com/barnst1865/London_Events.git
cd London_Events

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your DATABASE_URL and API keys
```

### Database Setup

```bash
# Create PostgreSQL database
createdb london_events

# Initialize schema and seed categories
python -c "from app.database import init_db; init_db()"
python seed_data.py
```

### Docker Setup

```bash
docker-compose up -d
docker-compose run --rm migrate
```

## Usage

### 1. Fetch Events

```bash
# Via CLI
python manage.py fetch                          # All sources, next 90 days
python manage.py fetch --days 60 --sources ticketmaster,eventbrite

# Via API
curl -X POST http://localhost:8000/api/events/fetch
```

### 2. Generate Weekly Newsletter

```bash
python generate_newsletter.py
# -> output/newsletter_2026-02-02.html
```

Open the HTML in a browser to preview, then paste into Substack's editor. Set the paywall at the `<!-- PAYWALL -->` marker.

### 3. Generate Selling-Fast Alert

```bash
python generate_alert.py
# -> output/alert_2026-02-02.html
```

Short-form post for ad-hoc Substack publishing when events cross the selling-fast threshold.

### 4. Browse Events via API

```bash
# Interactive docs
open http://localhost:8000/docs

# Endpoints
curl http://localhost:8000/api/events/
curl http://localhost:8000/api/events/selling-fast
curl http://localhost:8000/api/events/featured
curl http://localhost:8000/api/events/on-sale-soon
curl http://localhost:8000/api/sources
```

## Newsletter Structure

The generated HTML has two sections separated by a `<!-- PAYWALL -->` comment:

**Free section** (above paywall):
- Editor's Picks — 3-5 AI-curated highlights with editorial notes
- Selling Fast — events running low on tickets

**Paid section** (below paywall):
- Just Announced — events first seen in the last 7 days
- Full listings by category (Music, Theatre, Comedy, etc.)
- Price-tiered sections (Free Events, Under £20, Premium)

## API Keys

### Event Data Sources (Optional — enable what you have)

| Source | Sign Up | Env Var |
|--------|---------|---------|
| Ticketmaster | https://developer.ticketmaster.com/ | `TICKETMASTER_API_KEY` |
| Eventbrite | https://www.eventbrite.com/platform/ | `EVENTBRITE_API_KEY` |
| SeatGeek | https://platform.seatgeek.com/ | `SEATGEEK_CLIENT_ID` |

Venue scrapers (Time Out London, O2 Arena, Royal Albert Hall, Barbican, Southbank Centre) run without API keys.

### AI Curation (Optional)

| Service | Env Var | Notes |
|---------|---------|-------|
| Anthropic | `ANTHROPIC_API_KEY` | Powers editor's picks and editorial notes. Falls back to deterministic scoring without it. |

## Adding New Data Sources

Create a class inheriting from `BaseDataSource`:

```python
# app/data_sources/newsource.py
from .base import BaseDataSource, EventData
from datetime import datetime
from typing import List

class NewSource(BaseDataSource):
    @property
    def name(self) -> str:
        return "new_source"

    @property
    def source_type(self) -> str:
        return "api"  # or "scraper"

    def fetch_events(self, start_date: datetime, end_date: datetime) -> List[EventData]:
        # Your implementation here
        return events

    def is_enabled(self) -> bool:
        return bool(os.getenv("NEW_SOURCE_API_KEY"))
```

Register in `app/data_sources/__init__.py`:

```python
DATA_SOURCES = [
    TicketmasterSource,
    EventbriteSource,
    SeatGeekSource,
    NewSource,  # Add here
    # ...scrapers
]
```

The aggregator will automatically fetch from it and handle deduplication.

## Architecture

```
generate_newsletter.py / generate_alert.py    # CLI entry points
    |
    v
app/services/content_generator.py             # Builds Substack HTML
    |
    +-- app/services/ai_curator.py            # Anthropic API editorial curation
    +-- app/services/sellout_detector.py      # Ticket availability analysis
    |
app/services/event_aggregator.py              # Fetches + deduplicates events
    |
    +-- app/data_sources/                     # Plugin-based sources
        +-- ticketmaster.py, eventbrite.py, seatgeek.py
        +-- scrapers/ (timeout_london, o2_arena, royal_albert_hall, barbican, southbank_centre)
    |
app/models/database.py                        # SQLAlchemy ORM (events, categories, data_sources)
```

### Scheduling

The FastAPI app runs two APScheduler cron jobs:
- **Daily event refresh** at 3 AM — fetches from all sources for next 90 days
- **Weekly generation reminder** — logs a prompt to run `generate_newsletter.py`

Newsletter generation itself is manual (CLI-driven) so you control when to publish.

## Database

PostgreSQL with SQLAlchemy ORM. Tables: `events`, `categories`, `event_categories`, `data_sources`.

Schema created via `Base.metadata.create_all()` — no Alembic migrations.

## Environment Variables

See `.env.example` for all options. Only `DATABASE_URL` is required.

## Development

```bash
# Run dev server
uvicorn app.main:app --reload

# Tests
pytest

# Formatting & linting
black .
flake8

# View data source status
python manage.py sources

# View stats
python manage.py stats
```

## Roadmap

- [ ] Fix existing scrapers for reliable date parsing (Phase 2)
- [ ] West End / theatre coverage via Official London Theatre (Phase 3)
- [ ] Large venue scrapers — Alexandra Palace, Roundhouse, KOKO, etc. (Phase 3)
- [ ] DICE and Resident Advisor integration for indie/electronic scenes (Phase 4)
- [ ] Automated selling-fast alert generation (Phase 5)
- [ ] Test suite — deduplication, sellout detection, content generation, scrapers (Phase 6)

---

Built for London event lovers. Data from Ticketmaster, Eventbrite, SeatGeek, and London venue websites.
