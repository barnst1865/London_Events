"""Tests for AICurator — fallback logic + mocked Anthropic API."""
import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.models.database import EventStatus
from app.services.ai_curator import AICurator


@pytest.fixture
def curator():
    """Curator with no API key → always hits fallback."""
    c = AICurator()
    c.api_key = None
    return c


@pytest.fixture
def curator_with_key():
    """Curator with a fake API key."""
    c = AICurator()
    c.api_key = "test-key-123"
    return c


# --- _fallback_picks ---

class TestFallbackPicks:
    def test_empty_list(self, curator):
        assert curator._fallback_picks([], 5) == []

    def test_sorts_by_popularity(self, curator, make_event):
        e1 = make_event(title="Low", popularity_score=10)
        e2 = make_event(title="High", popularity_score=90)
        picks = curator._fallback_picks([e1, e2], 5)
        assert picks[0]["event_id"] == e2.id

    def test_selling_fast_boost(self, curator, make_event):
        e1 = make_event(title="Normal", popularity_score=80)
        e2 = make_event(title="Hot", popularity_score=10, status=EventStatus.SELLING_FAST)
        picks = curator._fallback_picks([e1, e2], 5)
        # e2 gets +100 boost (110 total) vs e1 (80)
        assert picks[0]["event_id"] == e2.id

    def test_featured_boost(self, curator, make_event):
        e1 = make_event(title="Normal", popularity_score=30)
        e2 = make_event(title="Featured", popularity_score=0, is_featured=True)
        picks = curator._fallback_picks([e1, e2], 5)
        # e2 gets +50 boost (50 total) vs e1 (30)
        assert picks[0]["event_id"] == e2.id

    def test_combined_boosts(self, curator, make_event):
        e1 = make_event(title="Normal", popularity_score=200)
        e2 = make_event(title="Super", popularity_score=60, status=EventStatus.SELLING_FAST, is_featured=True)
        picks = curator._fallback_picks([e1, e2], 5)
        # e2: 60 + 100 + 50 = 210 > e1: 200
        assert picks[0]["event_id"] == e2.id

    def test_respects_max_picks(self, curator, make_event):
        events = [make_event(title=f"E{i}") for i in range(10)]
        picks = curator._fallback_picks(events, 3)
        assert len(picks) == 3

    def test_return_format(self, curator, make_event):
        e = make_event()
        picks = curator._fallback_picks([e], 5)
        assert len(picks) == 1
        assert "event_id" in picks[0]
        assert "editorial_note" in picks[0]
        assert picks[0]["editorial_note"] == ""


# --- _fallback_newsletter_intro ---

class TestFallbackNewsletterIntro:
    def test_contains_event_count(self, curator):
        intro = curator._fallback_newsletter_intro(42)
        assert "42" in intro

    def test_contains_month_name(self, curator):
        intro = curator._fallback_newsletter_intro(10)
        # Should contain the current month name
        month_name = datetime.now().strftime("%B")
        assert month_name in intro


# --- _format_events_for_prompt ---

class TestFormatEventsForPrompt:
    def test_basic_event(self, curator, make_event):
        e = make_event(title="Jazz Night", venue_name="Ronnie Scotts")
        text = curator._format_events_for_prompt([e])
        assert "ID:" in text
        assert "Jazz Night" in text
        assert "Ronnie Scotts" in text

    def test_selling_fast_tag(self, curator, make_event):
        e = make_event(status=EventStatus.SELLING_FAST)
        text = curator._format_events_for_prompt([e])
        assert "[SELLING FAST]" in text

    def test_sold_out_tag(self, curator, make_event):
        e = make_event(status=EventStatus.SOLD_OUT)
        text = curator._format_events_for_prompt([e])
        assert "[SOLD OUT]" in text

    def test_venue_none_shows_tba(self, curator, make_event):
        e = make_event(venue_name=None)
        text = curator._format_events_for_prompt([e])
        assert "Venue TBA" in text

    def test_price_range(self, curator, make_event):
        e = make_event(price_min=25, price_max=50)
        text = curator._format_events_for_prompt([e])
        assert "£25" in text
        assert "£50" in text


# --- curate_editors_picks with API ---

class TestCurateEditorsPicksAPI:
    def test_no_api_key_returns_fallback(self, curator, make_event):
        events = [make_event(title=f"E{i}") for i in range(5)]
        picks = curator.curate_editors_picks(events, max_picks=3)
        assert len(picks) <= 3

    def test_mocked_api_success(self, curator_with_key, make_event):
        e1 = make_event(title="Event One")
        e2 = make_event(title="Event Two")
        events = [e1, e2]

        response_json = json.dumps([
            {"event_id": e1.id, "editorial_note": "Great show"},
            {"event_id": e2.id, "editorial_note": "Must see"},
        ])
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_json)]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.object(curator_with_key, "_get_client", return_value=mock_client):
            picks = curator_with_key.curate_editors_picks(events, max_picks=5)

        assert len(picks) == 2
        assert picks[0]["event_id"] == e1.id
        assert picks[0]["editorial_note"] == "Great show"

    def test_markdown_json_response(self, curator_with_key, make_event):
        """API returns JSON wrapped in markdown code blocks."""
        e = make_event()
        response_text = f'```json\n[{{"event_id": {e.id}, "editorial_note": "Nice"}}]\n```'

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_text)]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.object(curator_with_key, "_get_client", return_value=mock_client):
            picks = curator_with_key.curate_editors_picks([e], max_picks=5)

        assert len(picks) == 1
        assert picks[0]["editorial_note"] == "Nice"

    def test_api_error_falls_back(self, curator_with_key, make_event):
        events = [make_event(title=f"E{i}") for i in range(5)]

        with patch.object(curator_with_key, "_get_client", side_effect=Exception("API down")):
            picks = curator_with_key.curate_editors_picks(events, max_picks=3)

        # Should get fallback picks, not crash
        assert len(picks) <= 3

    def test_invalid_ids_filtered(self, curator_with_key, make_event):
        """API returns event_id that doesn't exist in the events list."""
        e = make_event()
        response_json = json.dumps([
            {"event_id": e.id, "editorial_note": "Real"},
            {"event_id": 99999, "editorial_note": "Fake"},
        ])

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_json)]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.object(curator_with_key, "_get_client", return_value=mock_client):
            picks = curator_with_key.curate_editors_picks([e], max_picks=5)

        assert len(picks) == 1
        assert picks[0]["event_id"] == e.id
