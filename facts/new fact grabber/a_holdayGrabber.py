import os
import json
import calendar
import re
from datetime import datetime, timedelta
from anthropic import Anthropic

LEAP_YEAR = 2024  # use leap-year indexing (e.g., Sep 7 = 251)

OUTPUT_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\a_raw"

def doy_to_month_day(doy: int):
    base = datetime(LEAP_YEAR, 1, 1) + timedelta(days=doy - 1)
    return base.strftime("%B"), base.day  # ("September", 7)


anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def extract_last_json_array(text: str) -> str:
    """
    Find the last top-level JSON array in arbitrary text (handles prose + code blocks).
    Returns the JSON string or '' if none.
    """
    stack = 0
    start = -1
    last = ""
    for i, ch in enumerate(text):
        if ch == '"' and (i == 0 or text[i-1] != '\\'):
            # naive: ignore string parsing for brevity; works well on model output that’s mostly valid JSON
            pass
        if ch == '[':
            if stack == 0:
                start = i
            stack += 1
        elif ch == ']':
            if stack > 0:
                stack -= 1
                if stack == 0 and start != -1:
                    last = text[start:i+1]
    return last.strip()

def ask_claude_for_initial_holidays(month: str, day: int) -> list:
    user_input = (
        f"List at least 10 holidays that are specifically celebrated on {month} {day} every year, "
        "or widely associated with that exact calendar date in online culture. "
        "Include both official observances and fun, quirky, or internet-famous celebrations. "
        "Avoid holidays that change dates each year (e.g. 'last Wednesday of March') or that are not consistently celebrated on this date in 2025. "
        "Skip religious-only holidays unless they are widely recognized and relevant to children. "
        "Do not include duplicates or aliases of the same holiday. "
        "For each entry, return:\n"
        "- name\n"
        "- whether it is kid-friendly (true or false)\n\n"
        "Respond only with a valid JSON list in this format:\n"
        '[{\"name\": \"Holiday Name\", \"kid_friendly\": true}]'
    )

    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        system="Return ONLY a valid JSON array. No prose. No code fences.",
        max_tokens=1000,
        temperature=0.0,
        messages=[
            {"role": "user", "content": user_input}
        ]
    )

    raw = response.content[0].text.strip()

    # Prefer code block, else find last JSON array, else raw
    block = re.search(r"```json\s*(\[\s*{.*?}\s*\])\s*```", raw, re.DOTALL)
    json_text = block.group(1).strip() if block else extract_last_json_array(raw)
    if not json_text:
        json_text = raw

    try:
        return json.loads(json_text)
    except Exception as e:
        print("❌ JSON parsing error (initial):", e)
        print(raw[:1200])
        return []

def ask_claude_to_clean_holidays(month: str, day: int, holidays: list) -> list:
    cleaning_prompt = (
        f"You are verifying whether each of the following holidays is truly celebrated on {month} {day} in the year 2025. "
        "Your job is to remove any holiday that is not *strictly tied* to this exact calendar date.\n\n"
        "Remove a holiday if:\n"
        "- It is based on a weekday (e.g., 'last Friday of March', 'third Wednesday', etc.)\n"
        "- It is defined by an ordinal number (e.g., '88th day of the year') that does not fall on this date in 2025\n"
        "- It only falls on this date some years, but not in 2025\n"
        "- Its official celebration date is different (e.g., another fixed day of the year)\n"
        "- It cannot be verified from reliable public sources (e.g., National Day calendars, official websites)\n"
        "- It is a duplicate, alias, or slight variation of another holiday already listed\n"
        "- It is vague or invented without strong reference to the exact calendar date\n\n"
        f"Keep only holidays that are consistently and verifiably celebrated on {month} {day} in 2025, and always on that date in other years as well.\n\n"
        "Return only the cleaned JSON list in this format:\n"
        '[{\"name\": \"Holiday Name\", \"kid_friendly\": true}]'
    )

    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        system="Return ONLY a valid JSON array. No prose. No code fences.",
        max_tokens=1000,
        temperature=0.0,
        messages=[
            {"role": "user", "content": cleaning_prompt},
            {"role": "user", "content": json.dumps(holidays, indent=2)}
        ]
    )
    raw = response.content[0].text.strip()

    # Prefer code block, else last JSON array, else raw
    block = re.search(r"```json\s*(\[\s*{.*?}\s*\])\s*```", raw, re.DOTALL)
    json_text = block.group(1).strip() if block else extract_last_json_array(raw)
    if not json_text:
        json_text = raw

    try:
        cleaned = json.loads(json_text)

        # Logging removed holidays
        initial_names = {h.get('name') for h in holidays}
        cleaned_names = {h.get('name') for h in cleaned}
        removed = initial_names - cleaned_names

        print("\n📋 Initial holidays:")
        for h in holidays:
            print(f"  - {h.get('name')} (kid_friendly: {h.get('kid_friendly')})")

        print("\n🗑️ Removed during cleanup:")
        for name in removed:
            if name: print(f"  ✘ {name}")

        print("\n✅ Final cleaned holidays:")
        for h in cleaned:
            print(f"  ✔ {h.get('name')} (kid_friendly: {h.get('kid_friendly')})")

        return cleaned

    except Exception as e:
        print("❌ JSON parsing error (cleanup):", e)
        print(raw[:1200])
        print("⚠️ Using initial holidays due to parse failure.")
        return holidays

def save_to_json(doy: int, month: str, day: int, holidays: list):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.join(OUTPUT_DIR, f"{doy}_{month}_{day}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(holidays, f, indent=2, ensure_ascii=False)
    print(f"\n📁 Saved {len(holidays)} holidays to {filename}")

if __name__ == "__main__":
    doy_input = input("Enter day-of-year number (e.g., 251 for Sep 7): ").strip()

    try:
        doy = int(doy_input)
        if not (1 <= doy <= 366):
            raise ValueError
    except ValueError:
        print("❌ Invalid day-of-year.")
        exit(1)

    month_input, day = doy_to_month_day(doy)

    print(f"🔍 Step 1: Asking Claude for all holidays on {month_input} {day}...")
    initial_holidays = ask_claude_for_initial_holidays(month_input, day)

    print(f"🧹 Step 2: Asking Claude to clean and verify the list...")
    cleaned_holidays = ask_claude_to_clean_holidays(month_input, day, initial_holidays)

    # Save as {DOY}_{Month}_{Day}.json in the absolute folder
    save_to_json(doy, month_input, day, cleaned_holidays)
