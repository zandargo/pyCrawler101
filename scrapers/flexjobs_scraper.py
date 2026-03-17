import logging
from typing import List
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

try:
    from playwright_stealth import Stealth as _Stealth
    _STEALTH = _Stealth()
    _HAS_STEALTH = True
except ImportError:
    _STEALTH = None
    _HAS_STEALTH = False

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class FlexJobsScraper(BaseScraper):
    """
    Playwright-based scraper for FlexJobs public search results.
    Note: FlexJobs is a paid service; only publicly visible teasers are scraped.
    URL: https://www.flexjobs.com/search?search={query}&location=
    """

    SOURCE = "FlexJobs"
    BASE_URL = "https://www.flexjobs.com"
    SEARCH_URL = "https://www.flexjobs.com/search"

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = f"{self.SEARCH_URL}?search={quote_plus(query)}&location="

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
                logger.error("FlexJobs: page load timed out for %s", url)
                browser.close()
                return jobs

            self.sleep(2, 4)

            # Dismiss modals / cookie banners
            for selector in [
                "button:has-text('Accept')",
                "button:has-text('Close')",
                "[class*='modal'] button",
                "#onetrust-accept-btn-handler",
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2_000):
                        btn.click()
                        self.sleep(0.8, 1.5)
                        break
                except Exception:
                    pass

            CARD_SELECTORS = [
                "li[data-job-id]",
                "[data-testid='job-result']",
                "article.job",
                "[class*='job-list-item']",
                "li[class*='job']",
                "#job-list li",
            ]

            card_locator = None
            for sel in CARD_SELECTORS:
                loc = page.locator(sel)
                if loc.count() > 0:
                    card_locator = loc
                    logger.info("FlexJobs: using selector '%s'", sel)
                    break

            if card_locator is None:
                logger.warning("FlexJobs: no job cards found on %s", url)
                browser.close()
                return jobs

            cards = card_locator.all()
            logger.info("FlexJobs: found %d cards", len(cards))

            for card in cards[:max_results]:
                try:
                    title_el = card.locator("h2 a, h3 a, a[class*='title'], [class*='job-title'] a")
                    title = self._safe_text(title_el)
                    if not title:
                        continue

                    link = self._safe_attr(title_el, "href")
                    if link and not link.startswith("http"):
                        link = f"{self.BASE_URL}{link}"

                    company_el = card.locator("[class*='company'], [class*='employer'], [data-testid='company']")
                    company = self._safe_text(company_el)

                    location_el = card.locator("[class*='location'], [class*='schedule']")
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
                    logger.debug("FlexJobs: error parsing card – %s", exc)
                    continue

            browser.close()

        return jobs
