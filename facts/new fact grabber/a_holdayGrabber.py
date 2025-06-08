import os
import json
import calendar
import re
from anthropic import Anthropic

anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
        "[{\"name\": \"Holiday Name\", \"kid_friendly\": true}]"
    )


    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1200,
        temperature=0.0,
        messages=[{"role": "user", "content": user_input}]
    )

    try:
        return json.loads(response.content[0].text.strip())
    except Exception as e:
        print("❌ JSON parsing error (initial):", e)
        print(response.content[0].text)
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
        "[{\"name\": \"Holiday Name\", \"kid_friendly\": true}]"
    )



    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        temperature=0.0,
        messages=[
            {"role": "user", "content": cleaning_prompt},
            {"role": "user", "content": json.dumps(holidays, indent=2)}
        ]
    )

    raw = response.content[0].text.strip()

    # Extract JSON from markdown code block
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    json_text = match.group(1) if match else raw

    try:
        cleaned = json.loads(json_text)

        # Logging removed holidays
        initial_names = {h['name'] for h in holidays}
        cleaned_names = {h['name'] for h in cleaned}
        removed = initial_names - cleaned_names

        print("\n📋 Initial holidays:")
        for h in holidays:
            print(f"  - {h['name']} (kid_friendly: {h['kid_friendly']})")

        print("\n🗑️ Removed during cleanup:")
        for name in removed:
            print(f"  ✘ {name}")

        print("\n✅ Final cleaned holidays:")
        for h in cleaned:
            print(f"  ✔ {h['name']} (kid_friendly: {h['kid_friendly']})")

        return cleaned

    except Exception as e:
        print("❌ JSON parsing error (cleanup):", e)
        print(raw)
        return []

def save_to_json(month: str, day: int, holidays: list):
    os.makedirs("a_raw", exist_ok=True)
    filename = os.path.join("a_raw", f"{month}_{day}_Holidays.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(holidays, f, indent=2, ensure_ascii=False)
    print(f"\n📁 Saved {len(holidays)} holidays to {filename}")

if __name__ == "__main__":
    month_input = input("Enter month name (e.g. March): ").strip().capitalize()
    day_input = input("Enter day (1-31): ").strip()

    try:
        day = int(day_input)
        if month_input not in calendar.month_name:
            raise ValueError
    except ValueError:
        print("❌ Invalid month or day.")
        exit(1)

    print(f"🔍 Step 1: Asking Claude for all holidays on {month_input} {day}...")
    initial_holidays = ask_claude_for_initial_holidays(month_input, day)

    print(f"🧹 Step 2: Asking Claude to clean and verify the list...")
    cleaned_holidays = ask_claude_to_clean_holidays(month_input, day, initial_holidays)

    # Overwrite the original with cleaned results
    save_to_json(month_input, day, cleaned_holidays)