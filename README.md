# What Happened On...

A pipeline for generating a 366-day series of illustrated educational PDF fact books — one for each day of the year — aimed at children aged 8–12. Each book is a full-colour, print-ready PDF containing daily historical facts, holidays, trivia, jokes, and quotes, published via Amazon KDP.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Configuration](#configuration)
- [Pipelines](#pipelines)
  - [Fact Pipeline](#fact-pipeline)
  - [Book Pipeline](#book-pipeline)
- [Running a Single Day](#running-a-single-day)
- [Publisher Bot](#publisher-bot)
- [Data Flow](#data-flow)
- [Categories](#categories)
- [Environment Variables](#environment-variables)

---

## Overview

The project has two independent pipelines:

| Pipeline | Purpose | Entry point |
|---|---|---|
| **Fact pipeline** | Scrape, score, enhance, and combine facts & holidays into final JSON | `pipelines/run_fact_pipeline.py` |
| **Book pipeline** | Generate print-ready PDFs (interior + cover) from final JSON | `pipelines/run_book_pipeline.py` |

Output: one folder per day (`{DOY}_{Month}_{Day}/`) inside the configured output directory, each containing `full_manuscript.pdf`, `book_cover.pdf`, and `front_cover.png`.

---

## Project Structure

```
factBook/
├── config.py                   # All paths & constants — import from here
├── pyproject.toml
├── requirements.txt
├── .env                        # API keys (not committed)
│
├── pipelines/
│   ├── run_fact_pipeline.py    # Orchestrates full 7-step fact pipeline
│   └── run_book_pipeline.py    # Orchestrates full 4-step book pipeline (parallel)
│
├── book/                       # PDF generation
│   ├── flowables.py            # Custom ReportLab flowables & doc template
│   ├── content_builder.py      # Page content assembly & category data
│   ├── generate.py             # Three-pass render pipeline (step 1)
│   ├── gap_fill.py             # Transparent gap fill (step 2)
│   └── speech_bubbles.py       # Speech bubble overlays & compression (step 3)
│
├── covers/
│   ├── generate.py             # Front cover PNG generation
│   ├── build_paperback.py      # Paperback cover PDF (step 4)
│   ├── build_hardcover.py      # Hardcover variant
│   └── build_spines.py         # Spine graphics
│
├── facts/                      # Fact pipeline steps 1 & 5–7
│   ├── day_grabber.py          # Fetch seasonal/calendar day facts (step 1)
│   ├── grabber.py              # Scrape historical facts from web
│   ├── scorer.py               # Score facts for relevance & kid-friendliness
│   ├── culler.py               # Filter, rank, and cap facts (interactive, step 5)
│   ├── enhancer.py             # Rewrite facts as kid-friendly stories (step 6)
│   ├── categoriser.py          # Assign category labels
│   ├── combiner.py             # Merge facts + holidays into final JSON (step 7)
│   └── checker.py              # Post-enhancement fact-checking
│
├── holidays/                   # Fact pipeline steps 2–4
│   ├── grabber.py              # AI-generated holiday list (step 2)
│   ├── scorer.py               # Score & rank holidays (step 3)
│   └── enhancer.py             # Rewrite holidays as stories (step 4)
│
├── content/
│   ├── category_jokes.py       # Curated jokes by category
│   ├── generate_jokes.py       # Auto-generate jokes via Claude
│   └── generate_quotes.py      # Auto-generate quotes via Claude
│
├── tools/                      # One-off utilities
│   ├── validate_integrity.py   # Check all 366 output folders are complete
│   ├── fact_fiddler.py         # Manual fact editing tool
│   ├── add_blank_pages.py      # Append blank pages to a PDF
│   ├── adjust_backgrounds.py   # Tweak background image brightness/contrast
│   ├── nuke_books.py           # Delete generated PDFs to force regeneration
│   ├── rename_books.py         # Batch rename output files
│   ├── fact_counter.py         # Count facts per day/category
│   └── gap_fill_debug.py       # Debug version of gap_fill.py
│
├── assets/
│   ├── backgrounds/            # Full-page section background PNGs
│   ├── overlays/               # Speech bubble PNGs (bonus fact, joke, quote, etc.)
│   ├── fonts/                  # Knewave-Regular.ttf (cover & headers)
│   ├── cover/raw/              # Base cover template (cover.png)
│   ├── crossword/              # Crossword puzzle assets
│   └── wordsearch/             # Word search assets
│
├── data/                       # Generated data — mostly git-ignored
│   ├── facts/
│   │   ├── a_rawDay/           # Seasonal/calendar facts (day_grabber output)
│   │   ├── a_raw/              # Raw holiday scrapes
│   │   ├── b_scored/           # Scored holidays
│   │   ├── c_enhanced/         # Enhanced holidays
│   │   ├── raw/                # Raw historical facts
│   │   ├── scored/             # Scored historical facts
│   │   ├── culled/             # Filtered & ranked facts
│   │   ├── enhanced/           # AI-rewritten fact stories
│   │   └── final/6_final/      # Combined final JSON per day
│   ├── books/                  # Intermediate PDFs
│   ├── jokes/                  # generatedJokes.json
│   └── quotes/                 # generatedquotes.json
│
├── publisher-bot/              # Playwright automation for KDP uploads
└── archive/                    # Old/draft files (not active)
```

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (publisher bot only)
- [Ghostscript](https://www.ghostscript.com/) — optional, enables PDF compression in step 3

### Install Python dependencies

```bash
pip install -r requirements.txt
```

### Install publisher bot dependencies

```bash
cd publisher-bot
npm install
npx playwright install chromium
```

### Configure environment variables

Create a `.env` file in the project root:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...          # Legacy — may not be required

# Optional: override output directory
# FACTBOOK_OUTPUT_DIR=C:\Path\To\What Happened On... (The Complete Collection)
```

`config.py` calls `load_dotenv()` automatically, so every script that imports config will pick up `.env` without any extra setup.

---

## Configuration

All paths and constants live in `config.py`. Import from there — never hardcode paths in scripts.

```python
from config import FINAL_FACTS_DIR, FINAL_OUTPUT_DIR, ASSETS_DIR
```

Key constants:

| Constant | Description |
|---|---|
| `FINAL_OUTPUT_DIR` | Root folder for all 366 day output folders |
| `FINAL_FACTS_DIR` | `data/facts/final/6_final/` — input for book pipeline |
| `ASSETS_DIR` | `assets/` |
| `TRIM_W_IN / TRIM_H_IN` | Book trim size: 6.0 × 9.0 inches (KDP standard) |
| `BLEED_IN` | 0.125 inch bleed per side |
| `LEAP_YEAR` | 2024 — used for DOY 1–366 mapping (includes Feb 29) |

---

## Pipelines

### Fact Pipeline

Generates the final enriched JSON for a given day. Run for one day or sweep all 366.

```bash
# Single day (DOY = 1 for January 1)
python pipelines/run_fact_pipeline.py --doy 1

# All days (sweeps Oct → Dec then Jan → Sep by default)
python pipelines/run_fact_pipeline.py
```

**Steps (sequential per day):**

| Step | Script | Description |
|---|---|---|
| 1 | `facts/day_grabber.py` | Generates seasonal/calendar day facts via Claude |
| 2 | `holidays/grabber.py` | AI-generated holiday list for the date |
| 3 | `holidays/scorer.py` | Scores & ranks holidays for kid-friendliness |
| 4 | `holidays/enhancer.py` | Rewrites holidays as kid-friendly stories |
| 5 | `facts/culler.py` | Filters and ranks facts — **interactive**, prompts for confirmation |
| 6 | `facts/enhancer.py` | Rewrites facts as illustrated stories with trivia via Claude Sonnet |
| 7 | `facts/combiner.py` | Merges holidays + facts into final JSON |

The pipeline is idempotent — it skips a day if `{DOY}_{Month}_{Day}_Final.json` already exists.

**Output:** `data/facts/final/6_final/{DOY}_{Month}_{Day}_Final.json`

```json
[
  {
    "id": "901",
    "title": "Polar Bear Plunge: The Coolest New Year Tradition",
    "story": "Thousands of brave people...",
    "activity_question": "What do many Polar Bear Plunge participants wear?",
    "activity_choices": ["Costumes or swimsuits", "Full winter coats", "..."],
    "activity_answer": "Costumes or swimsuits",
    "follow_up_question": "Would you ever try a polar bear plunge?",
    "categories": ["Days That Slay"],
    "suitable_for_8_to_12_year_old": true,
    "score": 88
  }
]
```

---

### Book Pipeline

Generates print-ready PDFs from a final JSON file. Up to 3 days run in parallel.

```bash
# All days with missing output
python pipelines/run_book_pipeline.py

# Single day
python book/generate.py --doy 1
```

**Steps (sequential per day):**

| Step | Script | Output |
|---|---|---|
| 1 | `book/generate.py` | `1.pdf` — base interior PDF |
| 2 | `book/gap_fill.py` | `2.pdf` — transparent gaps filled |
| 3 | `book/speech_bubbles.py` | `3.pdf` + `full_manuscript.pdf` |
| 4 | `covers/build_paperback.py` | `book_cover.pdf` |

> **Note:** PDF compression in step 3 requires Ghostscript to be installed and on `PATH`. Without it, `full_manuscript.pdf` is an uncompressed copy of `3.pdf`.

**Output per day** (inside `FINAL_OUTPUT_DIR/{DOY}_{Month}_{Day}/`):

```
full_manuscript.pdf   # Interior PDF — upload to KDP
book_cover.pdf        # Cover PDF — upload to KDP
front_cover.png       # Front cover image
```

---

## Running a Single Day

To run just one day manually through both pipelines:

```bash
# Step 1: Generate facts
python pipelines/run_fact_pipeline.py --doy 264

# Step 2: Generate book (once fact pipeline completes)
python book/generate.py --doy 264
python book/gap_fill.py --doy 264
python book/speech_bubbles.py --doy 264
python covers/build_paperback.py --doy 264
```

Set `FACTBOOK_DOY` to skip the interactive day-selection prompt in any script:

```bash
FACTBOOK_DOY=264 python facts/culler.py
```

---

## Publisher Bot

A Playwright automation tool that uploads completed books to Amazon KDP.

```bash
cd publisher-bot

# Authenticate (opens browser, saves session to auth.json)
node run-kdp-chrome.js

# Upload a specific day
node run-with-doy.js 264

# Run full upload test
npx playwright test tests/upload-new-manuscript-and-cover-live-filter.spec.js
```

`auth.json` stores the browser session and is git-ignored. Re-run `run-kdp-chrome.js` if your session expires.

Override the default book output path with the `FINAL_DIR` environment variable:

```bash
FINAL_DIR="D:\My Books" node run-with-doy.js 1
```

---

## Data Flow

```
facts/day_grabber.py  ──→  data/facts/a_rawDay/
holidays/grabber.py   ──→  data/facts/a_raw/
holidays/scorer.py    ──→  data/facts/b_scored/
holidays/enhancer.py  ──→  data/facts/c_enhanced/
facts/culler.py       ──→  data/facts/culled/        (interactive)
facts/enhancer.py     ──→  data/facts/enhanced/
facts/combiner.py     ──→  data/facts/final/6_final/
                                    │
                    ┌───────────────┘
                    ↓
          book/generate.py       →  {DOY}/1.pdf
          book/gap_fill.py       →  {DOY}/2.pdf
          book/speech_bubbles.py →  {DOY}/full_manuscript.pdf
          covers/build_paperback.py → {DOY}/book_cover.pdf
```

---

## Categories

Each fact is assigned to one of 11 categories, which determine the background artwork and section layout in the book:

| Category | Theme |
|---|---|
| Today's Vibe Check | Seasonal & calendar day facts |
| History's Mic Drop Moments | Major turning points & revolutions |
| World Shakers & Icon Makers | Notable people & legends |
| Big Brain Energy | Science, inventions & discoveries |
| Beyond Earth | Space & astronomy |
| Creature Feature | Animals & nature |
| Vibes, Beats & Brushes | Art, music & culture |
| Days That Slay | Holidays & celebrations |
| Full Beast Mode | Sports & athletic records |
| Mother Nature's Meltdowns | Natural disasters & weather |
| The What Zone | Weird, surprising & silly facts |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `OPENAI_API_KEY` | No | Legacy — not currently used |
| `FACTBOOK_OUTPUT_DIR` | No | Override default output directory |
| `FACTBOOK_DOY` | No | Pre-select day of year (skips interactive prompt) |
| `SKIP_CLAUDE` | No | Set to `1` to skip Claude ranking in culler |
| `SKIP_CLAUDE_DAY` | No | Set to `1` to use fallback day facts instead of API |
| `CLAUDE_MODEL` | No | Override Claude model (default: `claude-sonnet-4-5-20251001`) |

---

## Author

Created by TJ Mulrenan — inspired by a love for facts, storytelling, and sparking curiosity in young minds.
