import logging
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

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = f"{self.SEARCH_URL}?term={quote_plus(query)}"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://weworkremotely.com/",
        }

        try:
            self.sleep(1.0, 2.5)
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("We Work Remotely request failed: %s", exc)
            raise

        soup = BeautifulSoup(response.content, "lxml")

        # Job listings live inside <section class="jobs"> as <article class="feature">
        job_items = (
            soup.select("section.jobs > ul > li:not(.view-all)")
            or soup.select("ul.jobs-container li.feature")
            or soup.select("article.feature")
        )

        logger.info("We Work Remotely: found %d listings", len(job_items))

        for item in job_items[:max_results]:
            try:
                title_el = item.select_one("span.title")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    # Fallback: any anchor text
                    anchor = item.select_one("a")
                    if anchor:
                        title = anchor.get_text(" ", strip=True).split("\n")[0].strip()
                if not title:
                    continue

                anchor = item.select_one("a[href*='/remote-jobs/']")
                link = ""
                if anchor:
                    href = anchor.get("href", "")
                    link = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                company_el = item.select_one("span.company")
                company = company_el.get_text(strip=True) if company_el else ""

                region_el = item.select_one("span.region, span.location")
                location_str = region_el.get_text(strip=True) if region_el else "Remote"

                date_el = item.select_one("time")
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
