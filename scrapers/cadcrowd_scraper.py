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
    URL: https://www.cadcrowd.com/freelance-design-jobs/search?query={query}
    Focused on CAD, engineering design, and related technical roles.
    """

    SOURCE = "Cad Crowd"
    BASE_URL = "https://www.cadcrowd.com"
    SEARCH_URL = "https://www.cadcrowd.com/freelance-design-jobs/search"

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = f"{self.SEARCH_URL}?query={quote_plus(query)}"

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
            logger.error("Cad Crowd request failed: %s", exc)
            raise

        soup = BeautifulSoup(response.content, "lxml")

        job_items = (
            soup.select("div.job-listing-item")
            or soup.select("div[class*='job-item']")
            or soup.select("li[class*='job']")
            or soup.select("article[class*='job']")
            or soup.select(".project-list .project-item")
            or soup.select("div.panel")
        )

        logger.info("Cad Crowd: found %d listings", len(job_items))

        for item in job_items[:max_results]:
            try:
                title_el = item.select_one("h2 a, h3 a, a.job-title, a[class*='title']")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    h_tag = item.select_one("h2, h3, h4")
                    title = h_tag.get_text(strip=True) if h_tag else ""
                if not title:
                    continue

                link = ""
                if title_el:
                    href = title_el.get("href", "")
                    link = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                company_el = item.select_one("[class*='company'], [class*='client'], .posted-by")
                company = company_el.get_text(strip=True) if company_el else ""

                budget_el = item.select_one("[class*='budget'], [class*='price'], [class*='rate']")
                description = budget_el.get_text(strip=True) if budget_el else ""

                date_el = item.select_one("time, [class*='date'], [class*='posted']")
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
