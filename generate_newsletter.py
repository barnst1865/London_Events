#!/usr/bin/env python
"""CLI entry point: generate weekly newsletter HTML for Substack."""
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models.database import Event, EventStatus
from app.services.content_generator import ContentGenerator
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Generate the weekly newsletter."""
    logger.info("Initializing database...")
    init_db()

    db = SessionLocal()
    try:
        # Query upcoming events (next 90 days)
        now = datetime.utcnow()
        end_date = now + timedelta(days=90)

        events = (
            db.query(Event)
            .filter(Event.start_date >= now, Event.start_date <= end_date)
            .order_by(Event.start_date.asc())
            .all()
        )

        if not events:
            logger.warning("No upcoming events found. Run 'python manage.py fetch' first.")
            print("No upcoming events in database. Fetch events first:")
            print("  python manage.py fetch")
            return

        logger.info(f"Found {len(events)} upcoming events")

        # Generate content
        generator = ContentGenerator()
        html = generator.generate_weekly_newsletter(events)

        # Save to output directory
        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = output_dir / f"newsletter_{date_str}.html"
        output_path.write_text(html, encoding="utf-8")

        print(f"Newsletter generated: {output_path}")
        print(f"  Events included: {len(events)}")
        print(f"  Open in browser to preview, then paste into Substack.")

    except Exception as e:
        logger.error(f"Newsletter generation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
