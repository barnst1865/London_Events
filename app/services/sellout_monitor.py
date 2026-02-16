"""Sellout monitoring service — detects alert-worthy status changes."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.database import Event, EventStatus, AvailabilityHistory
from ..config import settings
from .content_generator import ContentGenerator

logger = logging.getLogger(__name__)


@dataclass
class AlertResult:
    """Result of checking for sellout alerts."""
    newly_selling_fast: List[Event] = field(default_factory=list)
    newly_sold_out: List[Event] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.utcnow)


class SelloutMonitor:
    """
    Monitors availability changes and triggers alerts.

    Queries availability_history for recent status transitions,
    determines if an alert should be generated, and produces
    Substack-ready HTML via ContentGenerator.
    """

    def check_for_alerts(self, db: Session, since: datetime) -> AlertResult:
        """
        Check for alert-worthy status changes since a given time.

        Args:
            db: Database session
            since: Only consider changes after this timestamp

        Returns:
            AlertResult with newly selling-fast and sold-out events
        """
        now = datetime.utcnow()

        # Get status transitions since the given time
        history_records = (
            db.query(AvailabilityHistory)
            .filter(AvailabilityHistory.recorded_at >= since)
            .order_by(AvailabilityHistory.recorded_at.desc())
            .all()
        )

        # Track the latest transition per event (deduplicate multiple changes)
        seen_event_ids = set()
        selling_fast_ids = set()
        sold_out_ids = set()

        for record in history_records:
            if record.event_id in seen_event_ids:
                continue
            seen_event_ids.add(record.event_id)

            if record.new_status == EventStatus.SELLING_FAST:
                selling_fast_ids.add(record.event_id)
            elif record.new_status == EventStatus.SOLD_OUT:
                sold_out_ids.add(record.event_id)

        result = AlertResult()

        # Load events, filtering to future events only
        if selling_fast_ids:
            result.newly_selling_fast = (
                db.query(Event)
                .filter(
                    Event.id.in_(selling_fast_ids),
                    Event.start_date >= now,
                )
                .order_by(Event.availability_percentage.asc())
                .all()
            )

        if sold_out_ids:
            result.newly_sold_out = (
                db.query(Event)
                .filter(
                    Event.id.in_(sold_out_ids),
                    Event.start_date >= now,
                )
                .order_by(Event.start_date.asc())
                .all()
            )

        logger.info(
            f"Alert check: {len(result.newly_selling_fast)} selling fast, "
            f"{len(result.newly_sold_out)} sold out (since {since})"
        )
        return result

    def should_generate_alert(self, result: AlertResult) -> bool:
        """
        Determine if an alert post should be generated.

        Args:
            result: AlertResult from check_for_alerts

        Returns:
            True if thresholds are met for alert generation
        """
        has_enough_selling_fast = (
            len(result.newly_selling_fast) >= settings.sellout_alert_min_selling_fast
        )
        has_enough_sold_out = (
            len(result.newly_sold_out) >= settings.sellout_alert_min_sold_out
        )
        return has_enough_selling_fast or has_enough_sold_out

    def generate_and_save_alert(self, db: Session) -> Optional[Path]:
        """
        Check for alerts and generate an HTML file if thresholds are met.

        Args:
            db: Database session

        Returns:
            Path to generated alert file, or None if no alert needed
        """
        since = datetime.utcnow() - timedelta(hours=25)
        result = self.check_for_alerts(db, since=since)

        if not self.should_generate_alert(result):
            logger.info("No alert needed — thresholds not met")
            return None

        # Combine events for the alert: selling-fast + recently sold-out
        all_alert_events = result.newly_selling_fast + result.newly_sold_out

        generator = ContentGenerator()
        html = generator.generate_selling_fast_alert(all_alert_events)

        if not html:
            logger.info("ContentGenerator returned empty content")
            return None

        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = output_dir / f"alert_{date_str}.html"
        output_path.write_text(html, encoding="utf-8")

        logger.info(
            f"Alert generated: {output_path} "
            f"({len(result.newly_selling_fast)} selling fast, "
            f"{len(result.newly_sold_out)} sold out)"
        )
        return output_path
