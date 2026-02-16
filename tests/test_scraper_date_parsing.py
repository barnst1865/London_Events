"""Tests for scraper date/price parsing — pure methods, no HTTP, no DB."""
import pytest
from datetime import datetime


# =====================================================================
# O2 Arena
# =====================================================================

class TestO2ArenaParseDateText:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.o2_arena import O2ArenaScraper
        self.scraper = O2ArenaScraper()

    def test_standard_format(self):
        assert self.scraper._parse_date_text("13 Feb 2026") == datetime(2026, 2, 13)

    def test_full_month_name(self):
        assert self.scraper._parse_date_text("13 February 2026") == datetime(2026, 2, 13)

    def test_no_spaces(self):
        assert self.scraper._parse_date_text("13Feb2026") == datetime(2026, 2, 13)

    def test_invalid_returns_none(self):
        assert self.scraper._parse_date_text("no date here") is None

    def test_empty_returns_none(self):
        assert self.scraper._parse_date_text("") is None

    def test_day_with_prefix_text(self):
        """Date embedded in surrounding text."""
        assert self.scraper._parse_date_text("Opens 20 Mar 2026") == datetime(2026, 3, 20)


class TestO2ArenaParsePrice:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.o2_arena import O2ArenaScraper
        self.scraper = O2ArenaScraper()

    def test_free_entry(self):
        assert self.scraper._parse_price("Free entry") == (0.0, 0.0)

    def test_single_price(self):
        assert self.scraper._parse_price("£25.00") == (25.0, 25.0)

    def test_price_range(self):
        assert self.scraper._parse_price("£25.00 - £75.00") == (25.0, 75.0)

    def test_no_pound_sign_ignored(self):
        """Prices without £ sign should not match."""
        assert self.scraper._parse_price("Tickets from 25") == (None, None)

    def test_none_input(self):
        assert self.scraper._parse_price(None) == (None, None)


# =====================================================================
# Barbican
# =====================================================================

class TestBarbicanParseDateRangeText:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.barbican import BarbicanScraper
        self.scraper = BarbicanScraper()

    def test_full_range(self):
        result = self.scraper._parse_date_range_text("Fri 30 Jan – Sun 19 Apr 2026")
        assert result == datetime(2026, 1, 30)

    def test_single_date(self):
        result = self.scraper._parse_date_range_text("15 Mar 2026")
        assert result == datetime(2026, 3, 15)

    def test_empty_returns_none(self):
        assert self.scraper._parse_date_range_text("") is None

    def test_none_returns_none(self):
        assert self.scraper._parse_date_range_text(None) is None

    def test_range_with_hyphen(self):
        result = self.scraper._parse_date_range_text("10 Feb - 20 Mar 2026")
        assert result == datetime(2026, 2, 10)


# =====================================================================
# Official London Theatre
# =====================================================================

class TestOLTParseAcfDate:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.official_london_theatre import OfficialLondonTheatreScraper
        self.scraper = OfficialLondonTheatreScraper()

    def test_valid_date(self):
        assert self.scraper._parse_acf_date("20260214") == datetime(2026, 2, 14)

    def test_none_returns_none(self):
        assert self.scraper._parse_acf_date(None) is None

    def test_empty_string_returns_none(self):
        assert self.scraper._parse_acf_date("") is None

    def test_wrong_length_returns_none(self):
        assert self.scraper._parse_acf_date("2026021") is None

    def test_invalid_date_returns_none(self):
        assert self.scraper._parse_acf_date("20261332") is None


# =====================================================================
# KOKO
# =====================================================================

class TestKokoParseEventDate:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.koko import KokoScraper
        self.scraper = KokoScraper()

    def test_us_format(self):
        assert self.scraper._parse_event_date("February 14, 2026") == datetime(2026, 2, 14)

    def test_uk_format(self):
        assert self.scraper._parse_event_date("14 February 2026") == datetime(2026, 2, 14)

    def test_invalid_returns_none(self):
        assert self.scraper._parse_event_date("not a date") is None

    def test_none_returns_none(self):
        assert self.scraper._parse_event_date(None) is None


