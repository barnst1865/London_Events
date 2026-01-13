"""Scheduler for automated tasks - monthly newsletter generation."""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
import pytz

from .database import SessionLocal
from .services.event_aggregator import EventAggregator
from .services.email_service import EmailService, SubscriptionService
from .models.database import User, Newsletter, SubscriptionTier
from .config import settings

logger = logging.getLogger(__name__)


class NewsletterScheduler:
    """
    Scheduler for automated newsletter generation and distribution.

    Runs monthly to:
    1. Fetch latest events from all sources
    2. Generate newsletter content
    3. Send to all subscribers
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=settings.report_generation_timezone)
        self.email_service = EmailService()

    def start(self):
        """Start the scheduler."""
        # Schedule monthly newsletter generation
        trigger = CronTrigger(
            day=settings.report_generation_day,
            hour=settings.report_generation_hour,
            minute=0,
            timezone=pytz.timezone(settings.report_generation_timezone)
        )

        self.scheduler.add_job(
            self.generate_and_send_newsletters,
            trigger=trigger,
            id='monthly_newsletter',
            name='Generate and send monthly newsletters',
            replace_existing=True
        )

        # Schedule daily event refresh
        self.scheduler.add_job(
            self.refresh_events,
            trigger='cron',
            hour=3,  # 3 AM
            minute=0,
            id='daily_event_refresh',
            name='Daily event data refresh',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Newsletter scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Newsletter scheduler stopped")

    def generate_and_send_newsletters(self):
        """Generate and send monthly newsletters to all subscribers."""
        logger.info("Starting monthly newsletter generation")

        db = SessionLocal()
        try:
            now = datetime.now()
            month = now.month
            year = now.year

            # First, refresh events for the upcoming month
            start_date = now
            end_date = start_date + timedelta(days=60)  # Next 60 days

            logger.info(f"Fetching events for {month}/{year}")
            aggregator = EventAggregator(db)
            results = aggregator.fetch_all_events(start_date, end_date)

            total_events_fetched = sum(results.values())
            logger.info(f"Fetched {total_events_fetched} events from {len(results)} sources")

            # Get all active users
            users = db.query(User).filter(User.is_active == True).all()
            logger.info(f"Sending newsletters to {len(users)} users")

            sent_count = 0
            subscription_service = SubscriptionService(db)

            for user in users:
                try:
                    # Get events for this user based on subscription tier
                    events = self._get_user_events(db, user, subscription_service)

                    if not events:
                        logger.warning(f"No events found for user {user.email}")
                        continue

                    # Send newsletter
                    is_sampler = not subscription_service.is_active_subscriber(user.id)
                    success = self.email_service.send_newsletter(
                        user=user,
                        events=events,
                        month=month,
                        year=year,
                        is_sampler=is_sampler
                    )

                    if success:
                        sent_count += 1

                except Exception as e:
                    logger.error(f"Failed to send newsletter to {user.email}: {e}")
                    continue

            # Create newsletter record
            newsletter = Newsletter(
                month=month,
                year=year,
                generation_date=datetime.utcnow(),
                events_count=total_events_fetched,
                sent_count=sent_count,
                status="sent"
            )
            db.add(newsletter)
            db.commit()

            logger.info(f"Newsletter generation complete. Sent to {sent_count}/{len(users)} users")

        except Exception as e:
            logger.error(f"Newsletter generation failed: {e}")
            raise
        finally:
            db.close()

    def refresh_events(self):
        """Daily refresh of event data."""
        logger.info("Starting daily event refresh")

        db = SessionLocal()
        try:
            # Refresh events for next 90 days
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

    def _get_user_events(
        self,
        db: Session,
        user: User,
        subscription_service: SubscriptionService
    ) -> list:
        """
        Get events for a user based on their subscription tier.

        Args:
            db: Database session
            user: User object
            subscription_service: Subscription service

        Returns:
            List of events
        """
        from sqlalchemy import and_
        from .models.database import Event, EventStatus

        # Base query - upcoming events only
        query = db.query(Event).filter(
            Event.start_date >= datetime.utcnow()
        ).order_by(Event.start_date.asc())

        # Get event limit based on subscription
        limit = subscription_service.get_user_event_limit(user.id)

        if limit == -1:
            # Full access - return many events, prioritize selling fast
            selling_fast = query.filter(
                Event.status == EventStatus.SELLING_FAST
            ).limit(20).all()

            remaining_limit = 100 - len(selling_fast)
            upcoming = query.filter(
                Event.status != EventStatus.SELLING_FAST
            ).limit(remaining_limit).all()

            return selling_fast + upcoming
        else:
            # Free tier - return limited sampler
            # Prioritize featured and selling fast events
            return query.filter(
                (Event.is_featured == True) |
                (Event.status == EventStatus.SELLING_FAST)
            ).limit(limit).all()


# Global scheduler instance
scheduler = NewsletterScheduler()


def start_scheduler():
    """Start the global scheduler."""
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    scheduler.stop()
