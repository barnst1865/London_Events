"""Sellout detection service - identifies events that are selling out."""
import logging
from typing import Optional
from datetime import datetime, timedelta
from ..models.database import EventStatus
from ..config import settings

logger = logging.getLogger(__name__)


class SelloutDetector:
    """
    Detects events that are selling out or likely to sell out.

    Uses multiple signals:
    - Ticket availability percentage
    - Rate of ticket sales
    - Time until event
    - Historical patterns
    """

    def __init__(self):
        self.sellout_threshold = settings.sellout_threshold_percentage
        self.low_availability_threshold = settings.low_availability_threshold

    def determine_status(
        self,
        tickets_available: Optional[int] = None,
        total_tickets: Optional[int] = None,
        on_sale_status: Optional[str] = None,
        previous_availability: Optional[int] = None,
        last_check: Optional[datetime] = None,
        event_date: Optional[datetime] = None,
    ) -> EventStatus:
        """
        Determine event status based on ticket availability.

        Args:
            tickets_available: Current number of tickets available
            total_tickets: Total ticket capacity
            on_sale_status: Status from source (onsale, offsale, etc.)
            previous_availability: Previous ticket count
            last_check: When availability was last checked
            event_date: Date of the event

        Returns:
            EventStatus enum value
        """
        # Check if sold out
        if tickets_available == 0 or (
            on_sale_status and on_sale_status in ["soldout", "sold_out", "sold-out"]
        ):
            return EventStatus.SOLD_OUT

        # Check if cancelled
        if on_sale_status and on_sale_status in ["cancelled", "canceled"]:
            return EventStatus.CANCELLED

        # If we have availability data, calculate percentage
        if tickets_available is not None and total_tickets is not None and total_tickets > 0:
            availability_percentage = (tickets_available / total_tickets) * 100

            # Selling fast if below threshold
            if availability_percentage <= self.sellout_threshold:
                return EventStatus.SELLING_FAST

            # Also mark as selling fast if low absolute number
            if tickets_available <= self.low_availability_threshold:
                return EventStatus.SELLING_FAST

        # Check rate of sales if we have historical data
        if (previous_availability is not None and
            tickets_available is not None and
            last_check is not None and
            event_date is not None):

            is_selling_fast = self._is_selling_fast_by_rate(
                current_available=tickets_available,
                previous_available=previous_availability,
                time_since_check=datetime.utcnow() - last_check,
                time_until_event=event_date - datetime.utcnow()
            )

            if is_selling_fast:
                return EventStatus.SELLING_FAST

        # Check on-sale status
        if on_sale_status:
            if on_sale_status in ["onsale", "on_sale"]:
                return EventStatus.ON_SALE
            elif on_sale_status in ["presale", "pre_sale"]:
                return EventStatus.ON_SALE
            elif on_sale_status in ["offsale", "off_sale"]:
                return EventStatus.UPCOMING

        # Default status
        return EventStatus.UPCOMING

    def _is_selling_fast_by_rate(
        self,
        current_available: int,
        previous_available: int,
        time_since_check: timedelta,
        time_until_event: timedelta
    ) -> bool:
        """
        Determine if event is selling fast based on rate of sales.

        Args:
            current_available: Current tickets available
            previous_available: Previous tickets available
            time_since_check: Time since last check
            time_until_event: Time until the event

        Returns:
            True if selling at a fast rate
        """
        if time_since_check.total_seconds() == 0:
            return False

        # Calculate tickets sold per day
        tickets_sold = previous_available - current_available
        days_since_check = time_since_check.total_seconds() / 86400

        if days_since_check == 0:
            return False

        tickets_per_day = tickets_sold / days_since_check

        # Calculate days until event
        days_until_event = time_until_event.total_seconds() / 86400

        if days_until_event <= 0:
            return False

        # Project when tickets will sell out
        if tickets_per_day > 0:
            days_to_sellout = current_available / tickets_per_day

            # If projected to sell out in less than 7 days, mark as selling fast
            if days_to_sellout <= 7:
                return True

            # If selling rate is accelerating (more than 50% of remaining time)
            if days_to_sellout < (days_until_event * 0.5):
                return True

        return False

    def get_sellout_probability(
        self,
        tickets_available: int,
        total_tickets: int,
        days_until_event: float,
        tickets_per_day: float = None
    ) -> float:
        """
        Calculate probability that event will sell out (0-1).

        Args:
            tickets_available: Current tickets available
            total_tickets: Total capacity
            days_until_event: Days until event
            tickets_per_day: Average ticket sales per day (optional)

        Returns:
            Probability between 0 and 1
        """
        if total_tickets == 0:
            return 0.0

        # Base probability on availability percentage
        availability_pct = (tickets_available / total_tickets) * 100
        base_probability = 1.0 - (availability_pct / 100)

        # Adjust based on time
        if days_until_event <= 0:
            return 0.0
        elif days_until_event <= 7:
            time_factor = 1.3
        elif days_until_event <= 30:
            time_factor = 1.1
        else:
            time_factor = 0.9

        probability = base_probability * time_factor

        # If we have sales rate data, factor it in
        if tickets_per_day is not None and tickets_per_day > 0:
            days_to_sellout = tickets_available / tickets_per_day
            if days_to_sellout < days_until_event:
                # Likely to sell out
                rate_factor = 1.2
            else:
                # Unlikely to sell out at current rate
                rate_factor = 0.8

            probability *= rate_factor

        return min(1.0, max(0.0, probability))

    def get_urgency_message(
        self,
        status: EventStatus,
        tickets_available: Optional[int] = None,
        availability_percentage: Optional[float] = None
    ) -> str:
        """
        Get user-friendly urgency message.

        Args:
            status: Event status
            tickets_available: Number of tickets available
            availability_percentage: Percentage of tickets available

        Returns:
            Urgency message string
        """
        if status == EventStatus.SOLD_OUT:
            return "SOLD OUT"

        elif status == EventStatus.SELLING_FAST:
            if tickets_available and tickets_available <= 10:
                return f"Only {tickets_available} tickets left!"
            elif availability_percentage and availability_percentage <= 5:
                return "Less than 5% of tickets remaining!"
            elif availability_percentage and availability_percentage <= 10:
                return "Selling fast - less than 10% remaining!"
            else:
                return "Selling fast - book soon!"

        elif status == EventStatus.ON_SALE:
            return "On sale now"

        elif status == EventStatus.CANCELLED:
            return "Cancelled"

        else:
            return ""

    def should_highlight(self, status: EventStatus) -> bool:
        """
        Determine if event should be highlighted in newsletter.

        Args:
            status: Event status

        Returns:
            True if should be highlighted
        """
        return status in [EventStatus.SELLING_FAST, EventStatus.ON_SALE]
