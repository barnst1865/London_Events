#!/usr/bin/env python
"""Management CLI for London Events application."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.database import SessionLocal, init_db
from app.services.event_aggregator import EventAggregator


def cli():
    """Simple CLI dispatcher."""
    import argparse

    parser = argparse.ArgumentParser(description="London Events Management CLI")
    sub = parser.add_subparsers(dest="command")

    # initdb
    sub.add_parser("initdb", help="Initialize database schema")

    # fetch
    fetch_p = sub.add_parser("fetch", help="Fetch events from data sources")
    fetch_p.add_argument("--days", type=int, default=90, help="Days ahead to fetch")
    fetch_p.add_argument("--sources", help="Comma-separated source names")

    # sources
    sub.add_parser("sources", help="List all data sources and their status")

    # stats
    sub.add_parser("stats", help="Show application statistics")

    args = parser.parse_args()

    if args.command == "initdb":
        cmd_initdb()
    elif args.command == "fetch":
        cmd_fetch(args.days, args.sources)
    elif args.command == "sources":
        cmd_sources()
    elif args.command == "stats":
        cmd_stats()
    else:
        parser.print_help()


def cmd_initdb():
    """Initialize database schema."""
    print("Initializing database...")
    init_db()
    print("Database initialized successfully.")


def cmd_fetch(days: int, sources: str = None):
    """Fetch events from data sources."""
    db = SessionLocal()
    try:
        start_date = datetime.now()
        end_date = start_date + timedelta(days=days)
        source_list = sources.split(",") if sources else None

        print(f"Fetching events from {start_date.date()} to {end_date.date()}...")
        if source_list:
            print(f"Sources: {', '.join(source_list)}")

        aggregator = EventAggregator(db)
        results = aggregator.fetch_all_events(
            start_date, end_date, force_sources=source_list
        )

        print("\nResults:")
        for source, count in results.items():
            print(f"  {source}: {count} events")

        total = sum(results.values())
        print(f"\nTotal: {total} events fetched")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    finally:
        db.close()


def cmd_sources():
    """List all data sources and their status."""
    from app.data_sources import get_all_sources

    print("Available Data Sources:\n")
    for source in get_all_sources():
        enabled = "+" if source.is_enabled() else "-"
        print(f"[{enabled}] {source.display_name} ({source.name})")
        print(f"    Type: {source.source_type}")
        print()


def cmd_stats():
    """Show application statistics."""
    from app.models.database import Event, DataSource, Category

    db = SessionLocal()
    try:
        event_count = db.query(Event).count()
        source_count = db.query(DataSource).count()
        category_count = db.query(Category).count()

        upcoming_events = db.query(Event).filter(
            Event.start_date >= datetime.now()
        ).count()

        selling_fast = db.query(Event).filter(
            Event.status == "selling_fast",
            Event.start_date >= datetime.now(),
        ).count()

        print("Application Statistics\n")
        print(f"Events (total):    {event_count}")
        print(f"Events (upcoming): {upcoming_events}")
        print(f"Selling fast:      {selling_fast}")
        print(f"Data sources:      {source_count}")
        print(f"Categories:        {category_count}")

    finally:
        db.close()


if __name__ == "__main__":
    cli()
