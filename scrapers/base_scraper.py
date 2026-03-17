from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import time
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class JobPost:
    title: str
    company: str
    location: str
    description: str
    date_posted: str
    date_accessed: str
    source: str
    link: str


class BaseScraper(ABC):
    SOURCE = "Unknown"

    USER_AGENTS = [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    ]

    def __init__(self) -> None:
        self.date_accessed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def user_agent(self) -> str:
        return random.choice(self.USER_AGENTS)

    def sleep(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """Polite delay to avoid hammering servers."""
        time.sleep(random.uniform(min_sec, max_sec))

    def _safe_text(self, locator, default: str = "") -> str:
        """Safely get inner text from a Playwright locator."""
        try:
            if locator.count() == 0:
                return default
            return locator.first.inner_text().strip()
        except Exception:
            return default

    def _safe_attr(self, locator, attr: str, default: str = "") -> str:
        """Safely get an attribute from a Playwright locator."""
        try:
            if locator.count() == 0:
                return default
            value = locator.first.get_attribute(attr)
            return value.strip() if value else default
        except Exception:
            return default

    @abstractmethod
    def scrape(
        self, query: str, location: str, max_results: int = 20
    ) -> List[JobPost]:
        """Scrape job posts and return a list of JobPost objects."""
