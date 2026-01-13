#!/usr/bin/env python
"""Management CLI for London Events application."""
import click
from datetime import datetime, timedelta
from app.database import SessionLocal, init_db
from app.services.event_aggregator import EventAggregator
from app.services.email_service import EmailService
from app.scheduler import NewsletterScheduler


@click.group()
def cli():
    """London Events Management CLI."""
    pass


@cli.command()
def initdb():
    """Initialize database schema."""
    click.echo("Initializing database...")
    init_db()
    click.echo("✓ Database initialized successfully!")


@cli.command()
@click.option('--days', default=90, help='Number of days ahead to fetch')
@click.option('--sources', help='Comma-separated list of sources (optional)')
def fetch(days, sources):
    """Fetch events from data sources."""
    db = SessionLocal()
    try:
        start_date = datetime.now()
        end_date = start_date + timedelta(days=days)

        source_list = sources.split(',') if sources else None

        click.echo(f"Fetching events from {start_date.date()} to {end_date.date()}...")
        if source_list:
            click.echo(f"Sources: {', '.join(source_list)}")

        aggregator = EventAggregator(db)
        results = aggregator.fetch_all_events(start_date, end_date, force_sources=source_list)

        click.echo("\nResults:")
        for source, count in results.items():
            click.echo(f"  {source}: {count} events")

        total = sum(results.values())
        click.echo(f"\n✓ Total: {total} events fetched")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
    finally:
        db.close()


@cli.command()
def sources():
    """List all data sources and their status."""
    from app.data_sources import get_all_sources

    click.echo("Available Data Sources:\n")
    for source in get_all_sources():
        enabled = "✓" if source.is_enabled() else "✗"
        click.echo(f"{enabled} {source.display_name} ({source.name})")
        click.echo(f"   Type: {source.source_type}")
        click.echo()


@cli.command()
@click.option('--email', required=True, help='User email address')
@click.option('--month', type=int, help='Month (1-12)', default=None)
@click.option('--year', type=int, help='Year', default=None)
def send_test_newsletter(email, month, year):
    """Send a test newsletter to a specific email."""
    from app.models.database import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            click.echo(f"✗ User not found: {email}", err=True)
            return

        now = datetime.now()
        month = month or now.month
        year = year or now.year

        # Get sampler events
        from app.api.events import get_sampler_events
        from unittest.mock import MagicMock

        # Mock request object
        request = MagicMock()
        events = get_sampler_events(db=db)

        click.echo(f"Sending test newsletter to {email}...")
        email_service = EmailService()
        success = email_service.send_newsletter(
            user=user,
            events=events,
            month=month,
            year=year,
            is_sampler=True
        )

        if success:
            click.echo("✓ Newsletter sent successfully!")
        else:
            click.echo("✗ Failed to send newsletter", err=True)

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
    finally:
        db.close()


@cli.command()
def generate_newsletters():
    """Manually trigger newsletter generation for all users."""
    click.echo("Generating and sending newsletters...")
    scheduler = NewsletterScheduler()
    try:
        scheduler.generate_and_send_newsletters()
        click.echo("✓ Newsletters generated and sent!")
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)


@cli.command()
@click.option('--email', required=True, help='User email')
@click.option('--password', required=True, help='User password')
@click.option('--name', help='Full name')
def create_user(email, password, name):
    """Create a new user."""
    from app.models.database import User, Subscription, SubscriptionTier, UserPreferences
    from app.api.auth import get_password_hash

    db = SessionLocal()
    try:
        # Check if exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            click.echo(f"✗ User already exists: {email}", err=True)
            return

        # Create user
        user = User(
            email=email,
            full_name=name,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_verified=False
        )
        db.add(user)
        db.flush()

        # Create subscription
        subscription = Subscription(
            user_id=user.id,
            tier=SubscriptionTier.FREE,
            status="active"
        )
        db.add(subscription)

        # Create preferences
        preferences = UserPreferences(
            user_id=user.id,
            preferred_categories=[],
        )
        db.add(preferences)

        db.commit()
        click.echo(f"✓ User created: {email}")

    except Exception as e:
        db.rollback()
        click.echo(f"✗ Error: {e}", err=True)
    finally:
        db.close()


@cli.command()
def stats():
    """Show application statistics."""
    from app.models.database import User, Event, Newsletter, DataSource

    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        event_count = db.query(Event).count()
        newsletter_count = db.query(Newsletter).count()
        source_count = db.query(DataSource).count()

        upcoming_events = db.query(Event).filter(
            Event.start_date >= datetime.now()
        ).count()

        click.echo("Application Statistics\n")
        click.echo(f"Users: {user_count}")
        click.echo(f"Events (total): {event_count}")
        click.echo(f"Events (upcoming): {upcoming_events}")
        click.echo(f"Newsletters sent: {newsletter_count}")
        click.echo(f"Data sources: {source_count}")

    finally:
        db.close()


if __name__ == '__main__':
    cli()
