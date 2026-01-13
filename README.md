# 🎭 London Events Report

A subscription-based service that generates monthly reports of upcoming events in London, including concert, theater, sports, and entertainment events. Features ticket availability tracking, selling-out alerts, and a freemium subscription model.

## ✨ Features

- **Multi-Source Event Aggregation**: Fetches events from Ticketmaster, Eventbrite, SeatGeek, and web scraping
- **Intelligent Deduplication**: Automatically identifies and merges duplicate events across sources
- **Selling-Out Detection**: Tracks ticket availability and alerts users when events are selling fast
- **Monthly Newsletter**: Automated email newsletter sent on the 1st of each month
- **Freemium Model**: Free sampler (5 events) with paid tiers for full access
- **REST API**: Complete API for event browsing and management
- **Expandable Architecture**: Easy to add new data sources

## 🏗️ Architecture

### Expandable Data Source System

The application uses a plugin-based architecture for data sources. To add a new source:

1. Create a class that inherits from `BaseDataSource`
2. Implement the required methods (`name`, `source_type`, `fetch_events`)
3. Add the class to `DATA_SOURCES` in `app/data_sources/__init__.py`

Example:
```python
from app.data_sources.base import BaseDataSource, EventData

class NewSource(BaseDataSource):
    @property
    def name(self) -> str:
        return "new_source"

    @property
    def source_type(self) -> str:
        return "api"  # or "scraper"

    def fetch_events(self, start_date, end_date) -> List[EventData]:
        # Your implementation
        return events
```

### Tech Stack

