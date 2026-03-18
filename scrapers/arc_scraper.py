import logging
from typing import List
from urllib.parse import quote_plus

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


class ArcScraper(BaseScraper):
    """
    Playwright-based scraper for Arc.dev remote jobs.
    URL: https://arc.dev/remote-jobs?q={query}
    """

    SOURCE = "Arc.dev"
    BASE_URL = "https://arc.dev"
    SEARCH_URL = "https://arc.dev/remote-jobs"

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = f"{self.SEARCH_URL}?q={quote_plus(query)}"

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
                viewport={"width": 1440, "height": 900},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = context.new_page()

            if _HAS_STEALTH and _STEALTH is not None:
                _STEALTH.apply_stealth_sync(page)
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )

            try:
                page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            except PlaywrightTimeout:
                logger.error("Arc.dev: page load timed out for %s", url)
                browser.close()
                return jobs
            except PlaywrightError as exc:
                logger.warning("Arc.dev: page navigation unavailable for %s (%s)", url, str(exc).splitlines()[0])
                browser.close()
                return jobs

            self.sleep(3, 5)

            CARD_SELECTORS = [
                "[data-testid='job-card']",
                "a[href*='/remote-jobs/']",
                "[class*='JobCard']",
                "[class*='job-card']",
                "[class*='job-listing']",
                "article",
            ]

            card_locator = None
            for sel in CARD_SELECTORS:
                loc = page.locator(sel)
                if loc.count() > 0:
                    card_locator = loc
                    logger.info("Arc.dev: using selector '%s'", sel)
                    break

            if card_locator is None:
                logger.warning("Arc.dev: no job cards found on %s", url)
                browser.close()
                return jobs

            cards = card_locator.all()
            logger.info("Arc.dev: found %d cards", len(cards))

            for card in cards[:max_results]:
                try:
                    title_el = card.locator("h2, h3, [class*='title'], [class*='position']")
                    title = self._safe_text(title_el)
                    if not title:
                        title = self._safe_text(card)
                        if not title:
                            continue

                    link = self._safe_attr(card, "href")
                    if not link:
                        link_el = card.locator("a").first
                        link = self._safe_attr(link_el, "href")
                    if link and link.startswith("/"):
                        link = f"{self.BASE_URL}{link}"

                    company_el = card.locator("[class*='company'], [class*='employer']")
                    company = self._safe_text(company_el)

                    location_el = card.locator("[class*='location'], [class*='region']")
                    location_str = self._safe_text(location_el) or "Remote"

                    jobs.append(
                        JobPost(
                            title=title,
                            company=company,
                            location=location_str,
                            description="",
                            date_posted="",
                            date_accessed=self.date_accessed,
                            source=self.SOURCE,
                            link=link,
                        )
                    )
                except Exception as exc:
                    logger.debug("Arc.dev: error parsing card – %s", exc)
                    continue

            browser.close()

        return jobs
