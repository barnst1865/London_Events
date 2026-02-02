"""AI-powered editorial curation using Anthropic Claude API."""
import logging
import json
from typing import List, Dict, Optional
from datetime import datetime

from ..config import settings
from ..models.database import Event, EventStatus

logger = logging.getLogger(__name__)


class AICurator:
    """
    LLM-powered editorial curation for the newsletter.

    Responsibilities:
    - Select editor's picks from the event pool
    - Generate editorial descriptions ("why this matters")
    - Write section intros with seasonal/topical awareness
    - Flag hidden gems vs obvious headliners
    """

    def __init__(self):
        self.api_key = settings.anthropic_api_key

    def _get_client(self):
        """Get Anthropic client (lazy import to avoid issues when key is missing)."""
        import anthropic

        return anthropic.Anthropic(api_key=self.api_key)

    def curate_editors_picks(
        self, events: List[Event], max_picks: int = 5
    ) -> List[Dict]:
        """
        Select and annotate editor's picks from the event pool.

        Args:
            events: All available upcoming events
            max_picks: Maximum number of picks to select

        Returns:
            List of dicts with 'event_id' and 'editorial_note' keys
        """
        if not self.api_key:
            logger.warning("No Anthropic API key — using fallback pick selection")
            return self._fallback_picks(events, max_picks)

        event_summaries = self._format_events_for_prompt(events[:80])

        prompt = f"""You are an editorial curator for a London events newsletter.
From the following events, select the {max_picks} best "Editor's Picks" — events that would most interest a London audience.

Prioritise:
- Uniqueness and cultural significance
- Events at prestigious venues
- Events selling fast (high urgency)
- Hidden gems that readers might miss
- Mix of categories (don't pick 5 concerts)

For each pick, write a 1-2 sentence editorial note explaining why it's worth attending.
Be specific and opinionated — not generic marketing copy.

EVENTS:
{event_summaries}

Respond with valid JSON only — an array of objects with "event_id" (integer) and "editorial_note" (string).
Example: [{{"event_id": 42, "editorial_note": "The RSC rarely brings full productions to the Barbican — this is a genuine once-a-year opportunity."}}]"""

        try:
            client = self._get_client()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()
            # Extract JSON from response (handle markdown code blocks)
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            picks = json.loads(text)
            valid_ids = {e.id for e in events}
            picks = [p for p in picks if p.get("event_id") in valid_ids]

            logger.info(f"AI selected {len(picks)} editor's picks")
            return picks[:max_picks]

        except Exception as e:
            logger.error(f"AI curation failed: {e}")
            return self._fallback_picks(events, max_picks)

    def generate_section_intro(self, section_name: str, event_count: int) -> str:
        """
        Generate a short intro for a newsletter section.

        Args:
            section_name: Name of the section (e.g. "Music", "Theatre")
            event_count: Number of events in the section

        Returns:
            1-2 sentence section intro
        """
        if not self.api_key:
            return ""

        now = datetime.now()
        month_name = now.strftime("%B")
        year = now.year

        prompt = f"""Write a single-sentence intro for the "{section_name}" section of a London events newsletter for {month_name} {year}.
There are {event_count} events listed. Be concise, specific to London, and avoid clichés.
Just the sentence — no quotes, no label."""

        try:
            client = self._get_client()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip().strip('"')

        except Exception as e:
            logger.error(f"Section intro generation failed: {e}")
            return ""

    def generate_newsletter_intro(self, total_events: int, highlights: str) -> str:
        """
        Generate the opening paragraph for the newsletter.

        Args:
            total_events: Total number of events in this edition
            highlights: Brief summary of notable events

        Returns:
            Opening paragraph text
        """
        if not self.api_key:
            return self._fallback_newsletter_intro(total_events)

        now = datetime.now()
        month_name = now.strftime("%B")
        year = now.year

        prompt = f"""Write a 2-3 sentence opening for this week's London events newsletter ({month_name} {year}).
We're featuring {total_events} events. Notable highlights: {highlights}

Tone: knowledgeable Londoner who's genuinely excited but not breathless. Conversational, not corporate.
Just the paragraph — no heading, no greeting."""

        try:
            client = self._get_client()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Newsletter intro generation failed: {e}")
            return self._fallback_newsletter_intro(total_events)

    def _format_events_for_prompt(self, events: List[Event]) -> str:
        """Format events as a compact text list for the LLM prompt."""
        lines = []
        for e in events:
            price = ""
            if e.price_min is not None:
                price = f" | £{e.price_min:.0f}"
                if e.price_max and e.price_max != e.price_min:
                    price += f"-£{e.price_max:.0f}"
            elif e.price_max is not None:
                price = f" | up to £{e.price_max:.0f}"

            status_tag = ""
            if e.status == EventStatus.SELLING_FAST:
                status_tag = " [SELLING FAST]"
            elif e.status == EventStatus.SOLD_OUT:
                status_tag = " [SOLD OUT]"

            venue = e.venue_name or "Venue TBA"
            date = e.start_date.strftime("%d %b")

            categories = ", ".join(c.name for c in e.categories) if e.categories else ""
            cat_str = f" ({categories})" if categories else ""

            lines.append(
                f"ID:{e.id} | {e.title} | {venue} | {date}{price}{status_tag}{cat_str}"
            )

        return "\n".join(lines)

    def _fallback_picks(self, events: List[Event], max_picks: int) -> List[Dict]:
        """
        Deterministic fallback when AI is unavailable.

        Prioritises selling-fast events, then featured, then by popularity score.
        """
        scored = []
        for e in events:
            score = e.popularity_score or 0.0
            if e.status == EventStatus.SELLING_FAST:
                score += 100
            if e.is_featured:
                score += 50
            scored.append((score, e))

        scored.sort(key=lambda x: x[0], reverse=True)

        picks = []
        for _, event in scored[:max_picks]:
            picks.append(
                {
                    "event_id": event.id,
                    "editorial_note": "",
                }
            )
        return picks

    def _fallback_newsletter_intro(self, total_events: int) -> str:
        """Simple fallback intro when AI is unavailable."""
        now = datetime.now()
        month_name = now.strftime("%B")
        return (
            f"This week's roundup features {total_events} events "
            f"across London this {month_name}."
        )
