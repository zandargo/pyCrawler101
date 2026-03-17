import logging
from typing import List
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class DailyRemoteScraper(BaseScraper):
    """
    requests + BeautifulSoup scraper for DailyRemote job listings.
    URL: https://dailyremote.com/remote-jobs?q={query}
    """

    SOURCE = "DailyRemote"
    BASE_URL = "https://dailyremote.com"
    SEARCH_URL = "https://dailyremote.com/remote-jobs"

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = f"{self.SEARCH_URL}?q={quote_plus(query)}"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://dailyremote.com/",
        }

        try:
            self.sleep(1.0, 2.5)
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("DailyRemote request failed: %s", exc)
            raise

        soup = BeautifulSoup(response.content, "lxml")

        job_items = (
            soup.select("article.card")
            or soup.select("div[class*='job-card']")
            or soup.select("div.card[class*='job']")
            or soup.select("[class*='JobCard']")
            or soup.select("li.job-listing")
            or soup.select("div.job")
        )

        logger.info("DailyRemote: found %d listings", len(job_items))

        for item in job_items[:max_results]:
            try:
                title_el = item.select_one("h2 a, h3 a, a[class*='title'], .card-title a")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    h_tag = item.select_one("h2, h3")
                    title = h_tag.get_text(strip=True) if h_tag else ""
                if not title:
                    continue

                link = ""
                if title_el:
                    href = title_el.get("href", "")
                    link = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                company_el = item.select_one(
                    "[class*='company'], [class*='employer'], .card-subtitle, cite"
                )
                company = company_el.get_text(strip=True) if company_el else ""

                date_el = item.select_one("time, [class*='date'], [class*='posted']")
                date_posted = ""
                if date_el:
                    date_posted = date_el.get("datetime", date_el.get_text(strip=True))[:10]

                desc_el = item.select_one("p, [class*='desc'], [class*='summary']")
                description = desc_el.get_text(strip=True) if desc_el else ""

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
                logger.debug("DailyRemote: error parsing item – %s", exc)
                continue

        return jobs
