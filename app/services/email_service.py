"""Email service for sending newsletters."""
import logging
from typing import List, Dict
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from premailer import transform
import base64

from ..config import settings
from ..models.database import User, Event

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email sending service using SendGrid.
    """

    def __init__(self):
        self.from_email = settings.from_email
        self.from_name = settings.from_name
        self.template_env = Environment(
            loader=FileSystemLoader("app/templates/email")
        )

    def send_newsletter(
        self,
        user: User,
        events: List[Event],
        month: int,
        year: int,
        is_sampler: bool = False
    ) -> bool:
        """
        Send newsletter email to user.

        Args:
            user: User to send to
            events: List of events to include
            month: Newsletter month
            year: Newsletter year
            is_sampler: Whether this is a free sampler

        Returns:
            True if sent successfully
        """
        try:
            # Render email HTML
            html_content = self._render_newsletter(
                user=user,
                events=events,
                month=month,
                year=year,
                is_sampler=is_sampler
            )

            # Send email
            subject = self._get_subject(month, year, is_sampler)
            return self._send_email(
                to_email=user.email,
                to_name=user.full_name or user.email,
                subject=subject,
                html_content=html_content
            )

        except Exception as e:
            logger.error(f"Failed to send newsletter to {user.email}: {e}")
            return False

    def _render_newsletter(
        self,
        user: User,
        events: List[Event],
        month: int,
        year: int,
        is_sampler: bool
    ) -> str:
        """Render newsletter HTML from template."""
        from calendar import month_name
        from ..services.sellout_detector import SelloutDetector

        sellout_detector = SelloutDetector()

        # Group events by category
        events_by_category = {}
        for event in events:
            for category in event.categories:
                if category.name not in events_by_category:
                    events_by_category[category.name] = []
                events_by_category[category.name].append(event)

        # Prepare event data with urgency info
        events_data = []
        for event in events:
            urgency_msg = sellout_detector.get_urgency_message(
                status=event.status,
                tickets_available=event.tickets_available,
                availability_percentage=event.availability_percentage
            )

            events_data.append({
                "event": event,
                "urgency_message": urgency_msg,
                "is_urgent": sellout_detector.should_highlight(event.status),
                "price_display": self._format_price(event.price_min, event.price_max, event.currency)
            })

        # Sort by urgency and date
        events_data.sort(key=lambda x: (not x["is_urgent"], x["event"].start_date))

        # Load template
        template_name = "sampler.html" if is_sampler else "newsletter.html"
        template = self.template_env.get_template(template_name)

        # Render
        html = template.render(
            user=user,
            events=events_data,
            events_by_category=events_by_category,
            month_name=month_name[month],
            year=year,
            is_sampler=is_sampler,
            total_events=len(events),
            app_name=settings.app_name,
            unsubscribe_url=f"https://example.com/unsubscribe/{user.id}"  # TODO: Implement
        )

        # Inline CSS for email clients
        html = transform(html)

        return html

    def _send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str
    ) -> bool:
        """Send email via SendGrid."""
        if not settings.sendgrid_api_key:
            logger.warning("SendGrid API key not configured")
            # In development, just log the email
            logger.info(f"Would send email to {to_email}: {subject}")
            return True

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=(to_email, to_name),
                subject=subject,
                html_content=html_content
            )

            sg = SendGridAPIClient(settings.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent to {to_email}")
                return True
            else:
                logger.error(f"SendGrid error: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _get_subject(self, month: int, year: int, is_sampler: bool) -> str:
        """Generate email subject line."""
        from calendar import month_name

        if is_sampler:
            return f"🎭 Your Free London Events Sampler - {month_name[month]} {year}"
        else:
            return f"🎭 London Events Report - {month_name[month]} {year}"

    def _format_price(self, price_min: float, price_max: float, currency: str) -> str:
        """Format price range for display."""
        if price_min is None and price_max is None:
            return "Price TBA"

        if price_min == 0 and (price_max is None or price_max == 0):
            return "FREE"

        symbol = "£" if currency == "GBP" else currency

        if price_min and price_max and price_min != price_max:
            return f"{symbol}{price_min:.2f} - {symbol}{price_max:.2f}"
        elif price_min:
            return f"From {symbol}{price_min:.2f}"
        elif price_max:
            return f"Up to {symbol}{price_max:.2f}"
        else:
            return "Price TBA"


class SubscriptionService:
    """Service for managing user subscriptions (placeholder)."""

    def __init__(self, db):
        self.db = db

    def is_active_subscriber(self, user_id: int) -> bool:
        """Check if user has active paid subscription."""
        from ..models.database import Subscription, SubscriptionTier

        subscription = self.db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).first()

        if not subscription:
            return False

        return (
            subscription.tier in [SubscriptionTier.MONTHLY, SubscriptionTier.ANNUAL]
            and subscription.status == "active"
        )