class TestKokoParseDoorTime:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.koko import KokoScraper
        self.scraper = KokoScraper()

    def test_10pm(self):
        assert self.scraper._parse_door_time("10:00 pm") == (22, 0)

    def test_930am(self):
        assert self.scraper._parse_door_time("9:30 am") == (9, 30)

    def test_12pm_noon(self):
        assert self.scraper._parse_door_time("12:00 pm") == (12, 0)

    def test_12am_midnight(self):
        assert self.scraper._parse_door_time("12:00 am") == (0, 0)

    def test_invalid_returns_none(self):
        assert self.scraper._parse_door_time("invalid") is None


# =====================================================================
# Roundhouse
# =====================================================================

class TestRoundhouseParseDateText:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.roundhouse import RoundhouseScraper
        self.scraper = RoundhouseScraper()

    def test_single_date_no_year(self):
        """Current year is used when no year is provided."""
        result = self.scraper._parse_date_text("Fri 20 February")
        assert result is not None
        assert result.month == 2
        assert result.day == 20

    def test_range_same_month(self):
        result = self.scraper._parse_date_text("Mon 16-Wed 18 February")
        assert result is not None
        assert result.month == 2
        assert result.day == 16

    def test_two_digit_year(self):
        result = self.scraper._parse_date_text("Tue 17 Feb 26")
        assert result == datetime(2026, 2, 17)

    def test_en_dash_range(self):
        result = self.scraper._parse_date_text("Tue 17 Feb 26\u2013Wed 18 Feb 26")
        assert result == datetime(2026, 2, 17)

    def test_empty_returns_none(self):
        assert self.scraper._parse_date_text("") is None


# =====================================================================
# Alexandra Palace
# =====================================================================

class TestAlexandraPalaceParseDateText:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.alexandra_palace import AlexandraPalaceScraper
        self.scraper = AlexandraPalaceScraper()

    def test_standard_format(self):
        assert self.scraper._parse_date_text("14 Feb 2026") == datetime(2026, 2, 14)

    def test_with_day_name(self):
        assert self.scraper._parse_date_text("Sat 14 Feb 2026") == datetime(2026, 2, 14)

    def test_range(self):
        result = self.scraper._parse_date_text("14 Feb \u2013 16 Feb 2026")
        assert result == datetime(2026, 2, 14)

    def test_empty_returns_none(self):
        assert self.scraper._parse_date_text("") is None

    def test_no_year_returns_none(self):
        """Alexandra Palace scraper requires a year (unlike Roundhouse)."""
        assert self.scraper._parse_date_text("14 Feb") is None


class TestAlexandraPalaceParsePrice:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.alexandra_palace import AlexandraPalaceScraper
        from bs4 import BeautifulSoup
        self.scraper = AlexandraPalaceScraper()
        self.BeautifulSoup = BeautifulSoup

    def _make_card(self, text):
        """Create a minimal BeautifulSoup Tag with the given text."""
        return self.BeautifulSoup(f"<div>{text}</div>", "html.parser").find("div")

    def test_free(self):
        card = self._make_card("Free entry")
        assert self.scraper._parse_price(card) == (0.0, 0.0)

    def test_price_range(self):
        card = self._make_card("Tickets £25 - £75")
        assert self.scraper._parse_price(card) == (25.0, 75.0)


# =====================================================================
# Eventim Apollo
# =====================================================================

class TestEventimApolloParseDateText:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.eventim_apollo import EventimApolloScraper
        self.scraper = EventimApolloScraper()

    def test_ordinal_th(self):
        assert self.scraper._parse_date_text("Friday 20th February 2026") == datetime(2026, 2, 20)

    def test_ordinal_st(self):
        assert self.scraper._parse_date_text("Saturday 1st March 2026") == datetime(2026, 3, 1)

    def test_ordinal_nd(self):
        assert self.scraper._parse_date_text("Monday 2nd March 2026") == datetime(2026, 3, 2)

    def test_ordinal_rd(self):
        assert self.scraper._parse_date_text("Wednesday 3rd March 2026") == datetime(2026, 3, 3)

    def test_month_day_range(self):
        result = self.scraper._parse_date_text("Feb 26th - Feb 27th 2026")
        assert result == datetime(2026, 2, 26)

    def test_empty_returns_none(self):
        assert self.scraper._parse_date_text("") is None

    def test_no_year_returns_none(self):
        assert self.scraper._parse_date_text("Friday 20th February") is None


