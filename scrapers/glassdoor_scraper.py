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
    logging.getLogger(__name__).warning(
        "playwright-stealth not found; scraping without stealth mode."
    )

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class GlassdoorScraper(BaseScraper):
    """
    Playwright-based scraper for Glassdoor Brasil (glassdoor.com.br).
    Uses stealth mode to reduce bot-detection fingerprints.

    NOTE: Glassdoor may display a sign-in modal; this scraper attempts
    to dismiss it automatically. Rate-limit politely.
    """

    SOURCE = "Glassdoor"
    BASE_URL = "https://www.glassdoor.com.br/Vaga/vagas.htm"

    # Selectors – Glassdoor's React SPA; may need periodic updates
    _CARD_SELECTORS = [
        'li[data-test="jobListing"]',
        "li.react-job-listing",
        '[data-id="job-listing-item"]',
    ]

    def scrape(
        self,
        query: str,
        location: str,
        max_results: int = 20,
    ) -> List[JobPost]:
        jobs: List[JobPost] = []

        url = (
            f"{self.BASE_URL}"
            f"?sc.keyword={quote_plus(query)}"
            f"&locKeyword={quote_plus(location)}"
            f"&sortBy=date_desc"
        )

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
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                viewport={"width": 1366, "height": 768},
                extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"},
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
                logger.error("Glassdoor: page load timed out for %s", url)
                browser.close()
                return jobs

            self.sleep(2, 4)

            # Dismiss sign-in / cookie modals
            for selector in [
                'button[data-test="modal-exit"]',
                "button.modal_closeIcon",
                'button[alt="Fechar"]',
                "button:has-text('Fechar')",
                "button:has-text('Close')",
                "#onetrust-accept-btn-handler",
                "button:has-text('Aceitar')",
                "button:has-text('Accept')",
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2_000):
                        btn.click()
                        self.sleep(0.8, 1.5)
                        break
                except Exception:
                    pass

            # Locate job cards
            card_locator = None
            for sel in self._CARD_SELECTORS:
                loc = page.locator(sel)
                if loc.count() > 0:
                    card_locator = loc
                    logger.info("Glassdoor: using card selector '%s'", sel)
                    break

            if card_locator is None:
                logger.warning("Glassdoor: no job cards found on %s", url)
                browser.close()
                return jobs

            cards = card_locator.all()
            logger.info("Glassdoor: found %d cards", len(cards))

            for card in cards[:max_results]:
                try:
                    title_el = card.locator(
                        '[data-test="job-title"], .jobTitle, a[data-test="job-title"]'
                    )
                    title = self._safe_text(title_el)
                    if not title:
                        continue

                    link = self._safe_attr(title_el, "href")
                    if link and not link.startswith("http"):
                        link = f"https://www.glassdoor.com.br{link}"

                    company = self._safe_text(
                        card.locator(
                            '[data-test="employer-name"], .employerName, [class*="EmployerProfile"]'
                        )
                    )
                    location_text = self._safe_text(
                        card.locator(
                            '[data-test="location"], .location, [class*="location"]'
                        )
                    )
                    date_text = self._safe_text(
                        card.locator(
                            '[data-test="job-age"], .listing-age, [class*="jobAge"]'
                        )
                    )
                    description = self._safe_text(
                        card.locator(
                            '[data-test="job-description"], .jobDescriptionContent, [class*="jobDescription"]'
                        )
                    )

                    jobs.append(
                        JobPost(
                            title=title,
                            company=company,
                            location=location_text,
                            description=description,
                            date_posted=date_text,
                            date_accessed=self.date_accessed,
                            source=self.SOURCE,
                            link=link,
                        )
                    )
                except Exception as exc:
                    logger.warning("Glassdoor: error parsing card – %s", exc)

            browser.close()

        return jobs
