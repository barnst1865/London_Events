"""Web scraping data sources."""
from .base_scraper import BaseScraper
from .timeout_london import TimeOutLondonScraper

__all__ = ['BaseScraper', 'TimeOutLondonScraper']
