import logging
from typing import List
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class CadCrowdScraper(BaseScraper):
    """
    requests + BeautifulSoup scraper for Cad Crowd freelance job listings.
    URL: https://www.cadcrowd.com/projects
    Focused on CAD, engineering design, and related technical roles.
    """

    SOURCE = "Cad Crowd"
    BASE_URL = "https://www.cadcrowd.com"
    SEARCH_URL = "https://www.cadcrowd.com/projects"

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = self.SEARCH_URL

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.cadcrowd.com/",
        }

        try:
            self.sleep(1.0, 2.5)
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Cad Crowd request failed: %s", exc)
            return jobs

        soup = BeautifulSoup(response.content, "lxml")

        # Cad Crowd currently exposes contests/projects cards rather than a direct
        # keyword search endpoint. Parse contest links and filter by query locally.
        job_items = soup.select("a[href*='/contest/']")

        logger.info("Cad Crowd: found %d listings", len(job_items))

        q_tokens = [tok for tok in query.lower().split() if tok]

        for item in job_items:
            if len(jobs) >= max_results:
                break
            try:
                href = item.get("href", "")
                if "/contest/" not in href:
                    continue

                title = item.get_text(" ", strip=True)
                if not title:
                    continue

                if q_tokens and not any(tok in title.lower() for tok in q_tokens):
                    continue

                link = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                container = item.find_parent(["li", "article", "div"]) or item
                desc_el = container.select_one("p") if hasattr(container, "select_one") else None
                description = desc_el.get_text(" ", strip=True) if desc_el else ""

                company = "Cad Crowd Client"

                date_el = container.select_one("time, [class*='date'], [class*='posted']") if hasattr(container, "select_one") else None
                date_posted = ""
                if date_el:
                    date_posted = date_el.get("datetime", date_el.get_text(strip=True))[:10]

                jobs.append(
                    JobPost(
                        title=title,
                        company=company,
                        location="Remote",
                        description=description,
                        date_posted=date_posted,
                        date_accessed=self.date_accessed,
                        source=self.SOURCE,
                        link=link,
                    )
                )
            except Exception as exc:
                logger.debug("Cad Crowd: error parsing item – %s", exc)
                continue

        return jobs
