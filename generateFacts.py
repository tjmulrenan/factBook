import json
import requests
import os
import logging
import time

# API URLs
WIKI_API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/"
NUMBERS_API_URL = "http://numbersapi.com/"

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
        month = MONTH_MAPPING[month]
    else:
        log_message("error", f"❌ Invalid month entered: {month}")
        return None
    return f"{month}/{int(day):02d}"

def is_pg_text(text):
    """Check if a fact is PG-rated using simple keyword filtering."""
    banned_keywords = [
        "killed", "murder", "assassinated", "war", "massacre", "terrorist",
        "suicide", "executed", "dead", "death", "hanged", "bomb", "rape",
        "shooting", "violence", "attack", "explosion", "genocide"
    ]
    text_lower = text.lower()
    return not any(word in text_lower for word in banned_keywords)

# Fetch Wikimedia API facts
def fetch_wikipedia_api_facts(month, day):
    """Fetch and filter PG-rated events from Wikimedia API."""
    date = format_date(month, day)
    if not date:
        return None

    url = f"{WIKI_API_URL}{date}"
    headers = {"User-Agent": "Factbook-Project (your-email@example.com)"}

    log_message("info", f"Fetching Wikipedia API events from {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        events = {
            "Events": [f"{item['year']} - {item['text']}" for item in data.get("events", []) if is_pg_text(item['text'])],
            "Births": [f"{item['year']} - {item['text']}" for item in data.get("births", []) if is_pg_text(item['text'])],
            # "Deaths" section is removed to keep it kid-friendly
        }

        log_message("info", f"Wikipedia API retrieved {sum(len(v) for v in events.values())} PG facts")
        return events

    except requests.RequestException as e:
        log_message("error", f"⚠️ Wikipedia API request failed: {e}")
        return None

# Fetch fun facts from Numbers API multiple times
def fetch_numbers_api_facts(month, day, attempts=300):
    """Fetch multiple fun historical facts from Numbers API."""
    if month in MONTH_MAPPING:
        month_number = MONTH_MAPPING[month]
    else:
        log_message("error", f"❌ Invalid month entered for Numbers API: {month}")
        return []

    facts = set()  # Using a set to avoid duplicate facts

    for _ in range(attempts):
        url = f"{NUMBERS_API_URL}{month_number}/{int(day)}/date"
        headers = {"User-Agent": "Factbook-Project (your-email@example.com)"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            fact = response.text.strip()

            if fact and fact not in facts:
                facts.add(fact)  # Add unique facts to the set

        except requests.RequestException as e:
            log_message("error", f"⚠️ Numbers API request failed: {e}")

        time.sleep(0.1)  # Small delay to avoid excessive API calls

    log_message("info", f"Numbers API retrieved {len(facts)} unique fun facts")
    return list(facts)  # Convert set back to list before returning

    """Fetch fun historical facts from Numbers API."""
    if month in MONTH_MAPPING:
        month_number = MONTH_MAPPING[month]
    else:
        log_message("error", f"❌ Invalid month entered for Numbers API: {month}")
        return []

    url = f"{NUMBERS_API_URL}{month_number}/{int(day)}/date"
    headers = {"User-Agent": "Factbook-Project (timmulrenan@hotmail.com)"}

    log_message("info", f"Fetching fun facts from Numbers API: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.text.strip()

        log_message("info", f"Numbers API retrieved fact: {data}")
        return [data]

    except requests.RequestException as e:
        log_message("error", f"⚠️ Numbers API request failed: {e}")
        return []

# Fetch and store all facts
def fetch_and_store_facts(month, day):
    log_message("info", f"📅 Collecting historical facts for {month} {day}...")

    wiki_data = fetch_wikipedia_api_facts(month, day) or {}
    numbers_data = fetch_numbers_api_facts(month, day)

    all_events = {
        "Wikipedia": wiki_data,
        "Fun Facts": numbers_data
    }

    # If no PG facts found, add a friendly fallback
    if not any(wiki_data.values()) and not numbers_data:
        all_events["Note"] = ["Oops! Looks like today is a quiet day in history. Try another one!"]

    total_events = sum(len(v) for v in wiki_data.values()) + len(numbers_data)
    log_message("info", f"✅ Total PG-rated events collected: {total_events}")

    filename = f"facts/{month}_{day}.json"
    os.makedirs("facts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(all_events, file, indent=4, ensure_ascii=False)

    log_message("info", f"✅ Facts saved for {month} {day}: {filename}")

# Run the script
if __name__ == "__main__":
    month = input("Enter the month (e.g., January): ").strip()
    day = input("Enter the day (e.g., 14): ").strip()
    
    if month not in MONTH_MAPPING:
        log_message("error", "❌ Invalid month name. Please enter a valid month.")
    else:
        fetch_and_store_facts(month, day)
