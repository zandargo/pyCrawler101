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


class WellfoundScraper(BaseScraper):
    """
    Playwright-based scraper for Wellfound (formerly AngelList Talent).
    URL: https://wellfound.com/jobs?q={query}&remote=true
    """

    SOURCE = "Wellfound"
    BASE_URL = "https://wellfound.com"
    SEARCH_URL = "https://wellfound.com/jobs"

    def scrape(self, query: str, location: str = "", max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = f"{self.SEARCH_URL}?q={quote_plus(query)}&remote=true"

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
                logger.error("Wellfound: page load timed out for %s", url)
                browser.close()
                return jobs

            self.sleep(3, 5)

            # Dismiss modals / sign-up prompts
            for selector in [
                "button:has-text('Close')",
                "button:has-text('Dismiss')",
                "[aria-label='Close']",
                "[aria-label='Dismiss']",
                "button:has-text('Accept')",
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
                "[data-test='StartupResult']",
                "div[class*='JobListing']",
                "div[class*='job-listing']",
                "a[class*='job-name']",
                "[class*='styles_component']",
                "[data-cy='job-listing-item']",
            ]

            card_locator = None
            for sel in CARD_SELECTORS:
                loc = page.locator(sel)
                if loc.count() > 0:
                    card_locator = loc
                    logger.info("Wellfound: using selector '%s'", sel)
                    break

            if card_locator is None:
                logger.warning("Wellfound: no job cards found on %s", url)
                browser.close()
                return jobs

            cards = card_locator.all()
            logger.info("Wellfound: found %d cards", len(cards))

            for card in cards[:max_results]:
                try:
                    title_el = card.locator("h2, h3, [class*='title'], [class*='role'], [class*='position']")
                    title = self._safe_text(title_el)
                    if not title:
                        continue

                    link_el = card.locator("a").first
                    link = self._safe_attr(link_el, "href")
                    if link and link.startswith("/"):
                        link = f"{self.BASE_URL}{link}"

                    company_el = card.locator("[class*='company'], [class*='startup'], h4")
                    company = self._safe_text(company_el)

                    location_el = card.locator("[class*='location'], [class*='remote']")
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
                    logger.debug("Wellfound: error parsing card – %s", exc)
                    continue

            browser.close()

        return jobs
