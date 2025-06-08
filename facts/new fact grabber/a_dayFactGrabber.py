import os
import json
import calendar
import re
from anthropic import Anthropic

anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def ask_claude_for_day_facts(month: str, day: int) -> list:
    user_input = (
        f"Give me at least 10 fun, surprising, or weirdly cool facts about the date {month} {day}. "
        "These facts must be about the *day itself*, not about historical events, holidays, or famous people.\n\n"
        "Facts should cover things like:\n"
        "- Where the day falls in the calendar\n"
        "- Seasonal changes in nature (animals, plants, weather, temperature shifts)\n"
        "- Changes in daylight, sunrise/sunset, or sky colors\n"
        "- Zodiac signs, moon phases, or proximity to solstices or equinoxes\n"
        "- Odd patterns or natural phenomena that often occur around this time each year\n\n"
        "Facts can come from anywhere in the world — be clear about the region if it doesn’t apply globally (e.g., 'in the Southern Hemisphere', 'in cold countries').\n\n"
        "Do not overuse soft words like 'usually' or 'often' — only use them when needed to stay accurate.\n"
        "Avoid repeating the same topic more than once (like birds, trees, or sunsets). Aim for a mix across sky, animals, plants, climate, and seasonal oddities.\n\n"
        "Vary how each fact starts. Do not begin every sentence the same way. Use a mix of formats — some can be questions, some can be bold statements, some can be silly or playful. Mention the date occasionally, but not in every fact.\n\n"
        "Keep the tone fun, light, and energetic — written for curious kids aged 8 to 12. Use simple language, short sentences, and playful phrasing. The more surprising, vivid, gross, or funny, the better.\n\n"
        "Write each fact like something a kid might blurt out to impress a friend.\n\n"
        "**Return only a valid JSON array of objects. Do not include markdown, explanations, or extra formatting. Do not wrap it in code blocks. Just return the JSON list.**"
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

def ask_claude_to_clean_day_facts(month: str, day: int, facts: list) -> list:
    cleaning_prompt = (
        f"You are cleaning and verifying a list of trivia facts about the date {month} {day}. "
        "These are not holidays or historical events, but facts about the *calendar day itself*.\n\n"
        "REMOVE any fact that:\n"
        "- Mentions a historical event, celebrity, or famous person\n"
        "- Is just the name of a holiday or celebration\n"
        "- Is vague with no seasonal, astronomical, or ecological basis (e.g., 'spring is nice')\n"
        "- Is totally unverifiable, misleading, or globally false\n"
        "- Is an exact duplicate or boring rewording of another\n\n"
        "KEEP facts that:\n"
        "- Relate to the date's place in the year (e.g., '88th day')\n"
        "- Include sunrise/sunset, equinox proximity, or moon/zodiac info\n"
        "- Mention typical weather, wildlife behavior, nature events, or seasonal transitions—especially if the region is clearly stated (e.g., 'in North America', 'in northern climates')\n"
        "- Use wording like 'usually', 'often', or 'typically' to describe recurring phenomena without overclaiming\n"
        "- Are quirky, specific, or nature-based in a way kids would enjoy\n\n"
        "Feel free to lightly reword or clarify a fact if it helps. "
        "Do NOT overclean—it's better to keep a fun and plausible fact with a clear region or seasonal note than to delete it unnecessarily.\n\n"
        "Return only the cleaned JSON list. Every item must be a dictionary with this format:\n"
        "[{\"fact\": \"Some cool calendar-related thing.\", \"kid_friendly\": true}]"
    )





    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        temperature=0.0,
        messages=[
            {"role": "user", "content": cleaning_prompt},
            {"role": "user", "content": json.dumps(facts, indent=2)}
        ]
    )

    raw = response.content[0].text.strip()

    # Extract JSON from markdown code block
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    json_text = match.group(1) if match else raw

    try:
        cleaned = json.loads(json_text)

        # Logging removed holidays
        initial_facts = {f['fact'] for f in facts}
        cleaned_facts = {f['fact'] for f in cleaned}
        removed = initial_facts - cleaned_facts

        print("\n📋 Initial day facts:")
        for f in facts:
            kid_flag = f.get("kid_friendly", "❓ missing")
            print(f"  - {f['fact']} (kid_friendly: {kid_flag})")

        print("\n🗑️ Removed during cleanup:")
        for fact in removed:
            print(f"  ✘ {fact}")

        print("\n✅ Final cleaned day facts:")
        for f in cleaned:
            kid_flag = f.get("kid_friendly", "❓ missing")
            print(f"  ✔ {f['fact']} (kid_friendly: {kid_flag})")


        return cleaned

    except Exception as e:
        print("❌ JSON parsing error (cleanup):", e)
        print(raw)
        return []

def save_to_json(month: str, day: int, facts: list):
    output_dir = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\a_rawDay"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{month}_{day}_Facts.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)
    print(f"\n📁 Saved {len(facts)} facts to {filename}")

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

    print(f"🔍 Step 1: Asking Claude for day-based facts about {month_input} {day}...")
    initial_facts = ask_claude_for_day_facts(month_input, day)

    print(f"🧹 Step 2: Asking Claude to clean and verify the list...")
    cleaned_facts = ask_claude_to_clean_day_facts(month_input, day, initial_facts)

    save_to_json(month_input, day, cleaned_facts)