import logging
from typing import List
from urllib.parse import quote_plus

import requests

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class RemoteOKScraper(BaseScraper):
    """
    Scraper for Remote OK using their public JSON API.
    API docs: https://remoteok.com/api
    """

    SOURCE = "Remote OK"
    API_URL = "https://remoteok.com/api"

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        # Tag-based filtering is the cleanest approach for their API
        params = {"tag": query}

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://remoteok.com/",
        }

        try:
            self.sleep(1.0, 2.5)
            response = requests.get(self.API_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.error("Remote OK request failed: %s", exc)
            raise
        except ValueError as exc:
            logger.error("Remote OK JSON parse error: %s", exc)
            raise

        # First element is a legal notice object; job objects follow
        job_list = [item for item in data if isinstance(item, dict) and item.get("id")]

        # Filter by query text (API tag param is case-sensitive; do a fallback text filter)
        q_lower = query.lower()
        filtered = [
            j for j in job_list
            if q_lower in (j.get("position") or "").lower()
            or q_lower in " ".join(j.get("tags") or []).lower()
            or q_lower in (j.get("description") or "").lower()
        ] or job_list  # fall back to all results if filter removes everything

        logger.info("Remote OK: %d jobs from API, %d after filter", len(job_list), len(filtered))

        for raw in filtered[:max_results]:
            try:
                title = raw.get("position") or ""
                if not title:
                    continue

                company = raw.get("company") or ""
                location_str = raw.get("location") or "Remote"
                link = raw.get("url") or f"https://remoteok.com/remote-jobs/{raw.get('id', '')}"
                date_posted = (raw.get("date") or "")[:10]
                description = raw.get("description") or ""
                # Strip basic HTML tags from description
                description = self._strip_html(description)

                jobs.append(
                    JobPost(
                        title=title,
                        company=company,
                        location=location_str,
                        description=description[:500],
                        date_posted=date_posted,
                        date_accessed=self.date_accessed,
                        source=self.SOURCE,
                        link=link,
                    )
                )
            except Exception as exc:
                logger.debug("Remote OK: error parsing item – %s", exc)
                continue

        return jobs
