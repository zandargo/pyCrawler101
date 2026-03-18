from .base_scraper import BaseScraper, JobPost
from .gupy_scraper import GupyScraper
from .indeed_scraper import IndeedScraper
from .vagas_scraper import VagasScraper
from .catho_scraper import CathoScraper
from .glassdoor_scraper import GlassdoorScraper
from .weworkremotely_scraper import WeWorkRemotelyScraper
from .remoteok_scraper import RemoteOKScraper
from .arc_scraper import ArcScraper
from .flexjobs_scraper import FlexJobsScraper
from .cadcrowd_scraper import CadCrowdScraper
from .wellfound_scraper import WellfoundScraper
from .dailyremote_scraper import DailyRemoteScraper
from .linkedin_scraper import LinkedInScraper

__all__ = [
    "BaseScraper",
    "JobPost",
    "GupyScraper",
    "IndeedScraper",
    "VagasScraper",
    "CathoScraper",
    "GlassdoorScraper",
    "WeWorkRemotelyScraper",
    "RemoteOKScraper",
    "ArcScraper",
    "FlexJobsScraper",
    "CadCrowdScraper",
    "WellfoundScraper",
    "DailyRemoteScraper",
    "LinkedInScraper",
]
