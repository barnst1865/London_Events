"""Scheduler for automated tasks — event collection and content generation triggers."""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from .database import SessionLocal
from .services.event_aggregator import EventAggregator
from .services.sellout_monitor import SelloutMonitor
from .config import settings

logger = logging.getLogger(__name__)


class EventScheduler:
    """
    Scheduler for automated event data collection.

    Runs:
    1. Daily event refresh at 3 AM (next 90 days)
    2. Sellout monitoring at 3:30 AM (checks for alert-worthy status changes)
    3. Weekly content generation trigger (logs reminder, actual generation is CLI-driven)
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler(
            timezone=settings.report_generation_timezone
        )

    def start(self):
        """Start the scheduler."""
        # Daily event refresh at 3 AM
        self.scheduler.add_job(
            self.refresh_events,
            trigger="cron",
            hour=3,
            minute=0,
            id="daily_event_refresh",
            name="Daily event data refresh",
            replace_existing=True,
        )

        # Sellout monitoring at 3:30 AM (after daily fetch completes)
        if settings.sellout_monitor_enabled:
            self.scheduler.add_job(
                self.check_sellout_alerts,
                trigger="cron",
                hour=3,
                minute=30,
                id="sellout_monitor",
                name="Sellout alert monitoring",
                replace_existing=True,
            )

        # Weekly reminder to generate newsletter (day of week configurable)
        self.scheduler.add_job(
            self.weekly_generation_reminder,
            trigger=CronTrigger(
                day_of_week=settings.report_generation_day_of_week,
                hour=settings.report_generation_hour,
                minute=0,
                timezone=pytz.timezone(settings.report_generation_timezone),
            ),
            id="weekly_generation_reminder",
            name="Weekly newsletter generation reminder",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Event scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Event scheduler stopped")

    def refresh_events(self):
        """Daily refresh of event data."""
        logger.info("Starting daily event refresh")

        db = SessionLocal()
        try:
            start_date = datetime.now()
            end_date = start_date + timedelta(days=90)

            aggregator = EventAggregator(db)
            results = aggregator.fetch_all_events(start_date, end_date)

            total_events = sum(results.values())
            logger.info(f"Daily refresh complete. Updated {total_events} events")

        except Exception as e:
            logger.error(f"Daily event refresh failed: {e}")
        finally:
            db.close()

    def check_sellout_alerts(self):
        """Check for sellout alerts after daily refresh."""
        logger.info("Starting sellout alert check")

        db = SessionLocal()
        try:
            monitor = SelloutMonitor()
            result_path = monitor.generate_and_save_alert(db)

            if result_path:
                logger.info(f"Sellout alert generated: {result_path}")
            else:
                logger.info("No sellout alert needed")

        except Exception as e:
            logger.error(f"Sellout alert check failed: {e}")
        finally:
            db.close()

    def weekly_generation_reminder(self):
        """Log a reminder that it's time to generate the weekly newsletter."""
        logger.info(
            "Weekly newsletter generation window. "
            "Run 'python generate_newsletter.py' to generate content."
        )


# Global scheduler instance
scheduler = EventScheduler()


def start_scheduler():
    """Start the global scheduler."""
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    scheduler.stop()
