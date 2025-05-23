import json
import requests
import os
import logging
import time

# API URL
WIKI_API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/"

# Month mapping dictionary
MONTH_MAPPING = {
    "January": "01", "February": "02", "March": "03", "April": "04", "May": "05", "June": "06",
    "July": "07", "August": "08", "September": "09", "October": "10", "November": "11", "December": "12"
}

# Setup logging
LOG_FILE = "debug.log"
logging.basicConfig(
    filename=LOG_FILE, 
    filemode="w", 
    format="%(asctime)s - %(levelname)s - %(message)s", 
    level=logging.DEBUG
)

def log_message(level, message):
    """Logs messages to console and file."""
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)

def format_date(month, day):
    """Convert month name to number & zero-pad day."""
    if month in MONTH_MAPPING:
        month = MONTH_MAPPING[month]  # Convert month name to number
    else:
        log_message("error", f"❌ Invalid month entered: {month}")
        return None
    return f"{month}/{int(day):02d}"

# Fetch Wikimedia API facts
def fetch_wikipedia_api_facts(month, day):
    """Fetch events from Wikimedia API."""
    date = format_date(month, day)
    if not date:
        return None  # Return None if month is invalid

    url = f"{WIKI_API_URL}{date}"
    headers = {"User-Agent": "Factbook-Project (your-email@example.com)"}

    log_message("info", f"Fetching Wikipedia API events from {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        events = {
            "Events": [f"{item['year']} - {item['text']}" for item in data.get("events", [])],
            "Births": [f"{item['year']} - {item['text']}" for item in data.get("births", [])],
            "Deaths": [f"{item['year']} - {item['text']}" for item in data.get("deaths", [])]
        }

        log_message("info", f"Wikipedia API retrieved {sum(len(v) for v in events.values())} facts")
        return events

    except requests.RequestException as e:
        log_message("error", f"⚠️ Wikipedia API request failed: {e}")
        return None

# Fetch and store all facts
def fetch_and_store_facts(month, day):
    log_message("info", f"📅 Collecting historical facts for {month} {day}...")

    wiki_data = fetch_wikipedia_api_facts(month, day)

    if not wiki_data:
        log_message("error", "❌ No data retrieved from Wikipedia API.")
        return

    total_events = sum(len(events) for events in wiki_data.values() if isinstance(events, list))
    log_message("info", f"✅ Total events collected: {total_events}")

    filename = f"facts/{month}_{day}.json"
    os.makedirs("facts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(wiki_data, file, indent=4, ensure_ascii=False)

    log_message("info", f"✅ Facts saved for {month} {day}: {filename}")

# Run the script
if __name__ == "__main__":
    month = input("Enter the month (e.g., January): ").strip()
    day = input("Enter the day (e.g., 14): ").strip()
    
    if month not in MONTH_MAPPING:
        log_message("error", "❌ Invalid month name. Please enter a valid month.")
    else:
        fetch_and_store_facts(month, day)
