import json
import requests
import os
import logging
from datetime import datetime, timedelta

# Wikipedia API URL
WIKI_API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/"

# Logging setup
LOG_FILE = "unsorted_debug.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG
)

def log_message(level, message):
    print(message)
    getattr(logging, level)(message)

def is_pg_text(text):
    banned_keywords = [
        "killed", "murder", "assassinated", "war", "massacre", "terrorist",
        "suicide", "executed", "dead", "death", "hanged", "bomb", "rape",
        "shooting", "violence", "attack", "explosion", "genocide"
    ]
    return not any(word in text.lower() for word in banned_keywords)

def fetch_wikipedia_api_facts(month, day):
    month_str = f"{month:02d}"
    day_str = f"{day:02d}"
    url = f"{WIKI_API_URL}{month_str}/{day_str}"
    headers = {"User-Agent": "Factbook-Project (tj.mulrenan@example.com)"}
    log_message("info", f"📅 Fetching {month_str}/{day_str} from Wikipedia...")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        events = [f"{item['year']} - {item['text']}" for item in data.get("events", []) if is_pg_text(item['text'])]
        births = [f"{item['year']} - {item['text']}" for item in data.get("births", []) if is_pg_text(item['text'])]

        log_message("info", f"✅ {len(events)} events, {len(births)} births retrieved.")
        return {"Events": events, "Births": births}

    except requests.RequestException as e:
        log_message("error", f"❌ API request failed for {month_str}/{day_str}: {e}")
        return {"error": str(e)}

def fetch_all_days():
    base_dir = r"C:\Users\tmulrenan\Desktop\Factbook Project\facts\unsorted"
    os.makedirs(base_dir, exist_ok=True)

    start_date = datetime(2024, 1, 1)  # Leap year to include Feb 29
    summary = []

    for i in range(366):
        date = start_date + timedelta(days=i)
        month = date.strftime("%B")
        day = date.day
        filename = f"{base_dir}\\{month}_{day}_unsorted.json"

        log_message("info", f"🔍 Processing: {month} {day}")

        # Check for existing file with valid content
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    total_facts = sum(len(data.get(k, [])) for k in ["Events", "Births"])
                    if total_facts > 0:
                        msg = f"🟡 {month} {day} - Already exists, {total_facts} facts"
                        log_message("info", msg)
                        summary.append(msg)
                        continue
            except Exception as e:
                log_message("warning", f"⚠️ Could not read {filename}, will retry: {e}")

        # Fetch if missing or invalid
        facts = fetch_wikipedia_api_facts(date.month, day)

        if "error" in facts:
            msg = f"❌ {month} {day} - FAILED: {facts['error']}"
            summary.append(msg)
            continue

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(facts, file, indent=4, ensure_ascii=False)

        total = sum(len(facts.get(k, [])) for k in facts)
        msg = f"✅ {month} {day} - {total} facts saved."
        summary.append(msg)
        log_message("info", f"📁 Saved to {filename}")

    # Save the final summary with UTF-8 encoding
    summary_file = os.path.join(base_dir, "fetch_summary.txt")
    with open(summary_file, "w", encoding="utf-8") as sf:
        sf.write("\n".join(summary))

    log_message("info", f"🎉 Done! Summary written to: {summary_file}")

if __name__ == "__main__":
    fetch_all_days()
