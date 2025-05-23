import json
import os
import re
from anthropic import Client
from pathlib import Path

# Claude client setup
client = Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Directories relative to script location
BASE_DIR = Path(__file__).parent.resolve()
UNSORTED_DIR = BASE_DIR / "unsorted"
OUTPUT_DIR = BASE_DIR / "newsorted"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Prompt with critical scoring + length guidance
USED_OPENERS = []

PROMPT_HEADER = """
You're helping create a children's fun fact book for curious kids aged 8 to 12.

Your job is to take a list of historical facts and return a fun, rewritten version for each fact.

Please follow these steps:

1. Analyze each fact and rate it honestly on a scale from 1 to 10 in these categories:
   - "quirkiness": Is it weird, surprising, or amusing?
   - "importance": How much did it impact history or society?
   - "kidAppeal": Would this make a 12-year-old say "Whoa!" or care?
   - "storyPotential": Could it be told with energy and imagination?
   - "inspiration": Would it make kids feel clever, curious, or brave?

⚠️ Be thoughtful and use the full scoring range:
- 1–3: Low, ordinary, or unlikely to grab kids
- 4–6: Decent, but not thrilling
- 7–8: Strong, unusual, or exciting
- 9–10: Reserved for truly extraordinary cases

2. Rewrite each fact as a one-paragraph story. Each story must include:
   - A short, catchy "title"
   - A lively, energetic "story" (one paragraph only)
   - A unique "opener" field to note the hook or first phrase
   - A closing reminder: "It happened on this day in history."

3. The total score (sum of all five values) determines how detailed the story should be:
- 4–12: Short (60–80 words)
- 13–24: Medium (100–130 words)
- 25–30: Long (up to 200 words)

🚫 Do NOT write every fact as a long story. Score critically to create variety in story length and tone.

Return ONLY a valid JSON array with one object per fact. Each object must include:
- title
- story
- opener
- quirkiness
- importance
- kidAppeal
- storyPotential
- inspiration

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
    except json.JSONDecodeError as e:
        print("❌ JSON parse failed — trying salvage mode...")
        print(f"🔍 Error: {e}")
        print(f"🔎 Starting text:\n{raw_output[:300]}\n")
        return [], False

def enhance_facts(facts):
    fact_texts = [f['fact'] for f in facts]
    used_openers_text = f"Previously used openers: {json.dumps(USED_OPENERS)}"
    facts_text = "".join([f"- {fact}\n" for fact in fact_texts])
    full_prompt = PROMPT_HEADER.replace("{USED_OPENERS}", used_openers_text) + f"\nFacts:\n{facts_text}"

    try:
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            temperature=0.7,
            messages=[{"role": "user", "content": full_prompt}]
        )
        raw_output = response.content[0].text
        print("\n🧾 RAW RESPONSE:\n" + raw_output[:1000] + ("..." if len(raw_output) > 1000 else ""))

        json_text = extract_json_from_markdown(raw_output)
        enhanced, _ = safe_parse_json(json_text)

        for orig, new in zip(facts, enhanced):
            new["id"] = orig["id"]
            if "opener" in new:
                USED_OPENERS.append(new["opener"])

        return enhanced

    except Exception as e:
        print(f"❌ Claude error: {str(e)}")
        return []

def choose_input_file():
    json_files = list(UNSORTED_DIR.glob("*_with_ids.json"))
    if not json_files:
        print("❌ No matching JSON files (ending in '_with_ids.json') found in 'unsorted'")
        return None

    print("\n📁 Available JSON files:")
    for idx, file_path in enumerate(json_files):
        print(f"{idx + 1}. {file_path.name}")

    try:
        choice = int(input("\n🔢 Enter the number of the file to process: ")) - 1
        if 0 <= choice < len(json_files):
            return json_files[choice]
        else:
            print("❌ Invalid choice.")
            return None
    except ValueError:
        print("❌ Please enter a number.")
        return None

def process_file():
    file_path = choose_input_file()
    if not file_path:
        return

    print(f"\n📖 Processing: {file_path.name}")

    with open(file_path, 'r', encoding='utf-8') as f:
        facts_data = json.load(f)

    if not isinstance(facts_data, list) or not all('fact' in f and 'id' in f for f in facts_data):
        print("❌ Input file must contain a list of objects with 'id' and 'fact'.")
        return

    test_batch = facts_data[:5]
    enhanced_facts = enhance_facts(test_batch)

    if enhanced_facts:
        base_name = file_path.stem.replace("_unsorted_with_ids", "_AI_rewritten_sorted")
        output_file = OUTPUT_DIR / f"{base_name}.json"
        with open(output_file, 'w', encoding='utf-8') as out:
            json.dump(enhanced_facts, out, indent=2, ensure_ascii=False)
        print(f"\n✅ Enhanced {len(enhanced_facts)} facts saved to:\n{output_file}")
    else:
        print("❌ No facts returned from Claude.")

if __name__ == "__main__":
    process_file()
