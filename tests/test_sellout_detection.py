"""Tests for SelloutDetector — pure logic, no DB needed."""
import pytest
from datetime import datetime, timedelta

from app.models.database import EventStatus
from app.services.sellout_detector import SelloutDetector


@pytest.fixture
def detector():
    return SelloutDetector()


# --- determine_status: SOLD_OUT ---

class TestDetermineStatusSoldOut:
    def test_tickets_available_zero(self, detector):
        assert detector.determine_status(tickets_available=0) == EventStatus.SOLD_OUT

    def test_on_sale_status_soldout(self, detector):
        assert detector.determine_status(on_sale_status="soldout") == EventStatus.SOLD_OUT

    def test_on_sale_status_sold_out_underscore(self, detector):
        assert detector.determine_status(on_sale_status="sold_out") == EventStatus.SOLD_OUT

    def test_on_sale_status_sold_out_hyphen(self, detector):
        assert detector.determine_status(on_sale_status="sold-out") == EventStatus.SOLD_OUT


# --- determine_status: CANCELLED ---

class TestDetermineStatusCancelled:
    def test_cancelled_british(self, detector):
        assert detector.determine_status(on_sale_status="cancelled") == EventStatus.CANCELLED

    def test_canceled_american(self, detector):
        assert detector.determine_status(on_sale_status="canceled") == EventStatus.CANCELLED


# --- determine_status: SELLING_FAST ---

class TestDetermineStatusSellingFast:
    def test_low_percentage(self, detector):
        """8% availability is below the 10% threshold."""
        result = detector.determine_status(tickets_available=80, total_tickets=1000)
        assert result == EventStatus.SELLING_FAST

    def test_low_absolute_count(self, detector):
        """40 tickets is below the 50 absolute threshold."""
        result = detector.determine_status(tickets_available=40, total_tickets=5000)
        assert result == EventStatus.SELLING_FAST

    def test_rate_based_selling_fast(self, detector):
        """Projected sellout in <7 days should be SELLING_FAST."""
        now = datetime.utcnow()
        result = detector.determine_status(
            tickets_available=100,
            total_tickets=10000,
            previous_availability=200,
            last_check=now - timedelta(days=1),
            event_date=now + timedelta(days=14),
        )
        assert result == EventStatus.SELLING_FAST


# --- determine_status: ON_SALE ---

class TestDetermineStatusOnSale:
    def test_onsale(self, detector):
        assert detector.determine_status(on_sale_status="onsale") == EventStatus.ON_SALE

    def test_on_sale_underscore(self, detector):
        assert detector.determine_status(on_sale_status="on_sale") == EventStatus.ON_SALE

    def test_presale(self, detector):
        assert detector.determine_status(on_sale_status="presale") == EventStatus.ON_SALE


# --- determine_status: UPCOMING ---

class TestDetermineStatusUpcoming:
    def test_offsale(self, detector):
        assert detector.determine_status(on_sale_status="offsale") == EventStatus.UPCOMING

    def test_no_args_default(self, detector):
        assert detector.determine_status() == EventStatus.UPCOMING

    def test_above_thresholds(self, detector):
        """Plenty of tickets → UPCOMING (no on_sale_status to promote to ON_SALE)."""
        result = detector.determine_status(tickets_available=500, total_tickets=1000)
        assert result == EventStatus.UPCOMING


# --- _is_selling_fast_by_rate ---

class TestIsSellingFastByRate:
    def test_zero_time_since_check(self, detector):
        assert detector._is_selling_fast_by_rate(
            current_available=100,
            previous_available=200,
            time_since_check=timedelta(0),
            time_until_event=timedelta(days=7),
        ) is False

    def test_event_in_past(self, detector):
        assert detector._is_selling_fast_by_rate(
            current_available=100,
            previous_available=200,
            time_since_check=timedelta(days=1),
            time_until_event=timedelta(days=-1),
        ) is False

    def test_no_sales(self, detector):
        """No tickets sold → not selling fast."""
        assert detector._is_selling_fast_by_rate(
            current_available=200,
            previous_available=200,
            time_since_check=timedelta(days=1),
            time_until_event=timedelta(days=7),
        ) is False


# --- get_sellout_probability ---

class TestGetSelloutProbability:
    def test_zero_total_returns_zero(self, detector):
        assert detector.get_sellout_probability(0, 0, 30) == 0.0

    def test_event_passed_returns_zero(self, detector):
        assert detector.get_sellout_probability(500, 1000, -1) == 0.0

    def test_high_availability_low_prob(self, detector):
        prob = detector.get_sellout_probability(900, 1000, 60)
        assert prob < 0.2

    def test_low_availability_soon_high_prob(self, detector):
        prob = detector.get_sellout_probability(50, 1000, 3)
        assert prob > 0.8

    def test_clamped_to_unit_interval(self, detector):
        prob = detector.get_sellout_probability(1, 1000, 1, tickets_per_day=500)
        assert 0.0 <= prob <= 1.0


# --- get_urgency_message ---

class TestGetUrgencyMessage:
    def test_sold_out(self, detector):
        assert detector.get_urgency_message(EventStatus.SOLD_OUT) == "SOLD OUT"

    def test_selling_fast_low_tickets(self, detector):
        msg = detector.get_urgency_message(EventStatus.SELLING_FAST, tickets_available=10)
        assert "10 tickets left" in msg

    def test_selling_fast_low_percentage(self, detector):
        msg = detector.get_urgency_message(
            EventStatus.SELLING_FAST, tickets_available=100, availability_percentage=5.0
        )
        assert "5%" in msg

    def test_on_sale(self, detector):
        assert detector.get_urgency_message(EventStatus.ON_SALE) == "On sale now"

    def test_upcoming_empty(self, detector):
        assert detector.get_urgency_message(EventStatus.UPCOMING) == ""

    def test_cancelled(self, detector):
        assert detector.get_urgency_message(EventStatus.CANCELLED) == "Cancelled"
