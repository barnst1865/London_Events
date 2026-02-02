#!/usr/bin/env python
"""CLI entry point: generate a selling-fast alert post for Substack."""
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

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
    """Generate a selling-fast alert post."""
    logger.info("Initializing database...")
    init_db()

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        end_date = now + timedelta(days=90)

        events = (
            db.query(Event)
            .filter(
                Event.start_date >= now,
                Event.start_date <= end_date,
                Event.status == EventStatus.SELLING_FAST,
            )
            .order_by(Event.availability_percentage.asc())
            .all()
        )

        if not events:
            print("No selling-fast events found. Nothing to alert about.")
            return

        logger.info(f"Found {len(events)} selling-fast events")

        generator = ContentGenerator()
        html = generator.generate_selling_fast_alert(events)

        if not html:
            print("No content generated.")
            return

        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = output_dir / f"alert_{date_str}.html"
        output_path.write_text(html, encoding="utf-8")

        print(f"Selling-fast alert generated: {output_path}")
        print(f"  Events included: {len(events)}")
        print(f"  Paste into Substack as an ad-hoc post.")

    except Exception as e:
        logger.error(f"Alert generation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
