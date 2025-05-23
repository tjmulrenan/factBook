import json
import os
import re
from anthropic import Client
from pathlib import Path
import time

# Claude client setup
client = Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Directories relative to script location
BASE_DIR = Path(__file__).parent.resolve()
UNSORTED_DIR = BASE_DIR / "unsorted"
OUTPUT_DIR = BASE_DIR / "newsorted"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Tags → Category mapping
TAG_TO_CATEGORY_MAP = {
    "Space Stuff 🚀": ["space"],
    "Brainy Science 🧪": ["science", "technology", "environment"],
    "Cool Creatures 🦎": ["animals"],
    "Arts & Pop 🕺": ["arts", "music", "literature", "film_tv", "games"],
    "Powerful People 👑": ["famous_people", "leaders", "royalty"],
    "Radical Revolutions 🔥": ["revolution", "activism"],
    "Big Decisions 🏩": ["politics", "rights", "injustice", "peace"],
    "War & Conflict ⚔️": ["war"],
    "Famous Firsts 🎉": ["firsts"],
    "World Records 🏍️": ["records"],
    "Great Inventions 🚰": ["inventions", "technology"],
    "Epic Fails & Fixes 💥": ["failures", "discoveries"],
    "Brave Explorers 🌍": ["explorers", "adventures", "travel"],
    "Fun & Festivals 🎊": ["celebrations", "holidays", "culture"],
    "Weird & Wonderful 🦯": ["weird", "funny"]
}

USED_OPENERS = []

PROMPT_HEADER = """
You're helping create a children's fun fact book for curious kids aged 8 to 12.

Your job is to take a list of historical facts and return a fun, rewritten version for each fact.

Each fact will come with an "id" field. You must include this same "id" in your output so we can trace and organize the facts later.

Please follow these steps:

1. Analyze each fact and rate it honestly on a scale from 1 to 10 in these categories:
   - "quirkiness": Is it weird, surprising, or amusing?
   - "importance": How much did it impact history or society?
   - "kidAppeal": Would this make a 12-year-old say "Whoa!" or care?
   - "storyPotential": Could it be told with energy and imagination?
   - "inspiration": Would it make kids feel clever, curious, or brave?

2. Rewrite each fact as a one-paragraph story. Each story must include:
   - A short, fun, kid-friendly "title"
   - A lively "story" (1 paragraph only)
   - A unique "opener" — the first sentence or hook that draws the reader in

3. Assign 1 to 3 accurate category tags per fact. Use only from this list:
- "People Who Changed the World 👑"
- "Spectacular Science & Inventions 🔬"
- "Space & Sky 🚀"
- "Animal Wonders 🐾"
- "Sports & Epic Records 🏅"
- "Art, Music & Creative Minds 🎨"
- "Turning Points in History 🌍"
- "Nature & the Environment 🌱"
- "Celebrations & Traditions 🎊"
- "Weird, Wild & Wonderful 🦯"
- "Everyday Heroes & Helpers 💪"
- "Mysteries, Myths & Lost Legends 🕵️"

4. Add a trivia question:
- activity_question
- activity_choices (4 options)
- activity_answer (correct one)

5. Optionally include:
- draw_prompt
- bonus_fact

Return ONLY valid JSON. Each object must include:
- id
- title
- story
- opener
- categories (1–3)
- activity_question
- activity_choices (4)
- activity_answer
- draw_prompt (optional)
- bonus_fact (optional)
- quirkiness
- importance
- kidAppeal
- storyPotential
- inspiration

Use only straight quotes. Escape all internal quotes like this: \"
Previously used openers: {USED_OPENERS}
"""

def extract_json_from_markdown(text):
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()

def safe_parse_json(raw_output):
    try:
        return json.loads(raw_output), True
    except json.JSONDecodeError:
        print("❌ JSON parse failed — trying salvage mode...")
        cleaned = raw_output.replace('“', '"').replace('”', '"').replace("’", "'").replace("\r", "").replace("\n", " ")
        cleaned = re.sub(r'(?<!\\)"(?=[^,{]*:)', r'\\"', cleaned)
        try:
            return json.loads(cleaned), True
        except json.JSONDecodeError:
            print("❌ Still failed after escaping. No valid full parse.")
            return [], False

def enhance_facts(facts):
    global USED_OPENERS
    fact_texts = [f'- id: {f["id"]}\n  fact: {f["fact"]}' for f in facts]
    used_openers_text = f"Previously used openers: {json.dumps(USED_OPENERS[-5:])}"
    facts_block = "\n".join(fact_texts)
    full_prompt = PROMPT_HEADER.replace("{USED_OPENERS}", used_openers_text) + f"\nFacts:\n{facts_block}"

    try:
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            temperature=0.7,
            timeout=90,
            messages=[{"role": "user", "content": full_prompt}]
        )
        raw_output = response.content[0].text
        print("\n🧾 RAW RESPONSE:\n" + raw_output[:1000] + ("..." if len(raw_output) > 1000 else ""))
        json_text = extract_json_from_markdown(raw_output)
        enhanced, success = safe_parse_json(json_text)
        if not success:
            print("📨 Prompt that caused the failure:\n" + full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""))

        id_map = {str(f["id"]): f for f in facts}
        matched = []
        for new in enhanced:
            orig = id_map.get(str(new.get("id")))
            if orig:
                new["id"] = orig["id"]
                if "opener" in new:
                    USED_OPENERS.append(new["opener"])
                matched.append(new)
            else:
                print(f"⚠️ No ID match found for: {new.get('title', '[No title]')}")
        return matched

    except Exception as e:
        print(f"❌ Claude error: {str(e)}")
        print("📨 Prompt that caused the failure:\n" + full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""))
        return []

# choose_input_file and process_file stay unchanged