- **Backend**: Python 3.11, FastAPI
- **Database**: PostgreSQL
- **Email**: SendGrid
- **Payments**: Stripe
- **Scheduling**: APScheduler
- **Deployment**: Docker, Docker Compose

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL
- Docker & Docker Compose (optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/London_Events.git
cd London_Events
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. **Set up database**
```bash
# Create PostgreSQL database
createdb london_events

# Initialize database schema
python -c "from app.database import init_db; init_db()"
```

6. **Run the application**
```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000 to see the landing page!

### Docker Setup (Recommended)

```bash
# Start all services
docker-compose up -d

# Initialize database
docker-compose run --rm migrate

# View logs
docker-compose logs -f app
```

## 🔑 API Keys Setup

You'll need API keys from these services:

### Event Data Sources

1. **Ticketmaster** (Free)
   - Sign up: https://developer.ticketmaster.com/
   - Add to `.env`: `TICKETMASTER_API_KEY=your_key`

2. **Eventbrite** (Free)
   - Sign up: https://www.eventbrite.com/platform/
   - Add to `.env`: `EVENTBRITE_API_KEY=your_key`

3. **SeatGeek** (Free)
   - Sign up: https://platform.seatgeek.com/
   - Add to `.env`: `SEATGEEK_CLIENT_ID=your_client_id`

### Required Services

4. **SendGrid** (Free tier: 100 emails/day)
   - Sign up: https://sendgrid.com/
   - Add to `.env`: `SENDGRID_API_KEY=your_key`

5. **Stripe** (Pay per transaction)
   - Sign up: https://stripe.com/
   - Get test keys from dashboard
   - Add to `.env`: `STRIPE_API_KEY=sk_test_...` and `STRIPE_PUBLISHABLE_KEY=pk_test_...`

## 📋 API Documentation

Once running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

### Key Endpoints

#### Events
- `GET /api/events/` - List all events (with filtering)
- `GET /api/events/{id}` - Get single event
- `GET /api/events/featured` - Get featured events
- `GET /api/events/selling-fast` - Get selling fast events
- `GET /api/events/on-sale-soon` - Get events going on sale soon
- `GET /api/events/sampler` - Get free sampler events
- `POST /api/events/fetch` - Trigger event fetching (admin)

#### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get token
- `GET /api/auth/me` - Get current user info

#### Subscriptions
- `GET /api/subscriptions/plans` - Get subscription plans
- `GET /api/subscriptions/my-subscription` - Get user's subscription
- `POST /api/subscriptions/checkout-session` - Create Stripe checkout
- `POST /api/subscriptions/cancel` - Cancel subscription

## 🔄 Adding New Data Sources

The system is designed to be easily expandable. Here's how to add a new data source:

### API Source Example

```python
# app/data_sources/newsource.py
from .base import BaseDataSource, EventData
from datetime import datetime
from typing import List

class NewAPISource(BaseDataSource):
    @property
    def name(self) -> str:
        return "new_api"

    @property
    def source_type(self) -> str:
        return "api"

    def fetch_events(self, start_date: datetime, end_date: datetime) -> List[EventData]:
        # Fetch from API
        response = requests.get("https://api.example.com/events")
        data = response.json()

        # Transform to EventData
        events = []
        for item in data:
            event = EventData(
                title=item['name'],
                start_date=self._parse_date(item['date']),
                source_name=self.name,
                source_id=item['id'],
                # ... other fields
            )
            events.append(event)

        return events

    def is_enabled(self) -> bool:
        return bool(os.getenv("NEW_API_KEY"))
```

Then add to `app/data_sources/__init__.py`:
```python
from .newsource import NewAPISource

DATA_SOURCES = [
    TicketmasterSource,
    EventbriteSource,
    SeatGeekSource,
    NewAPISource,  # Add here
    TimeOutLondonScraper,
]
```

That's it! The new source will automatically be used by the aggregator.

## 📅 Scheduling

The application includes automated scheduling for:

1. **Monthly Newsletter** (1st of each month at 9 AM London time)
   - Fetches latest events
   - Generates personalized newsletters
   - Sends to all active subscribers

2. **Daily Event Refresh** (3 AM London time)
   - Updates event data
   - Checks ticket availability
   - Updates selling-out status

To start the scheduler:
```python
from app.scheduler import start_scheduler
start_scheduler()
```

Or it will start automatically when running the FastAPI app.

## 🧪 Testing

### Manual Testing

1. **Fetch Events**
```bash
curl -X POST http://localhost:8000/api/events/fetch
```

2. **View Events**
```bash
curl http://localhost:8000/api/events/
```

3. **Get Sampler**
```bash
curl http://localhost:8000/api/events/sampler
```

### Run Tests
```bash
pytest
```

## 🚀 Deployment

### Option 1: Railway (Recommended)

1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Add PostgreSQL: `railway add postgresql`
5. Deploy: `railway up`
6. Set environment variables in Railway dashboard

### Option 2: Render

1. Create new Web Service
2. Connect GitHub repository
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add PostgreSQL database
6. Set environment variables

### Option 3: Docker on VPS

```bash
# On your server
git clone https://github.com/yourusername/London_Events.git
cd London_Events

# Configure environment
cp .env.example .env
nano .env

# Start services
docker-compose up -d

# Set up nginx reverse proxy (optional)
```

## 📊 Database Schema

- **users** - User accounts
- **subscriptions** - Subscription management
- **user_preferences** - User event preferences
- **events** - Event data
- **categories** - Event categories
- **event_categories** - Many-to-many relationship
- **data_sources** - Data source health tracking
- **newsletters** - Newsletter generation history

## 🔐 Security

- Passwords hashed with bcrypt
- JWT tokens for authentication
- Stripe webhook signature verification
- Environment variables for sensitive data
- Non-root Docker user
- SQL injection protection via SQLAlchemy ORM

## 📝 Environment Variables

See `.env.example` for all configuration options.

### Required
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret key (generate with `openssl rand -hex 32`)

### Optional (but recommended)
- `SENDGRID_API_KEY` - For email sending
- `STRIPE_API_KEY` - For payments
- `TICKETMASTER_API_KEY` - For event data
- `EVENTBRITE_API_KEY` - For event data
- `SEATGEEK_CLIENT_ID` - For event data

## 🤝 Contributing

Contributions welcome! To add a new data source:

1. Fork the repository
2. Create your data source class inheriting from `BaseDataSource`
3. Add tests
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Event data from Ticketmaster, Eventbrite, SeatGeek, Time Out London
- Built with FastAPI, SQLAlchemy, and SendGrid

## 📞 Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/London_Events/issues
- Email: support@example.com

## 🗺️ Roadmap

- [ ] Add more data sources (Songkick, Bandsintown)
- [ ] Implement user preferences and filtering
- [ ] Add weekly digest option
- [ ] Mobile app
- [ ] WhatsApp notifications
- [ ] Expand to other UK cities
- [ ] AI-powered event recommendations
- [ ] Social features (sharing, wishlists)

---

Built with ❤️ for London event lovers
