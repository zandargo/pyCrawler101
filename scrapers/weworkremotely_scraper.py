import logging
import random
import time
from typing import List
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Error as PlaywrightError

try:
    from playwright_stealth import Stealth as _Stealth
    _STEALTH = _Stealth()
    _HAS_STEALTH = True
except ImportError:
    _STEALTH = None
    _HAS_STEALTH = False

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
    DETAIL_ENRICH_LIMIT = 6
    DETAIL_ENRICH_BUDGET_SECONDS = 35.0
    DETAIL_PAGE_TIMEOUT_MS = 12_000
    DETAIL_SELECTOR_TIMEOUT_MS = 3_000

    def _get_job_anchor(self, item):
        anchor = item if getattr(item, "name", "") == "a" else item.select_one("a[href*='/remote-jobs/']")
        if anchor is None:
            return None

        href = (anchor.get("href") or "").strip()
        if not href:
            return None

        normalized_href = href
        if normalized_href.startswith(self.BASE_URL):
            normalized_href = normalized_href[len(self.BASE_URL):]

        if not normalized_href.startswith("/remote-jobs/"):
            return None

        if normalized_href.startswith("/remote-jobs/new"):
            return None

        return anchor

    def _get_job_items(self, soup: BeautifulSoup):
        selectors = (
            "section.jobs > ul > li:not(.view-all)",
            "section.jobs li:not(.view-all)",
            "ul.jobs-container li.feature",
            "ul.jobs-container li",
            "article.feature",
            "article",
        )

        for selector in selectors:
            items = [item for item in soup.select(selector) if self._get_job_anchor(item) is not None]
            if items:
                return items

        return []

    @staticmethod
    def _extract_description(item) -> str:
        description_el = item.select_one(".lis-container__job__content__description")
        if description_el:
            return description_el.get_text(" ", strip=True)
        return ""

    @staticmethod
    def _extract_posted_date(item) -> str:
        time_el = item.select_one("time")
        if time_el:
            return (time_el.get("datetime") or time_el.get_text(" ", strip=True)).strip()[:10]

        for meta_item in item.select("li.lis-container__job__sidebar__job-about__list__item"):
            meta_text = meta_item.get_text(" ", strip=True)
            if meta_text.lower().startswith("posted on"):
                posted_span = meta_item.select_one("span")
                if posted_span:
                    return posted_span.get_text(" ", strip=True)
                return meta_text[len("Posted on"):].strip()

        return ""

    def _enrich_jobs_with_playwright(self, jobs: List[JobPost]) -> None:
        jobs_to_enrich = [job for job in jobs if job.link and (not job.description or not job.date_posted)]
        jobs_to_enrich = jobs_to_enrich[: self.DETAIL_ENRICH_LIMIT]
        if not jobs_to_enrich:
            return

        deadline = time.monotonic() + self.DETAIL_ENRICH_BUDGET_SECONDS

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = browser.new_context(
                    user_agent=self.user_agent,
                    locale="en-US",
                    timezone_id="America/New_York",
                    viewport={"width": 1366, "height": 768},
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                page = context.new_page()

                if _HAS_STEALTH and _STEALTH is not None:
                    _STEALTH.apply_stealth_sync(page)
                page.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
                )

                for job in jobs_to_enrich:
                    if time.monotonic() >= deadline:
                        logger.info("We Work Remotely detail enrichment stopped after reaching time budget")
                        break

                    try:
                        remaining_seconds = deadline - time.monotonic()
                        if remaining_seconds <= 0:
                            break

                        page.goto(
                            job.link,
                            timeout=min(self.DETAIL_PAGE_TIMEOUT_MS, int(remaining_seconds * 1000)),
                            wait_until="domcontentloaded",
                        )
                        try:
                            page.wait_for_selector(
                                ".lis-container__job__content__description, li.lis-container__job__sidebar__job-about__list__item",
                                timeout=min(self.DETAIL_SELECTOR_TIMEOUT_MS, max(1, int((deadline - time.monotonic()) * 1000))),
                            )
                        except PlaywrightTimeout:
                            pass
                        self.sleep(0.4, 0.9)

                        soup = BeautifulSoup(page.content(), "lxml")
                        if not job.description:
                            job.description = self._extract_description(soup)
                        if not job.date_posted:
                            job.date_posted = self._extract_posted_date(soup)
                    except PlaywrightTimeout:
                        logger.warning("We Work Remotely detail page timed out for %s", job.link)
                    except PlaywrightError as exc:
                        logger.warning(
                            "We Work Remotely detail page unavailable for %s (%s)",
                            job.link,
                            str(exc).splitlines()[0],
                        )
                    except Exception as exc:
                        logger.warning("We Work Remotely detail page parse failed for %s: %s", job.link, exc)

                browser.close()
        except Exception as exc:
            logger.warning("We Work Remotely Playwright enrichment failed: %s", exc)

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
        job_items = self._get_job_items(soup)

        logger.info("We Work Remotely: found %d listings", len(job_items))

        for item in job_items[:max_results]:
            try:
                title_el = item.select_one("span.title") if hasattr(item, "select_one") else None
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    # Fallback: any anchor text
                    anchor = self._get_job_anchor(item)
                    if anchor:
                        title = anchor.get_text(" ", strip=True).split("\n")[0].strip()
                if not title:
                    continue
                if title.lower().startswith("post a job"):
                    continue

                anchor = self._get_job_anchor(item)
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

                description = self._extract_description(item) if hasattr(item, "select_one") else ""
                date_posted = self._extract_posted_date(item) if hasattr(item, "select_one") else ""

                jobs.append(
                    JobPost(
                        title=title,
                        company=company,
                        location=location_str or "Remote",
                        description=description,
                        date_posted=date_posted,
                        date_accessed=self.date_accessed,
                        source=self.SOURCE,
                        link=link,
                    )
                )
            except Exception as exc:
                logger.debug("We Work Remotely: error parsing item – %s", exc)
                continue

        self._enrich_jobs_with_playwright(jobs)

        return jobs
