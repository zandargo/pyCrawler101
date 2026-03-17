import logging
from typing import List

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class VagasScraper(BaseScraper):
    """
    requests + BeautifulSoup scraper for Vagas.com.br.
    Vagas is one of the oldest and largest Brazilian job boards.
    URL pattern: https://www.vagas.com.br/vagas-de-{slug}
    """

    SOURCE = "Vagas.com.br"
    BASE_URL = "https://www.vagas.com.br"

    def scrape(self, query: str, location: str, max_results: int = 20) -> List[JobPost]:
        jobs: List[JobPost] = []

        query_slug = query.strip().lower().replace(" ", "-")
        location_slug = location.strip().lower().replace(" ", "-") if location else ""

        if location_slug:
            url = f"{self.BASE_URL}/vagas-de-{query_slug}-em-{location_slug}"
        else:
            url = f"{self.BASE_URL}/vagas-de-{query_slug}"

        params = {"ordenar": "DataDePublicacao"}

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.vagas.com.br/",
            "DNT": "1",
        }

        try:
            self.sleep(1.0, 2.5)
            response = requests.get(
                url, params=params, headers=headers, timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Vagas.com.br request failed: %s", exc)
            raise

        soup = BeautifulSoup(response.content, "lxml")

        # Multiple selector candidates – Vagas has occasionally changed markup
        job_items = (
            soup.select("li.vaga")
            or soup.select("article.vaga-item")
            or soup.select("[class*='vaga']")
        )

        logger.info("Vagas.com.br: found %d listings", len(job_items))

        for item in job_items[:max_results]:
            try:
                title_el = item.select_one("h2.cargo a, h2 a, .vaga-titulo a, h3 a")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                link_href = title_el.get("href", "") if title_el else ""
                if link_href and not link_href.startswith("http"):
                    link_href = f"{self.BASE_URL}{link_href}"

                company_el = item.select_one(
                    ".emprVaga span, .empresa, .company-name, [class*='empresa']"
                )
                company = company_el.get_text(strip=True) if company_el else ""

                location_el = item.select_one(
                    ".localidade, .cidade, [class*='localidade'], [class*='cidade']"
                )
                location_text = (
                    location_el.get_text(strip=True) if location_el else location
                )

                date_el = item.select_one(
                    ".data-publicacao, time, [class*='data'], .date"
                )
                if date_el:
                    date_text = date_el.get("datetime") or date_el.get_text(strip=True)
                else:
                    date_text = ""

                desc_el = item.select_one(
                    ".detalhes-conteudo, .job-description-short, "
                    "[class*='descricao'], [class*='detalhe'] p"
                )
                description = desc_el.get_text(strip=True) if desc_el else ""

                jobs.append(
                    JobPost(
                        title=title,
                        company=company,
                        location=location_text,
                        description=description,
                        date_posted=date_text,
                        date_accessed=self.date_accessed,
                        source=self.SOURCE,
                        link=link_href,
                    )
                )
            except Exception as exc:
                logger.warning("Vagas.com.br: error parsing item – %s", exc)

        return jobs
