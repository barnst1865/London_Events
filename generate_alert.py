#!/usr/bin/env python
"""CLI entry point: generate a selling-fast alert post for Substack."""
import argparse
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models.database import Event, EventStatus
from app.services.content_generator import ContentGenerator
from app.services.sellout_monitor import SelloutMonitor
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Generate a selling-fast alert post."""
    parser = argparse.ArgumentParser(description="Generate selling-fast alert post")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Scheduler mode: quiet output, exit 0 = alert generated, exit 1 = no alert",
    )
    args = parser.parse_args()

    logger.info("Initializing database...")
    init_db()

    db = SessionLocal()
    try:
        if args.auto:
            # Automated mode: use SelloutMonitor with history-based detection
            monitor = SelloutMonitor()
            result_path = monitor.generate_and_save_alert(db)
            if result_path:
                logger.info(f"Alert generated: {result_path}")
                sys.exit(0)
            else:
                logger.info("No alert needed")
                sys.exit(1)
        else:
            # Manual mode: query current selling-fast + recently sold-out events
            now = datetime.utcnow()
            end_date = now + timedelta(days=90)

            selling_fast = (
                db.query(Event)
                .filter(
                    Event.start_date >= now,
                    Event.start_date <= end_date,
                    Event.status == EventStatus.SELLING_FAST,
                )
                .order_by(Event.availability_percentage.asc())
                .all()
            )

            sold_out = (
                db.query(Event)
                .filter(
                    Event.start_date >= now,
                    Event.start_date <= end_date,
                    Event.status == EventStatus.SOLD_OUT,
                    Event.previous_status != None,  # Only recently changed
                )
                .order_by(Event.start_date.asc())
                .all()
            )

            events = selling_fast + sold_out

            if not events:
                print("No selling-fast or recently sold-out events found. Nothing to alert about.")
                return

            logger.info(
                f"Found {len(selling_fast)} selling-fast and {len(sold_out)} sold-out events"
            )

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
            print(f"  Selling fast: {len(selling_fast)}")
            print(f"  Sold out: {len(sold_out)}")
            print(f"  Paste into Substack as an ad-hoc post.")

    except Exception as e:
        logger.error(f"Alert generation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
