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


class IndeedScraper(BaseScraper):
    """
    Playwright-based scraper for Indeed Brasil (br.indeed.com).
    Uses stealth mode to reduce bot-detection fingerprints.

    NOTE: Respects Indeed's rate limits – one page per session,
    with a polite delay before interacting with the DOM.
    """

    SOURCE = "Indeed Brasil"
    BASE_URL = "https://br.indeed.com/jobs"
    BASE_URL_REMOTE = "https://www.indeed.com/jobs"
    # Indeed's internal remote-job filter GUID
    _REMOTE_PARAM = "032b3046-06a3-4876-8dfd-474eb5e7ed11"

    def scrape(
        self,
        query: str,
        location: str,
        max_results: int = 20,
        remote: bool = False,
    ) -> List[JobPost]:
        jobs: List[JobPost] = []

        if remote:
            base_url = self.BASE_URL_REMOTE
            url = (
                f"{base_url}"
                f"?q={quote_plus(query)}"
                f"&l="
                f"&remotejob={self._REMOTE_PARAM}"
                f"&sort=date"
            )
        else:
            base_url = self.BASE_URL
            url = (
                f"{base_url}"
                f"?q={quote_plus(query)}"
                f"&l={quote_plus(location)}"
                f"&sort=date"
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
            if remote:
                locale = "en-US"
                timezone_id = "America/New_York"
                accept_lang = "en-US,en;q=0.9"
            else:
                locale = "pt-BR"
                timezone_id = "America/Sao_Paulo"
                accept_lang = "pt-BR,pt;q=0.9,en;q=0.8"

            context = browser.new_context(
                user_agent=self.user_agent,
                locale=locale,
                timezone_id=timezone_id,
                viewport={"width": 1366, "height": 768},
                extra_http_headers={"Accept-Language": accept_lang},
            )
            page = context.new_page()

            if _HAS_STEALTH and _STEALTH is not None:
                _STEALTH.apply_stealth_sync(page)

            # Patch navigator.webdriver manually as a safety net
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )

            try:
                page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            except PlaywrightTimeout:
                logger.error("Indeed: page load timed out for %s", url)
                browser.close()
                return jobs

            self.sleep(2, 4)

            # Dismiss cookie / consent banners
            for selector in [
                "button:has-text('Aceitar')",
                "button:has-text('Accept')",
                "#onetrust-accept-btn-handler",
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2_000):
                        btn.click()
                        self.sleep(1, 2)
                        break
                except Exception:
                    pass

            # Job card selectors (Indeed updates these periodically)
            # slider_item  = the visible job card (title, company, location)
            # slider_sub_item = paired sibling with snippet (belowJobSnippet)
            cards = page.locator('[data-testid="slider_item"]').all()
            sub_items = page.locator('[data-testid="slider_sub_item"]').all()

            # Fallback for older Indeed layouts
            if not cards:
                for sel in [".job_seen_beacon", ".result"]:
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        cards = loc.all()
                        break

            if not cards:
                logger.warning("Indeed: no job cards found on %s", url)
                browser.close()
                return jobs

            logger.info("Indeed: found %d cards", len(cards))

            for idx, card in enumerate(cards[:max_results]):
                try:
                    title_el = card.locator(
                        '[data-testid="jobTitle"] a, .jobTitle a, h2 a'
                    )
                    title = self._safe_text(title_el)
                    if not title:
                        continue

                    link = self._safe_attr(title_el, "href")
                    if link and not link.startswith("http"):
                        link_base = "https://www.indeed.com" if remote else "https://br.indeed.com"
                        link = f"{link_base}{link}"

                    company = self._safe_text(
                        card.locator(
                            '[data-testid="company-name"], .companyName'
                        )
                    )
                    location_text = self._safe_text(
                        card.locator(
                            '[data-testid="text-location"], .companyLocation'
                        )
                    )

                    # Description: full content lives in .jobsearch-JobComponent-description.
                    # Collect all matching elements and join with newlines to preserve
                    # internal structure. Search inside the paired slider_sub_item first,
                    # then fall back to the page-level detail panel (auto-opened card),
                    # then to the belowJobSnippet snippet.
                    description = ""
                    _desc_containers = []
                    if idx < len(sub_items):
                        _desc_containers = sub_items[idx].locator(".jobsearch-JobComponent-description").all()
                    if not _desc_containers:
                        _desc_containers = page.locator(".jobsearch-JobComponent-description").all()
                    if _desc_containers:
                        _parts = [el.inner_text().strip() for el in _desc_containers]
                        description = "\n".join(p for p in _parts if p)
                    if not description and idx < len(sub_items):
                        description = self._safe_text(
                            sub_items[idx].locator('[data-testid="belowJobSnippet"]')
                        )
                    # Fallback for legacy layouts where snippet is inside the card
                    if not description:
                        for _desc_sel in [
                            '[data-testid="job-snippet"]',
                            ".job-snippet",
                        ]:
                            description = self._safe_text(card.locator(_desc_sel))
                            if description:
                                break

                    # Date posted: Indeed no longer renders this on listing
                    # cards. Try legacy selectors; value will be empty if absent.
                    date_text = ""
                    for _date_sel in [
                        '[data-testid="myJobsStateDate"]',
                        '[data-testid*="date"]',
                        ".date",
                    ]:
                        date_text = self._safe_text(card.locator(_date_sel))
                        if date_text:
                            break
                    if not date_text and idx < len(sub_items):
                        for _date_sel in [
                            '[data-testid="myJobsStateDate"]',
                            '[data-testid*="date"]',
                            ".date",
                        ]:
                            date_text = self._safe_text(sub_items[idx].locator(_date_sel))
                            if date_text:
                                break

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
                    logger.warning("Indeed: error parsing card – %s", exc)

            browser.close()

        return jobs
