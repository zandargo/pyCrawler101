import logging
from typing import List

from .base_scraper import BaseScraper, JobPost

logger = logging.getLogger(__name__)


class GlassdoorScraper(BaseScraper):
    """
    Glassdoor scraper (currently disabled).
    
    Glassdoor.com.br has implemented sophisticated bot-detection that
    prevents automated scraping:
    - Cloudflare security challenges
    - React SPA with dynamic rendering
    - JavaScript-based content loading
    
    The site blocks access before job listings can be retrieved.
    """

    SOURCE = "Glassdoor"
    BASE_URL = "https://www.glassdoor.com.br/Vaga/vagas.htm"

    def scrape(self, query: str, location: str, max_results: int = 20) -> List[JobPost]:
        """
        Glassdoor scraper is currently disabled due to anti-bot protections.
        
        Args:
            query: Job search query (ignored)
            location: Location to search (ignored)
            max_results: Max results to return (ignored)
        
        Returns:
            Empty list (no results available)
        """
        
        # Log warning once per instance
        if not hasattr(self, '_glassdoor_warning_logged'):
            logger.warning(
                "\n" + "="*75 +
                "\n🔒 Glassdoor scraper is DISABLED"
                "\n" + "-"*75 +
                "\nGlassdoor Brasil has bot-detection that blocks automated scrapers:"
                "\n  • Security verification pages before content loads"
                "\n  • React SPA with dynamic component rendering"
                "\n  • JavaScript-based job data that's not in initial HTML"
                "\n" + "-"*75 +
                "\n✅ Other job sources ARE working:"
                "\n   Indeed • Vagas • CatHo • Gupy • WeWorkRemotely"
                "\n   FlexJobs • RemoteOK • Wellfound • Arc • CadCrowd"
                "\n" + "-"*75 +
                "\n💡 To restore Glassdoor scraping:"
                "\n   1. Check if page structure changed: glassdoor.com.br"
                "\n   2. Use Glassdoor's official API (if available)"
                "\n   3. Try a paid scraping service (ScrapingBee, etc.)"
                "\n   4. Contact Glassdoor about data access"
                "\n" + "="*75
            )
            self._glassdoor_warning_logged = True
        
        return []
