import logging
import random
import re
import time
from typing import List

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """
    requests + BeautifulSoup scraper for LinkedIn public jobs endpoint.

    Endpoint:
    https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
    """

    SOURCE = "LinkedIn"
    SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    JOB_DETAILS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    PAGE_SIZE = 25

    def _request_with_retry(
        self,
        url: str,
        headers: dict,
        params: dict | None = None,
        timeout: int = 30,
        max_attempts: int = 4,
    ) -> requests.Response:
        """HTTP GET with retry/backoff for transient LinkedIn failures."""
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                self.sleep(0.8, 1.8)
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )

                # LinkedIn may throttle with 429 or temporary 5xx responses.
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == max_attempts:
                        response.raise_for_status()
                    wait_seconds = min(2 ** attempt, 12) + random.uniform(0.2, 1.0)
                    logger.warning(
                        "LinkedIn transient status %s on attempt %d/%d; backing off %.1fs",
                        response.status_code,
                        attempt,
                        max_attempts,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue

                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt == max_attempts:
                    break
                wait_seconds = min(2 ** attempt, 12) + random.uniform(0.2, 1.0)
                logger.warning(
                    "LinkedIn request error on attempt %d/%d: %s; backing off %.1fs",
                    attempt,
                    max_attempts,
                    exc,
                    wait_seconds,
                )
                time.sleep(wait_seconds)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("LinkedIn request failed without exception details")

    @staticmethod
    def _extract_job_id(link: str) -> str:
        """Extract LinkedIn numeric job id from a job URL."""
        if not link:
            return ""

        patterns = [
            r"/jobs/view/(\d+)",
            r"-([0-9]{7,})(?:[/?]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _normalize_multiline_text(text: str) -> str:
        """Normalize whitespace while preserving meaningful line breaks."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Clean per-line noise but keep paragraph/list separation.
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

        compact_lines: List[str] = []
        previous_blank = False
        for line in lines:
            if not line:
                if not previous_blank:
                    compact_lines.append("")
                previous_blank = True
                continue
            compact_lines.append(line)
            previous_blank = False

        return "\n".join(compact_lines).strip()

    def _fetch_job_description(self, job_id: str, headers: dict) -> str:
        """Fetch and parse detailed job description from LinkedIn guest endpoint."""
        if not job_id:
            return ""

        details_url = self.JOB_DETAILS_URL.format(job_id=job_id)

        try:
            response = self._request_with_retry(details_url, headers=headers, params=None, timeout=30)
        except requests.RequestException as exc:
            logger.debug("LinkedIn details request failed for job_id=%s: %s", job_id, exc)
            return ""

        soup = BeautifulSoup(response.text, "lxml")
        desc_el = (
            soup.select_one("div.show-more-less-html__markup")
            or soup.select_one("section.show-more-less-html")
            or soup.select_one("div.description__text")
        )
        if not desc_el:
            return ""

        for br in desc_el.select("br"):
            br.replace_with("\n")

        description_raw = desc_el.get_text("\n", strip=True)
        description = self._normalize_multiline_text(description_raw)
        return description[:3000]

    def scrape(
        self,
        query: str,
        location: str = "",
        max_results: int = 20,
        remote: bool = False,
        fetch_description: bool = False,
    ) -> List[JobPost]:
        jobs: List[JobPost] = []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.linkedin.com/jobs/",
        }

        params = {
            "keywords": query,
        }

        if remote:
            # LinkedIn workplace filter: 2 = Remote.
            params["f_WT"] = "2"
        elif location.strip():
            params["location"] = location.strip()

        start = 0
        max_pages = max(1, (max_results // self.PAGE_SIZE) + 2)

        for _ in range(max_pages):
            if len(jobs) >= max_results:
                break

            params["start"] = str(start)

            try:
                response = self._request_with_retry(
                    self.SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=30,
                )
            except requests.RequestException as exc:
                logger.error("LinkedIn request failed (start=%s): %s", start, exc)
                break

            soup = BeautifulSoup(response.text, "lxml")
            cards = soup.select("li")

            if not cards:
                logger.info("LinkedIn: no cards found at start=%d", start)
                break

            page_added = 0
            for card in cards:
                if len(jobs) >= max_results:
                    break

                try:
                    title_el = card.select_one("h3.base-search-card__title")
                    title = title_el.get_text(" ", strip=True) if title_el else ""
                    if not title:
                        continue

                    company_el = card.select_one(
                        "h4.base-search-card__subtitle a, h4.base-search-card__subtitle"
                    )
                    company = company_el.get_text(" ", strip=True) if company_el else ""

                    location_el = card.select_one("span.job-search-card__location")
                    location_str = location_el.get_text(" ", strip=True) if location_el else ""
                    if remote and not location_str:
                        location_str = "Remote"

                    link_el = card.select_one("a.base-card__full-link")
                    link = ""
                    if link_el:
                        link = (link_el.get("href") or "").strip()

                    time_el = card.select_one("time")
                    date_posted = ""
                    if time_el:
                        date_posted = (time_el.get("datetime") or time_el.get_text(" ", strip=True)).strip()

                    description = ""
                    if fetch_description:
                        job_id = self._extract_job_id(link)
                        description = self._fetch_job_description(job_id, headers)

                    jobs.append(
                        JobPost(
                            title=title,
                            company=company,
                            location=location_str,
                            description=description,
                            date_posted=date_posted,
                            date_accessed=self.date_accessed,
                            source=self.SOURCE,
                            link=link,
                        )
                    )
                    page_added += 1
                except Exception as exc:
                    logger.debug("LinkedIn: error parsing card at start=%d: %s", start, exc)
                    continue

            logger.info("LinkedIn: added %d jobs from start=%d", page_added, start)

            if page_added == 0:
                break

            start += self.PAGE_SIZE

        return jobs[:max_results]
