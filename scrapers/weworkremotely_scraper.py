import logging
import random
import time
from typing import List
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class WeWorkRemotelyScraper(BaseScraper):
    """
    requests + BeautifulSoup scraper for We Work Remotely.
    URL: https://weworkremotely.com/remote-jobs/search?term={query}
    """

    SOURCE = "We Work Remotely"
    BASE_URL = "https://weworkremotely.com"
    SEARCH_URL = "https://weworkremotely.com/remote-jobs/search"
    SEARCH_URL_ALT = "https://weworkremotely.com/remote-jobs"

    def _request_with_retry(self, url: str, headers: dict, max_attempts: int = 3) -> requests.Response | None:
        for attempt in range(1, max_attempts + 1):
            try:
                self.sleep(0.8, 1.8)
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code in (403, 429):
                    if attempt == max_attempts:
                        logger.warning("We Work Remotely blocked request (%s) for %s", response.status_code, url)
                        return None
                    backoff = min(2 ** attempt, 8) + random.uniform(0.2, 1.0)
                    time.sleep(backoff)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                if attempt == max_attempts:
                    logger.warning("We Work Remotely request failed for %s: %s", url, exc)
                    return None
                backoff = min(2 ** attempt, 8) + random.uniform(0.2, 1.0)
                time.sleep(backoff)

        return None

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://weworkremotely.com/",
        }

        search_url = f"{self.SEARCH_URL}?term={quote_plus(query)}"
        search_url_alt = f"{self.SEARCH_URL_ALT}/search?term={quote_plus(query)}"
        fallback_url = self.SEARCH_URL_ALT

        response = (
            self._request_with_retry(search_url, headers)
            or self._request_with_retry(search_url_alt, headers)
            or self._request_with_retry(fallback_url, headers)
        )
        if response is None:
            return jobs

        soup = BeautifulSoup(response.content, "lxml")

        # Job listings live inside <section class="jobs"> as <article class="feature">
        job_items = (
            soup.select("section.jobs > ul > li:not(.view-all)")
            or soup.select("ul.jobs-container li.feature")
            or soup.select("article.feature")
            or soup.select("a[href*='/remote-jobs/']")
        )

        logger.info("We Work Remotely: found %d listings", len(job_items))

        for item in job_items[:max_results]:
            try:
                title_el = item.select_one("span.title") if hasattr(item, "select_one") else None
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    # Fallback: any anchor text
                    anchor = item if getattr(item, "name", "") == "a" else item.select_one("a")
                    if anchor:
                        title = anchor.get_text(" ", strip=True).split("\n")[0].strip()
                if not title:
                    continue

                anchor = item if getattr(item, "name", "") == "a" else item.select_one("a[href*='/remote-jobs/']")
                link = ""
                if anchor:
                    href = anchor.get("href", "")
                    link = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                if "/remote-jobs/" not in link:
                    continue

                company_el = item.select_one("span.company") if hasattr(item, "select_one") else None
                company = company_el.get_text(strip=True) if company_el else ""

                region_el = item.select_one("span.region, span.location") if hasattr(item, "select_one") else None
                location_str = region_el.get_text(strip=True) if region_el else "Remote"

                date_el = item.select_one("time") if hasattr(item, "select_one") else None
                date_posted = date_el.get("datetime", "")[:10] if date_el else ""

                jobs.append(
                    JobPost(
                        title=title,
                        company=company,
                        location=location_str or "Remote",
                        description="",
                        date_posted=date_posted,
                        date_accessed=self.date_accessed,
                        source=self.SOURCE,
                        link=link,
                    )
                )
            except Exception as exc:
                logger.debug("We Work Remotely: error parsing item – %s", exc)
                continue

        return jobs