class TestEventimApolloParsePrice:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.eventim_apollo import EventimApolloScraper
        from bs4 import BeautifulSoup
        self.scraper = EventimApolloScraper()
        self.BeautifulSoup = BeautifulSoup

    def _make_card(self, text):
        return self.BeautifulSoup(f"<div>{text}</div>", "html.parser").find("div")

    def test_free(self):
        card = self._make_card("Free entry")
        assert self.scraper._parse_price(card) == (0.0, 0.0)

    def test_price_range(self):
        card = self._make_card("Tickets £25.00 - £75.00")
        assert self.scraper._parse_price(card) == (25.0, 75.0)


# =====================================================================
# DICE
# =====================================================================

class TestDiceParseEvent:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.dice import DiceScraper
        self.scraper = DiceScraper()

    def test_valid_event(self):
        data = {
            "id": "abc123",
            "name": "Test Party",
            "date_unix": 1771020000,  # some future timestamp
            "venues": [{"name": "Test Venue", "address": "123 London Rd"}],
            "price": {"amount_from": 2500},
            "status": "on-sale",
        }
        event = self.scraper._parse_event(data, "music", set())
        assert event is not None
        assert event.title == "Test Party"
        assert event.price_min == 25.0
        assert event.venue_name == "Test Venue"

    def test_no_date_unix_returns_none(self):
        data = {"id": "abc123", "name": "No Date"}
        assert self.scraper._parse_event(data, "music", set()) is None

    def test_no_id_returns_none(self):
        data = {"name": "No ID", "date_unix": 1771020000}
        assert self.scraper._parse_event(data, "music", set()) is None

    def test_price_in_pence(self):
        data = {
            "id": "p1",
            "name": "Pence Event",
            "date_unix": 1771020000,
            "price": {"amount_from": 1500},
        }
        event = self.scraper._parse_event(data, "music", set())
        assert event.price_min == 15.0

    def test_sold_out_status(self):
        data = {
            "id": "so1",
            "name": "Sold Event",
            "date_unix": 1771020000,
            "status": "sold-out",
        }
        event = self.scraper._parse_event(data, "music", set())
        assert event.on_sale_status == "sold_out"


# =====================================================================
# Resident Advisor
# =====================================================================

class TestResidentAdvisorParseDate:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.data_sources.scrapers.resident_advisor import ResidentAdvisorScraper
        self.scraper = ResidentAdvisorScraper()

    def test_unix_int(self):
        result = self.scraper._parse_date(1771020000)
        assert isinstance(result, datetime)

    def test_unix_float(self):
        result = self.scraper._parse_date(1771020000.5)
        assert isinstance(result, datetime)

    def test_iso_without_z(self):
        result = self.scraper._parse_date("2026-02-14T22:00:00.000")
        assert result == datetime(2026, 2, 14, 22, 0, 0)

    def test_iso_with_z(self):
        result = self.scraper._parse_date("2026-02-14T22:00:00.000Z")
        assert result == datetime(2026, 2, 14, 22, 0, 0)

    def test_date_only(self):
        result = self.scraper._parse_date("2026-02-14")
        assert result == datetime(2026, 2, 14)

    def test_unix_as_string(self):
        result = self.scraper._parse_date("1771020000")
        assert isinstance(result, datetime)

    def test_none_returns_none(self):
        assert self.scraper._parse_date(None) is None

    def test_garbage_returns_none(self):
        assert self.scraper._parse_date("not-a-date-at-all") is None
