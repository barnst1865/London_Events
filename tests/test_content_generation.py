"""Tests for ContentGenerator — HTML output and price formatting."""
import pytest
from datetime import datetime

from app.models.database import EventStatus
from app.services.content_generator import ContentGenerator


@pytest.fixture
def gen():
    return ContentGenerator()


# --- _format_price ---

class TestFormatPrice:
    def test_none_none(self, gen, make_event):
        event = make_event(price_min=None, price_max=None)
        assert gen._format_price(event) == "Price TBA"

    def test_free_min_zero_max_none(self, gen, make_event):
        event = make_event(price_min=0, price_max=None)
        assert gen._format_price(event) == "FREE"

    def test_free_both_zero(self, gen, make_event):
        event = make_event(price_min=0, price_max=0)
        assert gen._format_price(event) == "FREE"

    def test_from_price(self, gen, make_event):
        event = make_event(price_min=25.0, price_max=None)
        assert gen._format_price(event) == "From £25.00"

    def test_up_to_price(self, gen, make_event):
        event = make_event(price_min=None, price_max=75.0)
        assert gen._format_price(event) == "Up to £75.00"

    def test_range(self, gen, make_event):
        event = make_event(price_min=25.0, price_max=75.0)
        result = gen._format_price(event)
        assert result == "£25.00 – £75.00"

    def test_same_min_max(self, gen, make_event):
        event = make_event(price_min=25.0, price_max=25.0)
        assert gen._format_price(event) == "From £25.00"

    def test_non_gbp_currency(self, gen, make_event):
        event = make_event(price_min=25.0, price_max=75.0, currency="EUR")
        result = gen._format_price(event)
        assert "EUR" in result


# --- _render_event_card ---

class TestRenderEventCard:
    def test_basic_card(self, gen, make_event):
        event = make_event(title="Cool Show", venue_name="The O2", price_min=30.0)
        html = gen._render_event_card(event)
        assert "Cool Show" in html
        assert "The O2" in html
        assert "£30.00" in html

    def test_urgency_shown(self, gen, make_event):
        event = make_event(
            status=EventStatus.SELLING_FAST,
            tickets_available=5,
        )
        html = gen._render_event_card(event, include_urgency=True)
        assert "5 tickets left" in html

    def test_ticket_url_link(self, gen, make_event):
        event = make_event(ticket_url="https://tickets.example.com")
        html = gen._render_event_card(event)
        assert '<a href="https://tickets.example.com">' in html
        assert "Tickets" in html

    def test_venue_none_shows_tba(self, gen, make_event):
        event = make_event(venue_name=None)
        html = gen._render_event_card(event)
        assert "Venue TBA" in html


# --- generate_selling_fast_alert ---

class TestGenerateSellingFastAlert:
    def test_empty_list(self, gen):
        assert gen.generate_selling_fast_alert([]) == ""

    def test_all_upcoming_filtered_out(self, gen, make_event):
        events = [make_event(status=EventStatus.UPCOMING) for _ in range(3)]
        assert gen.generate_selling_fast_alert(events) == ""

    def test_selling_fast_events_included(self, gen, make_event):
        events = [
            make_event(title="Hot Show A", status=EventStatus.SELLING_FAST),
            make_event(title="Hot Show B", status=EventStatus.SELLING_FAST),
        ]
        html = gen.generate_selling_fast_alert(events)
        assert "Hot Show A" in html
        assert "Hot Show B" in html
        assert "Selling Fast Alert" in html

    def test_max_8_events(self, gen, make_event):
        events = [
            make_event(title=f"Show {i}", status=EventStatus.SELLING_FAST)
            for i in range(10)
        ]
        html = gen.generate_selling_fast_alert(events)
        # Show 8 and Show 9 should NOT appear (0-indexed, so shows 0-7 = 8 events)
        assert "Show 7" in html
        assert "Show 8" not in html
