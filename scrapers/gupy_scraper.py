import re
import logging
from typing import List

import requests

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class GupyScraper(BaseScraper):
    """
    Scraper for Gupy.io using their public REST API.
    Gupy is one of the most popular ATS/job boards in Brazil.
    API endpoint: https://portal.api.gupy.io/api/job
    """

    SOURCE = "Gupy"
    API_URL = "https://portal.api.gupy.io/api/job"
    PAGE_SIZE = 10  # Gupy API max per page

    def scrape(self, query: str, location: str, max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []
        offset = 0

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://portal.gupy.io/",
            "Origin": "https://portal.gupy.io",
        }

        while len(jobs) < max_results:
            params: dict = {
            "name": query,
                "offset": offset,
            }
            if location:
                params["city"] = location

            try:
                self.sleep(0.5, 1.5)
                response = requests.get(
                    self.API_URL,
                    params=params,
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                logger.error("Gupy API request failed: %s", exc)
                raise

            job_list = data.get("data", [])
            if not job_list:
                break

            for raw in job_list:
                if len(jobs) >= max_results:
                    break

                city = raw.get("city") or ""
                state = raw.get("state") or ""
                loc_parts = [p for p in (city, state) if p]
                location_str = ", ".join(loc_parts)

                published = raw.get("publishedDate") or ""
                date_posted = published[:10] if published else ""

                jobs.append(
                    JobPost(
                        title=raw.get("name") or "",
                        company=raw.get("careerPageName") or "",
                        location=location_str,
                        description=self._strip_html(raw.get("description") or ""),
                        date_posted=date_posted,
                        date_accessed=self.date_accessed,
                        source=self.SOURCE,
                        link=raw.get("jobUrl") or "",
                    )
                )

            pagination = data.get("pagination", {})
            total = pagination.get("total", 0)
            if offset + self.PAGE_SIZE >= total or len(job_list) < self.PAGE_SIZE:
                break

            offset += self.PAGE_SIZE

        return jobs

    # ------------------------------------------------------------------
    @staticmethod
    def _strip_html(html: str) -> str:
        """Remove HTML tags and collapse whitespace."""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
