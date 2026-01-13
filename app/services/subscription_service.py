"""Subscription service - manages user subscriptions."""
from sqlalchemy.orm import Session
from ..models.database import Subscription, SubscriptionTier


class SubscriptionService:
    """Service for managing user subscriptions."""

    def __init__(self, db: Session):
        self.db = db

    def is_active_subscriber(self, user_id: int) -> bool:
        """Check if user has active paid subscription."""
        subscription = self.db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).first()

        if not subscription:
            return False

        return (
            subscription.tier in [SubscriptionTier.MONTHLY, SubscriptionTier.ANNUAL]
            and subscription.status == "active"
        )

    def get_user_event_limit(self, user_id: int) -> int:
        """
        Get the number of events user can access.

        Returns:
            Number of events, or -1 for unlimited
        """
        from ..config import settings

        if self.is_active_subscriber(user_id):
            return -1  # Unlimited

        return settings.free_events_limit
