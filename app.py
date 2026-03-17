"""
Brazil Job Crawler — Streamlit interface
Run: streamlit run app.py
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import sys
from datetime import datetime

# On Windows, set the ProactorEventLoop policy at process startup so that
# every new event loop (including those created internally by Playwright's
# sync_playwright) uses ProactorEventLoop, which supports subprocess creation.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import pandas as pd
import streamlit as st

from scrapers import CathoScraper, GupyScraper, IndeedScraper, JobPost, VagasScraper
from utils.export import export_to_excel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config  (must be the very first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MG Job Crawler",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
/* ── Global ─────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1426 0%, #141E36 100%);
    border-right: 1px solid rgba(78, 205, 196, 0.18);
}
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stCheckbox label,
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #CBD5E1 !important;
}
[data-testid="stSidebar"] hr { border-color: rgba(78,205,196,0.2); }

/* ── Search button ───────────────────────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stButton"] > button,
[data-testid="stSidebar"] button[kind="primary"] {
    background: linear-gradient(135deg, #4ECDC4 0%, #A855F7 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 1.2rem !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 15px rgba(78, 205, 196, 0.25) !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(78, 205, 196, 0.45) !important;
}

/* ── Header card ─────────────────────────────────────────────────────────── */
.hero-header {
    background: linear-gradient(135deg, #0D1426 0%, #1A2744 100%);
    border: 1px solid rgba(78, 205, 196, 0.25);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.8rem;
    text-align: center;
}
.hero-header h1 {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(90deg, #4ECDC4 0%, #A855F7 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.4rem 0;
}
.hero-header p {
    color: #8892A4;
    font-size: 1rem;
    margin: 0;
}

/* ── Metric cards ────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: rgba(78, 205, 196, 0.07);
    border: 1px solid rgba(78, 205, 196, 0.25);
    border-radius: 12px;
    padding: 0.8rem 1.2rem;
}
[data-testid="metric-container"] label { color: #8892A4 !important; }

/* ── Section titles ──────────────────────────────────────────────────────── */
.section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #4ECDC4;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin: 1.2rem 0 0.6rem 0;
    border-left: 3px solid #4ECDC4;
    padding-left: 0.6rem;
}

/* ── Source badge chips ──────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 0.18rem 0.65rem;
    border-radius: 20px;
    font-size: 0.74rem;
    font-weight: 600;
    margin: 2px;
}
.badge-gupy    { background: rgba(0,122,255,0.15); color:#60A5FA; border:1px solid rgba(0,122,255,0.3); }
.badge-indeed  { background: rgba(37,99,235,0.15); color:#818CF8; border:1px solid rgba(37,99,235,0.3); }
.badge-vagas   { background: rgba(220,38,38,0.15); color:#F87171; border:1px solid rgba(220,38,38,0.3); }
.badge-catho   { background: rgba(234,88,12,0.15); color:#FB923C; border:1px solid rgba(234,88,12,0.3); }

/* ── Export button ───────────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    transition: all 0.25s ease !important;
}
[data-testid="stDownloadButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(34,197,94,0.4) !important;
}

/* ── Dataframe tweaks ────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* ── Warning / info banners ──────────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: 10px; }

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0D1426; }
::-webkit-scrollbar-thumb { background: #4ECDC4; border-radius: 4px; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "results_df" not in st.session_state:
    st.session_state["results_df"] = None

if "last_search" not in st.session_state:
    st.session_state["last_search"] = {}

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-header">
        <h1>💼 MG Job Crawler</h1>
        <p>Search across multiple job platforms for positions requiring specific degrees or skills</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔎 Search Parameters")

    requirements = st.text_input(
        "Requirements",
        placeholder="e.g. Engenharia de Software, MBA, Data Science…",
        help="Enter a college degree, skill, or job title.",
    )

    location = st.text_input(
        "Location",
        placeholder="e.g. São Paulo, Rio de Janeiro, Brasília…",
        help="City or state. Leave blank to search nationwide.",
    )

    st.markdown('<div class="section-title">Job Sites</div>', unsafe_allow_html=True)
    use_gupy   = st.checkbox("🔵 Gupy",         value=True,  help="Uses public Gupy REST API – most reliable.")
    use_indeed = st.checkbox("🟣 Indeed Brasil", value=True,  help="Playwright + stealth. May require CAPTCHA workarounds.")
    use_vagas  = st.checkbox("🔴 Vagas.com.br",  value=True,  help="HTML scraping via requests + BeautifulSoup.")
    use_catho  = st.checkbox("🟠 Catho",         value=False, help="Playwright + stealth. Slow – enable if needed.")

    st.markdown('<div class="section-title">Options</div>', unsafe_allow_html=True)
    max_results = st.slider(
        "Max results per site",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
        help="Limit the number of results fetched from each source.",
    )

    st.markdown("---")
    search_clicked = st.button("🔍 Search Jobs", type="primary", width='stretch')

    st.markdown("---")
    st.caption(
        "⚠️ **Ethical Scraping Notice**  \n"
        "This tool respects rate limits and only accesses publicly available data. "
        "Do not use for commercial data harvesting."
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRAPER_MAP: dict[str, tuple[type, str]] = {
    "gupy":   (GupyScraper,   "Gupy"),
    "indeed": (IndeedScraper, "Indeed Brasil"),
    "vagas":  (VagasScraper,  "Vagas.com.br"),
    "catho":  (CathoScraper,  "Catho"),
}


def _run_scraper_in_thread(
    scraper_cls: type,
    query: str,
    location: str,
    max_results: int,
) -> list[JobPost]:
    """
    Run a scraper in a dedicated thread to avoid conflicts with
    Streamlit's internal asyncio event loop (Playwright creates its own loop).
    """
    scraper = scraper_cls()
    return scraper.scrape(query, location, max_results)


def _jobs_to_dataframe(jobs: list[JobPost]) -> pd.DataFrame:
    rows = [
        {
            "title":         j.title,
            "company":       j.company,
            "location":      j.location,
            "description":   j.description,
            "date_posted":   j.date_posted,
            "date_accessed": j.date_accessed,
            "source":        j.source,
            "link":          j.link,
        }
        for j in jobs
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------
if search_clicked:
    if not requirements.strip():
        st.warning("Please enter at least one requirement (degree, skill, or job title).")
    else:
        selected: list[str] = []
        if use_gupy:   selected.append("gupy")
        if use_indeed: selected.append("indeed")
        if use_vagas:  selected.append("vagas")
        if use_catho:  selected.append("catho")

        if not selected:
            st.warning("Please select at least one job site in the sidebar.")
        else:
            all_jobs: list[JobPost] = []
            errors: list[str] = []

            progress_bar = st.progress(0, text="Starting search…")

            for idx, key in enumerate(selected):
                cls, label = SCRAPER_MAP[key]
                progress_pct = idx / len(selected)
                progress_bar.progress(progress_pct, text=f"Searching **{label}**…")

                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            _run_scraper_in_thread,
                            cls,
                            requirements.strip(),
                            location.strip(),
                            max_results,
                        )
                        jobs = future.result(timeout=90)
                    all_jobs.extend(jobs)
                    logger.info("%s returned %d results", label, len(jobs))
                except concurrent.futures.TimeoutError:
                    errors.append(f"**{label}** timed out (90 s). Try fewer sites or increase timeout.")
                except Exception as exc:
                    logger.exception("Scraper %s failed", label)
                    errors.append(f"**{label}** failed: {exc}")

            progress_bar.progress(1.0, text="Done!")
            progress_bar.empty()

            for err in errors:
                st.warning(err)

            if all_jobs:
                st.session_state.results_df = _jobs_to_dataframe(all_jobs)
                st.session_state.last_search = {
                    "requirements": requirements.strip(),
                    "location": location.strip(),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                st.success(f"Found **{len(all_jobs)} job posting(s)** across {len(selected)} site(s).")
            else:
                if not errors:
                    st.info("No results found. Try different keywords or a broader location.")

# ---------------------------------------------------------------------------
# Results section
# ---------------------------------------------------------------------------
if st.session_state.results_df is not None and not st.session_state.results_df.empty:
    df_full: pd.DataFrame = st.session_state.results_df.copy()

    last = st.session_state.last_search
    st.caption(
        f"Last search — **{last.get('requirements')}** in **{last.get('location') or 'Nationwide'}** "
        f"@ {last.get('timestamp')}"
    )

    # ------------------------------------------------------------------
    # Filter controls
    # ------------------------------------------------------------------
    st.markdown('<div class="section-title">Filters</div>', unsafe_allow_html=True)
    filter_cols = st.columns([3, 3, 1])

    with filter_cols[0]:
        all_cities = sorted(df_full["location"].dropna().unique().tolist())
        city_options = ["All cities"] + all_cities
        selected_city = st.selectbox("Filter by city / location", city_options)

    with filter_cols[1]:
        all_sources = sorted(df_full["source"].dropna().unique().tolist())
        source_options = ["All sources"] + all_sources
        selected_source = st.selectbox("Filter by source", source_options)

    df_view = df_full.copy()
    if selected_city != "All cities":
        df_view = df_view[df_view["location"] == selected_city]
    if selected_source != "All sources":
        df_view = df_view[df_view["source"] == selected_source]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Results", len(df_full))
    m2.metric("Filtered Results", len(df_view))
    m3.metric("Sources", df_view["source"].nunique())
    m4.metric("Locations Found", df_view["location"].nunique())

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------
    st.markdown('<div class="section-title">Job Listings</div>', unsafe_allow_html=True)

    st.dataframe(
        df_view,
        width='stretch',
        hide_index=True,
        height=520,
        column_config={
            "title": st.column_config.TextColumn(
                "Job Title",
                width="medium",
                help="Position name as listed on the source site.",
            ),
            "company": st.column_config.TextColumn("Company", width="medium"),
            "location": st.column_config.TextColumn("Location", width="small"),
            "description": st.column_config.TextColumn(
                "Description",
                width="large",
                max_chars=220,
                help="Snippet / description from the posting.",
            ),
            "date_posted": st.column_config.TextColumn(
                "Date Posted",
                width="small",
            ),
            "date_accessed": st.column_config.TextColumn(
                "Date Accessed",
                width="small",
            ),
            "source": st.column_config.TextColumn("Source", width="small"),
            "link": st.column_config.LinkColumn(
                "Link",
                width="medium",
                help="Click to open the original posting.",
                display_text="Open ↗",
            ),
        },
    )

    # ------------------------------------------------------------------
    # Export — results stay visible after clicking (session_state preserved)
    # ------------------------------------------------------------------
    st.markdown("---")
    export_col, info_col = st.columns([2, 5])

    with export_col:
        excel_bytes = export_to_excel(df_view)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Export to Excel",
            data=excel_bytes,
            file_name=f"job_results_{timestamp_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Downloads only the currently filtered results.",
        )

    with info_col:
        st.caption(
            f"Exporting **{len(df_view)}** row(s). "
            "The table remains visible after downloading."
        )
