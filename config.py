# config.py — single source of truth for all paths & constants
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Project root — always the directory that contains this file.
# Works regardless of where you launch Python from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()

# ---------------------------------------------------------------------------
# Asset directories (static images / fonts — committed to git)
# ---------------------------------------------------------------------------
ASSETS_DIR      = PROJECT_ROOT / "assets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
FONTS_DIR       = ASSETS_DIR / "fonts"
OVERLAYS_DIR    = ASSETS_DIR / "overlays"
PICTURES_DIR    = ASSETS_DIR / "pictures"
COVER_DIR       = ASSETS_DIR / "cover"
CROSSWORD_DIR   = ASSETS_DIR / "crossword"
WORDSEARCH_DIR  = ASSETS_DIR / "wordsearch"

# ---------------------------------------------------------------------------
# Data directories (generated / large files — git-ignored)
# ---------------------------------------------------------------------------
DATA_DIR        = PROJECT_ROOT / "data"
BOOKS_DIR       = DATA_DIR / "books"
LOGS_DIR        = DATA_DIR / "logs"
JOKES_JSON      = DATA_DIR / "jokes" / "generatedJokes.json"
QUOTES_JSON     = DATA_DIR / "quotes" / "generatedquotes.json"

# Fact pipeline stage directories
FACTS_DATA_DIR    = DATA_DIR / "facts"
RAW_FACTS_DIR     = FACTS_DATA_DIR / "raw"          # scraped raw facts
SCORED_FACTS_DIR  = FACTS_DATA_DIR / "scored"       # after scoring
CULLED_FACTS_DIR  = FACTS_DATA_DIR / "culled"       # after culling
ENHANCED_FACTS_DIR = FACTS_DATA_DIR / "enhanced"    # after AI enhancement
CATEG_FACTS_DIR   = FACTS_DATA_DIR / "categorised"  # after categorisation
FINAL_FACTS_DIR   = FACTS_DATA_DIR / "final" / "6_final"  # final combined facts
CHECKED_FACTS_DIR = FACTS_DATA_DIR / "checked"      # after fact-checking

# Holiday pipeline stage directories
HOL_RAW_DIR      = FACTS_DATA_DIR / "a_raw"         # raw holiday scrapes
HOL_DAY_DIR      = FACTS_DATA_DIR / "a_rawDay"      # raw day-event scrapes
HOL_SCORED_DIR   = FACTS_DATA_DIR / "b_scored"      # scored holidays
HOL_ENHANCED_DIR = FACTS_DATA_DIR / "c_enhanced"    # enhanced holidays

# ---------------------------------------------------------------------------
# External output directory — the 366-day book collection.
# Override with the FACTBOOK_OUTPUT_DIR environment variable if your output
# lives somewhere other than the default below.
# ---------------------------------------------------------------------------
FINAL_OUTPUT_DIR = Path(
    os.getenv("FACTBOOK_OUTPUT_DIR") or
    (PROJECT_ROOT / "What Happened On... (The Complete Collection)")
)

# ---------------------------------------------------------------------------
# Book dimensions (inches) — used by both generate.py and cover builders
# ---------------------------------------------------------------------------
TRIM_W_IN = 6.0
TRIM_H_IN = 9.0
BLEED_IN  = 0.125   # KDP bleed per side

# ---------------------------------------------------------------------------
# Pipeline / scheduling
# ---------------------------------------------------------------------------
LEAP_YEAR = 2024    # DOY mapping uses a leap year so every date 1–366 exists
