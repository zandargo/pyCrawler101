import logging
from typing import List
from urllib.parse import quote

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


class CathoScraper(BaseScraper):
    """
    Playwright-based scraper for Catho.com.br.
    Catho is a major paid job board in Brazil.
    URL: https://www.catho.com.br/vagas/{query}/{location}/
    """

    SOURCE = "Catho"
    BASE_URL = "https://www.catho.com.br/vagas"

    def scrape(self, query: str, location: str, max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        query_slug = quote(query.strip().lower().replace(" ", "-"))
        if location:
            location_slug = quote(location.strip().lower().replace(" ", "-"))
            url = f"{self.BASE_URL}/{query_slug}/{location_slug}/"
        else:
            url = f"{self.BASE_URL}/{query_slug}/"

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
                logger.error("Catho: page load timed out for %s", url)
                browser.close()
                return jobs
            except PlaywrightError as exc:
                logger.warning("Catho: page navigation unavailable for %s (%s)", url, str(exc).splitlines()[0])
                browser.close()
                return jobs

            self.sleep(2, 4)

            # Dismiss cookie banners if present
            for selector in [
                "button:has-text('Aceitar')",
                "button:has-text('Concordar')",
                "[id*='accept'], [id*='cookie'] button",
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2_000):
                        btn.click()
                        self.sleep(0.8, 1.5)
                        break
                except Exception:
                    pass

            # Candidate selectors for Catho job cards
            CARD_SELECTORS = [
                "[data-testid='job-card']",
                "article[class*='JobCard']",
                "li[class*='job-item']",
                "[class*='job-card']",
                "article",
            ]
            card_locator = None
            for sel in CARD_SELECTORS:
                loc = page.locator(sel)
                if loc.count() > 0:
                    card_locator = loc
                    logger.info("Catho: matched cards with selector '%s'", sel)
                    break

            if card_locator is None:
                logger.warning("Catho: no job cards found on %s", url)
                browser.close()
                return jobs

            cards = card_locator.all()
            logger.info("Catho: found %d cards", len(cards))

            for card in cards[:max_results]:
                try:
                    title_el = card.locator("h2 a, h3 a, [class*='title'] a, a[href*='/vagas/']")
                    title = self._safe_text(title_el)
                    if not title:
                        continue

                    link = self._safe_attr(title_el, "href")
                    if link and not link.startswith("http"):
                        link = f"https://www.catho.com.br{link}"

                    company = self._safe_text(
                        card.locator("[class*='company'], [class*='empresa'], [class*='Company']")
                    )
                    location_text = self._safe_text(
                        card.locator("[class*='location'], [class*='cidade'], [class*='Location']")
                    )
                    date_text = self._safe_text(
                        card.locator("time, [class*='date'], [class*='data']")
                    )
                    description = self._safe_text(
                        card.locator("[class*='description'], [class*='descricao'], p")
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
                    logger.warning("Catho: error parsing card – %s", exc)

            browser.close()

        return jobs
