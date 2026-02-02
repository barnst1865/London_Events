"""Generate Substack-compatible HTML newsletter content."""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from ..models.database import Event, EventStatus
from .sellout_detector import SelloutDetector
from .ai_curator import AICurator

logger = logging.getLogger(__name__)


class ContentGenerator:
    """
    Generates Substack-compatible HTML newsletter content.

    Structure:
    - FREE section (above Substack paywall):
      - Newsletter intro
      - Editor's Picks (3-5 AI-curated highlights)
      - Selling Fast alerts
    - PAYWALL marker
    - PAID section (below paywall):
      - Just Announced
      - Full listings by category
      - Price-tiered sections (Free Events, Under £20, Premium)
    """

    def __init__(self):
        self.sellout_detector = SelloutDetector()
        self.ai_curator = AICurator()

    def generate_weekly_newsletter(self, events: List[Event]) -> str:
        """
        Generate the full weekly newsletter HTML.

        Args:
            events: All upcoming events from the database

        Returns:
            HTML string ready for Substack
        """
        now = datetime.now()
        date_str = now.strftime("%d %B %Y")

        # Partition events
        selling_fast = [e for e in events if e.status == EventStatus.SELLING_FAST]
        just_announced = self._get_just_announced(events)
        by_category = self._group_by_category(events)
        free_events = [e for e in events if e.price_min is not None and e.price_min == 0]
        under_20 = [
            e
            for e in events
            if e.price_min is not None and 0 < e.price_min <= 20
        ]
        premium = [
            e for e in events if e.price_min is not None and e.price_min > 20
        ]

        # AI curation
        picks_data = self.ai_curator.curate_editors_picks(events, max_picks=5)
        picks_map = {p["event_id"]: p["editorial_note"] for p in picks_data}
        picks_events = [e for e in events if e.id in picks_map]

        highlights = ", ".join(e.title for e in picks_events[:3])
        intro_text = self.ai_curator.generate_newsletter_intro(
            len(events), highlights
        )

        # Build HTML
        sections = []

        # --- FREE SECTION (above paywall) ---
        sections.append(self._render_header(date_str, len(events)))
        sections.append(self._render_intro(intro_text))

        if picks_events:
            sections.append(
                self._render_editors_picks(picks_events, picks_map)
            )

        if selling_fast:
            sections.append(self._render_selling_fast(selling_fast[:10]))

        # --- PAYWALL MARKER ---
        sections.append("\n<!-- PAYWALL -->\n")

        # --- PAID SECTION (below paywall) ---
        if just_announced:
            sections.append(self._render_just_announced(just_announced[:15]))

        for category_name, cat_events in sorted(by_category.items()):
            if cat_events:
                sections.append(
                    self._render_category_section(category_name, cat_events)
                )

        if free_events:
            sections.append(
                self._render_price_section("Free Events", free_events[:15])
            )
        if under_20:
            sections.append(
                self._render_price_section("Under £20", under_20[:15])
            )
        if premium:
            sections.append(
                self._render_price_section("Premium Experiences", premium[:15])
            )

        sections.append(self._render_footer(date_str))

        return "\n\n".join(sections)

    def generate_selling_fast_alert(self, events: List[Event]) -> str:
        """
        Generate a short-form "Selling Fast" alert post.

        Args:
            events: Events that have crossed the SELLING_FAST threshold

        Returns:
            HTML string for a Substack alert post
        """
        selling_fast = [e for e in events if e.status == EventStatus.SELLING_FAST]
        if not selling_fast:
            return ""

        now = datetime.now()
        date_str = now.strftime("%d %B %Y")

        sections = []
        sections.append(f"<h1>Selling Fast Alert — {date_str}</h1>")
        sections.append(
            "<p>These events are running low on tickets. "
            "If any catch your eye, don't wait.</p>"
        )

        for event in selling_fast[:8]:
            sections.append(self._render_event_card(event, include_urgency=True))

        sections.append(
            "<hr>\n<p><em>Full listings and editor's picks in the weekly edition.</em></p>"
        )

        return "\n\n".join(sections)

    # --- Rendering helpers ---

    def _render_header(self, date_str: str, total_events: int) -> str:
        return (
            f"<h1>London Events — Week of {date_str}</h1>\n"
            f"<p><strong>{total_events} events</strong> across London this week and beyond.</p>"
        )

    def _render_intro(self, intro_text: str) -> str:
        if not intro_text:
            return ""
        return f"<p>{intro_text}</p>"

    def _render_editors_picks(
        self, events: List[Event], notes: Dict[int, str]
    ) -> str:
        lines = ["<h2>Editor's Picks</h2>"]
        for event in events:
            note = notes.get(event.id, "")
            lines.append(self._render_pick_card(event, note))
        return "\n".join(lines)

    def _render_pick_card(self, event: Event, editorial_note: str) -> str:
        price = self._format_price(event)
        date = event.start_date.strftime("%A %d %B")
        venue = event.venue_name or "Venue TBA"

        urgency = self.sellout_detector.get_urgency_message(
            event.status, event.tickets_available, event.availability_percentage
        )
        urgency_html = f'\n<p><strong>{urgency}</strong></p>' if urgency else ""

        note_html = f"\n<p><em>{editorial_note}</em></p>" if editorial_note else ""

        link = ""
        if event.ticket_url:
            link = f'\n<p><a href="{event.ticket_url}">Get tickets</a></p>'

        return (
            f"<h3>{event.title}</h3>\n"
            f"<p>{venue} · {date} · {price}</p>"
            f"{urgency_html}"
            f"{note_html}"
            f"{link}"
        )

    def _render_selling_fast(self, events: List[Event]) -> str:
        lines = ["<h2>Selling Fast</h2>"]
        for event in events:
            lines.append(self._render_event_card(event, include_urgency=True))
        return "\n".join(lines)

    def _render_just_announced(self, events: List[Event]) -> str:
        lines = ["<h2>Just Announced</h2>"]
        for event in events:
            lines.append(self._render_event_card(event))
        return "\n".join(lines)

    def _render_category_section(
        self, category_name: str, events: List[Event]
    ) -> str:
        lines = [f"<h2>{category_name}</h2>"]
        for event in events[:20]:
            lines.append(self._render_event_card(event))
        return "\n".join(lines)

    def _render_price_section(self, title: str, events: List[Event]) -> str:
        lines = [f"<h2>{title}</h2>"]
        for event in events:
            lines.append(self._render_event_card(event))
        return "\n".join(lines)

    def _render_event_card(
        self, event: Event, include_urgency: bool = False
    ) -> str:
        price = self._format_price(event)
        date = event.start_date.strftime("%a %d %b")
        venue = event.venue_name or "Venue TBA"

        urgency_html = ""
        if include_urgency:
            msg = self.sellout_detector.get_urgency_message(
                event.status, event.tickets_available, event.availability_percentage
            )
            if msg:
                urgency_html = f" — <strong>{msg}</strong>"

        link = ""
        if event.ticket_url:
            link = f' · <a href="{event.ticket_url}">Tickets</a>'

        return (
            f"<p><strong>{event.title}</strong> · {venue} · {date} · {price}"
            f"{urgency_html}{link}</p>"
        )

    def _render_footer(self, date_str: str) -> str:
        return (
            "<hr>\n"
            f"<p><em>London Events Report — {date_str}</em></p>\n"
            "<p><em>Data sourced from Ticketmaster, Eventbrite, SeatGeek, "
            "and venue websites. Availability is checked daily but can change rapidly "
            "— always confirm on the ticket link.</em></p>"
        )

    # --- Data helpers ---

    def _get_just_announced(
        self, events: List[Event], days: int = 7
    ) -> List[Event]:
        """Get events first seen in the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [
            e
            for e in events
            if e.first_seen_at and e.first_seen_at >= cutoff
        ]

    def _group_by_category(
        self, events: List[Event]
    ) -> Dict[str, List[Event]]:
        """Group events by their primary category."""
        grouped = defaultdict(list)
        for event in events:
            if event.categories:
                for cat in event.categories:
                    grouped[cat.name].append(event)
            else:
                grouped["Other"].append(event)
        return dict(grouped)

    def _format_price(self, event: Event) -> str:
        """Format price for display."""
        if event.price_min is None and event.price_max is None:
            return "Price TBA"
        if event.price_min == 0 and (event.price_max is None or event.price_max == 0):
            return "FREE"

        symbol = "£" if event.currency == "GBP" else event.currency

        if (
            event.price_min is not None
            and event.price_max is not None
            and event.price_min != event.price_max
        ):
            return f"{symbol}{event.price_min:.2f} – {symbol}{event.price_max:.2f}"
        elif event.price_min is not None:
            return f"From {symbol}{event.price_min:.2f}"
        elif event.price_max is not None:
            return f"Up to {symbol}{event.price_max:.2f}"
        else:
            return "Price TBA"
