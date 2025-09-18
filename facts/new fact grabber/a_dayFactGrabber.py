import os
import json
import calendar
import re
from datetime import datetime, timedelta
from anthropic import Anthropic
from anthropic._exceptions import BadRequestError, APIStatusError
# runtime toggles
SKIP_CLAUDE_DAY = os.getenv("SKIP_CLAUDE_DAY") == "1"
LEAP_YEAR = 2024  # treat as leap year for DOY mapping

def local_day_facts_fallback(month: str, day: int):
    # lightweight, deterministic “good enough” facts so the pipeline can proceed
    # No external calls; clearly labeled as approximate
    doy = (datetime(LEAP_YEAR, 1, 1) - datetime(LEAP_YEAR, 1, 1)).days  # 0
    date = datetime(LEAP_YEAR, list(calendar.month_name).index(month), day)
    day_of_year = (date - datetime(LEAP_YEAR, 1, 1)).days + 1
    days_left = 366 - day_of_year
    season_north = ("Winter","Spring","Summer","Autumn")[
        (date.month%12+3)//3 - 1
    ]
    season_south = ("Summer","Autumn","Winter","Spring")[
        (date.month%12+3)//3 - 1
    ]

    facts = [
        {"fact": f"{month} {day} is day {day_of_year} of the year in a leap year, with about {days_left} days left.", "kid_friendly": True},
        {"fact": f"In the Northern Hemisphere it’s roughly {season_north.lower()} now, but it’s {season_south.lower()} down in the Southern Hemisphere!", "kid_friendly": True},
        {"fact": f"Sunrise and sunset are shifting each day around {month} {day}—you might notice mornings getting {'darker' if season_north in ('Autumn','Winter') else 'brighter'} and evenings getting {'shorter' if season_north in ('Autumn','Winter') else 'longer'}.", "kid_friendly": True},
        {"fact": f"Trees and wildlife are reacting to the season: expect {'crunchy leaves and migrating birds' if season_north in ('Autumn','Winter') else 'busy bugs, flowers, and nesting birds'} in many places.", "kid_friendly": True},
        {"fact": f"If you look west after sunset around {month} {day}, the sky can glow with extra orange and pink—classic \"golden hour\" light for photos.", "kid_friendly": True},
        {"fact": f"Countdowns! Only {days_left} days until New Year—perfect time to start a tiny habit challenge.", "kid_friendly": True},
        {"fact": f"Weather flips by region: tropical places may be rainy while dry regions stay clear—same date, totally different vibes.", "kid_friendly": True},
        {"fact": f"Farmers often track dates like {month} {day} to time planting or harvest windows, depending on the climate zone.", "kid_friendly": True},
        {"fact": f"Stargazing tip: pick a clear night near {month} {day}, let your eyes adjust for 15 minutes, and you’ll spot way more stars.", "kid_friendly": True},
        {"fact": f"Animals notice day length! Many species use changing daylight around this date to guide migration, molting, or hibernation prep.", "kid_friendly": True},
    ]
    return facts

def doy_to_month_day(doy: int):
    base = datetime(LEAP_YEAR, 1, 1) + timedelta(days=doy - 1)
    return base.strftime("%B"), base.day  # e.g., ("September", 7)

anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def ask_claude_for_day_facts(month: str, day: int) -> list:
    if SKIP_CLAUDE_DAY:
        print("⏭️ SKIP_CLAUDE_DAY=1 — using local fallback for day facts.")
        return local_day_facts_fallback(month, day)

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

    try:
        response = anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1200,
            temperature=0.0,
            messages=[{"role": "user", "content": user_input}]
        )
        return json.loads(response.content[0].text.strip())
    except BadRequestError as e:
        # This is your “credit balance is too low” case
        print(f"⚠️ Anthropic bad request: {e}. Using local fallback facts.")
        return local_day_facts_fallback(month, day)
    except Exception as e:
        print(f"⚠️ Anthropic call failed ({type(e).__name__}): {e}. Using local fallback facts.")
        return local_day_facts_fallback(month, day)

def ask_claude_to_clean_day_facts(month: str, day: int, facts: list) -> list:
    if SKIP_CLAUDE_DAY:
        # Just pass through if skipping Claude
        return facts

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

    try:
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
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        json_text = match.group(1) if match else raw
        cleaned = json.loads(json_text)
        return cleaned
    except BadRequestError as e:
        print(f"⚠️ Anthropic bad request during cleanup: {e}. Passing through uncleaned facts.")
        return facts
    except Exception as e:
        print(f"⚠️ Cleanup failed ({type(e).__name__}): {e}. Passing through uncleaned facts.")
        return facts

def save_to_json(doy: int, month: str, day: int, facts: list):
    output_dir = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\a_rawDay"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{doy}_{month}_{day}_Facts.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)
    print(f"\n📁 Saved {len(facts)} facts to {filename}")

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

    print(f"🔍 Step 1: Asking Claude for day-based facts about {month_input} {day}...")
    initial_facts = ask_claude_for_day_facts(month_input, day)

    if not initial_facts:
        print("ℹ No initial facts returned. Using local fallback.")
        initial_facts = local_day_facts_fallback(month_input, day)

    print(f"🧹 Step 2: Cleaning/verifying...")
    cleaned_facts = ask_claude_to_clean_day_facts(month_input, day, initial_facts) or initial_facts

    save_to_json(doy, month_input, day, cleaned_facts)
