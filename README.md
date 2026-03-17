# 💼 pyCrawler101 — Brazil Job Crawler

A modern, ethical web scraper that collects job listings from major Brazilian job platforms and presents them in a clean Streamlit interface. Designed to help researchers and job-seekers find positions requiring specific college degrees or skills.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Multi-source scraping** | Gupy (API), Indeed Brasil, Vagas.com.br, Catho |
| **Smart filtering** | Filter results by city / location and source site |
| **Modern UI** | Dark-themed Streamlit app with gradient accents |
| **Export to Excel** | Styled `.xlsx` export — table stays visible afterward |
| **Playwright stealth** | Reduces bot-detection fingerprints on JS-rendered sites |
| **Ethical by design** | Polite delays, respects public data only, no auth bypass |

---

## 🗂 Project Structure

```
pyCrawler101/
├── app.py                   # Streamlit entry point
├── requirements.txt
├── .gitignore
├── README.md
│
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py      # Abstract base class + JobPost dataclass
│   ├── gupy_scraper.py      # Gupy public REST API
│   ├── indeed_scraper.py    # Indeed Brasil – Playwright + stealth
│   ├── vagas_scraper.py     # Vagas.com.br – requests + BeautifulSoup
│   └── catho_scraper.py     # Catho – Playwright + stealth
│
└── utils/
    ├── __init__.py
    └── export.py            # Excel export with openpyxl formatting
```

---

## 🚀 Setup & Installation

### Prerequisites

- Python **3.10** or later
- Git

### 1 — Clone the repository

```bash
git clone https://github.com/your-username/pyCrawler101.git
cd pyCrawler101
```

### 2 — Create and activate a virtual environment

**Windows (PowerShell / CMD)**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4 — Install Playwright browser binaries

```bash
playwright install chromium
```

> This downloads the Chromium browser used by Indeed and Catho scrapers (~150 MB).  
> If you only use **Gupy** and **Vagas.com.br**, this step is optional.

---

## ▶️ Running the App

```bash
streamlit run app.py
```

The app will open automatically at **http://localhost:8501**.

---

## 🖥 Usage

1. **Enter your requirements** — a college degree, skill, or job title (e.g. *Engenharia de Software*, *MBA*, *Data Science*).
2. **Enter a location** — city or state (e.g. *São Paulo*, *Rio de Janeiro*). Leave blank to search nationwide.
3. **Select job sites** — tick the checkboxes for the sources you want.
4. **Set max results** — use the slider to control how many listings to fetch per site.
5. Click **Search Jobs** and wait for the results table to appear.
6. Use the **Filter by city** and **Filter by source** dropdowns to narrow results.
7. Click **Export to Excel** to download a formatted `.xlsx` file — the table remains visible.

---

## 📊 Output Columns

| Column | Description |
|---|---|
| **Job Title** | Position name as listed on the source site |
| **Company** | Employer name |
| **Location** | City / state from the listing |
| **Description** | Snippet or full description (check for degree requirements here) |
| **Date Posted** | Publication date (format varies by source) |
| **Date Accessed** | Timestamp when the crawl ran |
| **Source** | Job platform (Gupy, Indeed Brasil, etc.) |
| **Link** | Direct URL to the original posting |

---

## ⚙️ Scraper Details

### Gupy
Uses the **public Gupy REST API** (`portal.api.gupy.io/api/job`). No browser required. Most reliable source — low chance of blocking.

### Indeed Brasil
Uses **Playwright + playwright-stealth** to render JavaScript and extract job cards from `br.indeed.com`. Includes cookie-banner dismissal and navigator patching.

### Vagas.com.br
Uses **requests + BeautifulSoup** (HTML scraping). Vagas.com.br is server-rendered, so a full browser is not needed. Multiple selector fallbacks are included.

### Catho
Uses **Playwright + playwright-stealth** similar to Indeed. Disabled by default due to slower load times — enable in the sidebar when needed.

---

## ⚠️ Ethical Scraping Policy

This tool:
- **Only accesses publicly visible job data** (no login, no private endpoints).
- **Inserts polite delays** between requests (`1–3 s` random jitter).
- **Limits result counts** to avoid hammering servers.
- **Does not store or redistribute** scraped data beyond local use.

Please review each site's **Terms of Service** before using this tool for commercial purposes. The selectors used may break if a site updates its HTML structure — open a pull request if you find updated selectors.

---

## 🤝 Contributing

Pull requests are welcome! To add a new scraper:

1. Create `scrapers/my_site_scraper.py` that subclasses `BaseScraper`.
2. Implement the `scrape(query, location, max_results)` method returning `List[JobPost]`.
3. Register it in `scrapers/__init__.py` and add a checkbox in `app.py`.

---

## 📄 License

MIT License — see `LICENSE` for details.
