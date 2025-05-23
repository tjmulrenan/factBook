import json
import requests
import os
import logging
import re
from difflib import SequenceMatcher

# Wikipedia API URL
WIKI_API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/"

# Month mapping
MONTH_MAPPING = {
    "January": "01", "February": "02", "March": "03", "April": "04", "May": "05", "June": "06",
    "July": "07", "August": "08", "September": "09", "October": "10", "November": "11", "December": "12"
}

# Logging setup
LOG_FILE = "debug.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG
)

def log_message(level, message):
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)

def format_date(month, day):
    if month in MONTH_MAPPING:
        return f"{MONTH_MAPPING[month]}/{int(day):02d}"
    log_message("error", f"❌ Invalid month entered: {month}")
    return None

def is_pg_text(text):
    banned_keywords = [
        "killed", "murder", "assassinated", "war", "massacre", "terrorist",
        "suicide", "executed", "dead", "death", "hanged", "bomb", "rape",
        "shooting", "violence", "attack", "explosion", "genocide"
    ]
    text_lower = text.lower()
    return not any(word in text_lower for word in banned_keywords)

def normalize_fact_text(text):
    return re.sub(r'\W+', '', text.strip().lower())

def is_semantic_duplicate(text1, text2, threshold=0.85):
    ratio = SequenceMatcher(None, normalize_fact_text(text1), normalize_fact_text(text2)).ratio()
    return ratio >= threshold

def fetch_wikipedia_api_facts(month, day):
    date = format_date(month, day)
    if not date:
        return {}

    url = f"{WIKI_API_URL}{date}"
    headers = {"User-Agent": "Factbook-Project (your-email@example.com)"}
    log_message("info", f"Fetching Wikipedia API events from {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        events = {
            "Events": [f"{item['year']} - {item['text']}" for item in data.get("events", []) if is_pg_text(item['text'])],
            "Births": [f"{item['year']} - {item['text']}" for item in data.get("births", []) if is_pg_text(item['text'])]
        }

        log_message("info", f"Wikipedia API retrieved {sum(len(v) for v in events.values())} PG facts")
        return events

    except requests.RequestException as e:
        log_message("error", f"⚠️ Wikipedia API request failed: {e}")
        return {}

def fetch_and_store_facts(month, day):
    log_message("info", f"📅 Collecting historical facts for {month} {day}...")

    wiki_data = fetch_wikipedia_api_facts(month, day)

    all_events = {
        "Wikipedia": wiki_data
    }

    if not any(wiki_data.values()):
        all_events["Note"] = ["Oops! Looks like today is a quiet day in history. Try another one!"]

    total_events = sum(len(v) for v in wiki_data.values())
    log_message("info", f"✅ Total PG-rated events collected: {total_events}")

    filename = f"facts/{month}_{day}.json"
    os.makedirs("facts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(all_events, file, indent=4, ensure_ascii=False)

    log_message("info", f"✅ Facts saved for {month} {day}: {filename}")

if __name__ == "__main__":
    month = input("Enter the month (e.g., January): ").strip()
    day = input("Enter the day (e.g., 14): ").strip()

    if month not in MONTH_MAPPING:
        log_message("error", "❌ Invalid month name. Please enter a valid month.")
    else:
        fetch_and_store_facts(month, day)
