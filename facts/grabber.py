import calendar
import datetime
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RAW_FACTS_DIR

OUTPUT_DIR = str(RAW_FACTS_DIR)

def fetch_onthisday_events(month: str, day: int):
    url = f"https://www.onthisday.com/events/{month.lower()}/{day}"
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"🌐 Scraping {url}...")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        debug_path = f"debug_events_{month}_{day}.html"
        with open(debug_path, "w", encoding="utf-8") as debug_file:
            debug_file.write(response.text)
        print(f"📝 Saved raw HTML to {debug_path}")

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    facts = []

    # === Main event list ===
    event_items = soup.select("ul.event-list > li.event")
    print(f"🔍 Found {len(event_items)} standard events")

    for i, li in enumerate(event_items, 1):
        full_text = li.get_text(strip=True)
        clean_text = re.sub(r"\[\d+\]", "", full_text).replace("\u200b", "").replace("\xa0", " ").strip()
        year_tag = li.find("a", class_="date")
        year = year_tag.get_text(strip=True) if year_tag else None

        if not year:
            match = re.match(r"^\s*(\d{1,4})(?:\s?(BC|AD))?(.*)", clean_text)
            if not match or not match.group(3).strip():
                print(f"  ⚠️ Skipping item {i} — missing year or text\n     Raw text: {full_text}")
                continue

            year = match.group(1).strip()
            if match.group(2):
                year += " " + match.group(2).strip()
            text = match.group(3).strip()
        else:
            text = clean_text[len(year):].strip()

        if not text:
            print(f"  ⚠️ Skipping item {i} — empty text after year removal")
            continue

        facts.append({
            "year": year,
            "text": text
        })

    # === POI Highlight Section ===
    poi_blocks = soup.select("div.section--highlight.section--poi p")
    print(f"🟨 Found {len(poi_blocks)} highlighted POI entries")

    for i, p in enumerate(poi_blocks, 1):
        full_text = p.get_text(strip=True)
        clean_text = re.sub(r"\[\d+\]", "", full_text).replace("\u200b", "").replace("\xa0", " ").strip()

        match = re.match(r"^(\d{1,4})(?:\s?(BC|AD))?(.*)", clean_text)
        if not match or not match.group(3).strip():
            print(f"  ⚠️ Skipping item {i} — missing year or text\n     Raw text: {full_text}")
            continue

        year = match.group(1).strip()
        if match.group(2):
            year += " " + match.group(2).strip()
        text = match.group(3).strip()

        facts.append({
            "year": year,
            "text": text
        })

    # === Other Highlight Sections ===
    other_highlight_blocks = soup.select("div.section--highlight:not(.section--poi) p")
    print(f"🟪 Found {len(other_highlight_blocks)} other highlighted entries")

    for i, p in enumerate(other_highlight_blocks, 1):
        full_text = p.get_text(strip=True)
        clean_text = re.sub(r"\[\d+\]", "", full_text).replace("\u200b", "").replace("\xa0", " ").strip()

        match = re.match(r"^(\d{1,4})(?:\s?(BC|AD))?(.*)", clean_text)
        if not match or not match.group(3).strip():
            print(f"  ⚠️ Skipping item {i} — missing year or text\n     Raw text: {full_text}")
            continue

        year = match.group(1).strip()
        if match.group(2):
            year += " " + match.group(2).strip()
        text = match.group(3).strip()

        facts.append({
            "year": year,
            "text": text
        })

    print(f"✅ Total facts collected: {len(facts)}")
    return facts

def fetch_birthdays(month: str, day: int):
    url = f"https://www.onthisday.com/birthdays/{month.lower()}/{day}"
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"🌐 Scraping birthdays from {url}...")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        debug_path = f"debug_birthdays_{month}_{day}.html"
        with open(debug_path, "w", encoding="utf-8") as debug_file:
            debug_file.write(response.text)
        print(f"📝 Saved raw birthday HTML to {debug_path}")

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    birthday_items = soup.select("ul.event-list > li.person")

    print(f"🎂 Found {len(birthday_items)} birthdays")

    birthdays = []

    for i, li in enumerate(birthday_items, 1):
        try:
            year_tag = li.select_one("a.birthDate") or li.select_one("b")
            full_text = li.get_text(strip=True)

            if not year_tag or not full_text:
                print(f"⚠️ Skipping birthday {i} — missing year or text")
                continue

            year = year_tag.get_text(strip=True)
            text = full_text[len(year):].strip()

            birthdays.append({
                "year": year,
                "text": text
            })
        except Exception as e:
            print(f"⚠️ Skipped birthday {i} due to parsing error: {e}")
            continue

    return birthdays

def save_to_json(day_of_year: int, month: str, day: int, events, birthdays):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.join(OUTPUT_DIR, f"{day_of_year}_{month}_{day}.json")
    combined_facts = events + birthdays
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"Facts": combined_facts}, f, indent=2, ensure_ascii=False)
    print(f"📁 Saved to {filename}")

if __name__ == "__main__":
    # Use a leap year so Feb 29 is included and numbering is 1..366
    YEAR = 2024

    for month_index in range(1, 13):
        month_name = calendar.month_name[month_index]
        days_in_month = calendar.monthrange(YEAR, month_index)[1]

        for day in range(1, days_in_month + 1):
            print(f"\n📅 Scraping {month_name} {day}...")

            events = fetch_onthisday_events(month_name, day)
            birthdays = fetch_birthdays(month_name, day)

            # Compute day-of-year including leap day
            day_of_year = datetime.date(YEAR, month_index, day).timetuple().tm_yday

            print(f"📊 Events: {len(events)}")
            print(f"🎉 Birthdays: {len(birthdays)}")
            print(f"📦 Total facts to save: {len(events) + len(birthdays)}")
            print(f"🧮 Day-of-year: {day_of_year}")

            save_to_json(day_of_year, month_name, day, events, birthdays)
