"""Data sources package - expandable event data collection system."""
from typing import List, Type
from .base import BaseDataSource

# Import all data source implementations
from .ticketmaster import TicketmasterSource
from .eventbrite import EventbriteSource
from .seatgeek import SeatGeekSource

# Import scrapers
from .scrapers.timeout_london import TimeOutLondonScraper
from .scrapers.o2_arena import O2ArenaScraper
from .scrapers.royal_albert_hall import RoyalAlbertHallScraper
from .scrapers.barbican import BarbicanScraper
from .scrapers.southbank_centre import SouthbankCentreScraper
from .scrapers.official_london_theatre import OfficialLondonTheatreScraper
from .scrapers.koko import KokoScraper
from .scrapers.roundhouse import RoundhouseScraper
from .scrapers.alexandra_palace import AlexandraPalaceScraper
from .scrapers.eventim_apollo import EventimApolloScraper
from .scrapers.dice import DiceScraper
from .scrapers.resident_advisor import ResidentAdvisorScraper


# Registry of all available data sources
# Add new sources here to automatically include them in the system
DATA_SOURCES: List[Type[BaseDataSource]] = [
    TicketmasterSource,
    EventbriteSource,
    SeatGeekSource,
    TimeOutLondonScraper,
    O2ArenaScraper,
    RoyalAlbertHallScraper,
    BarbicanScraper,
    SouthbankCentreScraper,
    OfficialLondonTheatreScraper,
    KokoScraper,
    RoundhouseScraper,
    AlexandraPalaceScraper,
    EventimApolloScraper,
    DiceScraper,
    ResidentAdvisorScraper,
]


def get_all_sources() -> List[BaseDataSource]:
    """
    Get instances of all registered data sources.

    Returns:
        List of instantiated data source objects
    """
    return [source_class() for source_class in DATA_SOURCES]


def get_enabled_sources() -> List[BaseDataSource]:
    """
    Get only enabled data sources.

    Returns:
        List of enabled data source instances
    """
    return [source for source in get_all_sources() if source.is_enabled()]


def get_source_by_name(name: str) -> BaseDataSource:
    """
    Get a specific data source by name.

    Args:
        name: Name of the data source

    Returns:
        Data source instance

    Raises:
        ValueError: If source not found
    """
    for source in get_all_sources():
        if source.name == name:
            return source
    raise ValueError(f"Data source '{name}' not found")


__all__ = [
    'BaseDataSource',
    'DATA_SOURCES',
    'get_all_sources',
    'get_enabled_sources',
    'get_source_by_name',
]
