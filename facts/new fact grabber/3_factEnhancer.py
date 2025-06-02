import json
import os
import re
from anthropic import Client
from pathlib import Path
import time
import html
import sys
import math
import datetime
from tqdm import tqdm


# Path setup
FACTS_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/culled"
SORTED_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/enhanced"
BATCH_SIZE = 1  # or 1 if you want to test smaller batches
os.makedirs(SORTED_DIR, exist_ok=True)

def list_json_files(directory):
    files = [f for f in os.listdir(directory) if f.endswith(".json")]
    files.sort()
    for i, file in enumerate(files, 1):
        print(f"{i}: {file}")
    return files

def choose_file(files):
    while True:
        try:
            choice = int(input("\nEnter the number of the file to process: "))
            if 1 <= choice <= len(files):
                return files[choice - 1]
        except ValueError:
            pass
        print("Invalid choice. Try again.")

# Claude client setup
client = Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPT_HEADER = """
You're helping write a fun fact book for curious kids aged 8 to 12.

Write at a level they can understand: simple words, short sentences, clear ideas. Avoid fancy vocabulary or long explanations.

Each fact has an "id", a "fact", a "max_word_limit", and sometimes a "year". Your job is to turn it into a fun, easy-to-read story.

Use a playful tone when the topic allows — humor, surprise, or quirky wording is great for lighter facts. If the topic is serious, keep it respectful and easy to follow.

---

**1. Write the story:**

Follow these exact rules:

- Your story must be **between (max_word_limit - 30) and max_word_limit** words.
- For example, if `max_word_limit` is 140, your story must be **between 110 and 140 words**.
- If the story is **under the minimum**, that is an error. **Do not submit it. Fix it first.**
- Always write a story — never skip one.
- Add a **short, fun title**.
- Write a **single-paragraph story** with a strong, attention-grabbing first sentence.
  - Don’t begin with “Imagine...”, “In [year]...”, or any generic setup.
  - Make the opening fresh and exciting.
- Use a lively, simple style — like you're telling something cool to a smart 10-year-old.
- ⚠️ **Include the year the event happened naturally in the story — even if the year is only found in the fact text.**
  - If the fact refers to a specific year (like 1974, 2025, etc.), you must mention it clearly in the story.
  - Example: “In 1974, something amazing happened…” or “Back in 2025, Beyoncé surprised the world…”

---

**2. Add a trivia question:**

- `activity_question`: A multiple-choice question based on something clearly in the story.
- `activity_choices`: 4 answers total.
  - For fun topics, include one silly or unexpected wrong answer.
  - For serious topics, keep all answers realistic.
- `activity_answer`: The correct one.

---

**3. Add one bonus (only if it adds value):**

Pick **only one**, and keep it **under 20 words**:

- `quote`: A short, fun or thoughtful quote from someone in the story.
- `follow_up_question`: A curious, open-ended question to get kids thinking.
- `bonus_fact`: A fun or surprising detail that isn’t already in the story.

Rate how helpful the bonus is using this scale:

- 90–100: **Amazing** — clever, emotional, surprising, or sparks real curiosity.
- 70–89: **Good** — adds helpful or fun value.
- 40–69: **Okay** — adds a little something.
- Below 40: **Weak** — dull, obvious, or just repeats the story.

🎯 Only give 90+ if a smart, curious 10-year-old would say “Whoa, really?”

⚠️ Don’t include a bonus if it doesn’t help. Leave it out instead of forcing it.

Include:
- `"optional_type"` — either `"quote"`, `"follow_up_question"`, or `"bonus_fact"`
- `"optional_quality_score"` — a number from 0 to 100 based on how much the bonus improves the story

---

**4. Add 3 categories:**

Each should include:
- `"category"` — choose from the list below
- `"score"` — from 0.0 to 1.0 showing how well it fits

🎯 Valid categories:
- History’s Mic Drop Moments — wars, revolutions, treaties, global turning points  
- World Shakers & Icon Makers — powerful leaders, world changers, inspiring people  
- Big Brain Energy — discoveries, breakthroughs, tech, biology, chemistry  
- Beyond Earth — astronomy, space missions, meteorology  
- Creature Feature — cool creatures, conservation, animal records or traits  
- Vibes, Beats & Brushes — creativity, artists, music, cultural trends  
- Days That Slay — holidays, rituals, festivals, national days  
- Full Beast Mode — competitions, record-breakers, sporting firsts  
- Mother Nature’s Meltdowns — volcanoes, climate, ecosystems, nature wonders  
- The What Zone — oddities, mysteries, unusual facts

---

Return ONLY valid JSON with:

- `id`  
- `title`  
- `story`  
- `activity_question`  
- `activity_choices` (4 total)  
- `activity_answer`  
- `categories` (3 total, each with `category` and `score`)  
- `suitable_for_8_to_12_year_old` (true or false)

✅ Include just ONE of the following:
- `quote`  
- `follow_up_question`  
- `bonus_fact`  
...with the matching `optional_type` and `optional_quality_score`.

Only use straight quotes ("). Escape internal quotes as \\".
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

def log_retry_error(error_message, batch, attempt):
    with open("retry_log.txt", "a", encoding="utf-8") as log_file:
        timestamp = datetime.datetime.now().isoformat()
        ids = ", ".join(f["id"] for f in batch)
        log_file.write(f"[{timestamp}] Attempt {attempt + 1} failed for IDs: {ids}\nError: {error_message}\n\n")


def enhance_facts(facts, retries=2):
    # Check all required fields are present
    if any("score" not in f or "max_word_limit" not in f for f in facts):
        raise ValueError("One or more facts are missing 'score' or 'max_word_limit'.")

    for attempt in range(retries + 1):
        try:
            fact_texts = [
                f'- id: {f["id"]}\n  fact: {f["fact"]}\n  score: {f["score"]}\n  max_word_limit: {f["max_word_limit"]}\n  year: {f.get("year", "unknown")}'
                for f in facts
            ]
            facts_block = "\n".join(fact_texts)
            full_prompt = PROMPT_HEADER + f"\nFacts:\n{facts_block}"

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.7,
                timeout=90,
                messages=[{"role": "user", "content": full_prompt}]
            )
            
            print("🔢 Claude usage:",
                  f"\n  input_tokens:  {response.usage.input_tokens}",
                  f"\n  output_tokens: {response.usage.output_tokens}")

            raw_output = response.content[0].text
            print("\n🧾 RAW RESPONSE:\n" + raw_output[:1000] + ("..." if len(raw_output) > 1000 else ""))
            raw_output = html.unescape(raw_output)

            if not raw_output.strip():
                raise ValueError("Empty response from Claude.")

            json_text = extract_json_from_markdown(raw_output)
            enhanced, success = safe_parse_json(json_text)

            if not success:
                print("📨 Prompt that caused the failure:\n" + full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""))

            id_map = {str(f["id"]): f for f in facts}
            matched = []
            if isinstance(enhanced, dict):
                enhanced = [enhanced]  # wrap in a list if it's a single object

            for new in enhanced:
                orig = id_map.get(str(new.get("id")))
                if orig:
                    new["id"] = orig["id"]
                    new["score"] = orig["score"]  # ✅ Add the score back in
                    matched.append(new)

                else:
                    print(f"⚠️ No ID match found for: {new.get('title', '[No title]')}")


            return matched

        except Exception as e:
            print(f"❌ Claude error (attempt {attempt + 1}): {e}")
            log_retry_error(str(e), facts, attempt)
            if attempt < retries:
                time.sleep(2)
            else:
                return []


# choose_input_file and process_file stay unchanged

def process_file(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Adjust for new structure
    input_facts = [
        {
            "id": str(fact["id"]),
            "fact": fact["original"],
            "score": fact["score"],
            "max_word_limit": fact.get("max_word_limit"),
            "year": fact.get("year")
        }
        for fact in data
        if fact.get("is_kid_friendly") is True
    ]

    if not input_facts:
        print("No kid-friendly facts found.")
        return

    enhanced = []
    total_batches = math.ceil(len(input_facts) / BATCH_SIZE)
    for i in tqdm(range(0, len(input_facts), BATCH_SIZE), desc="Enhancing", unit="batch"):
        batch = input_facts[i:i + BATCH_SIZE]
        batch_result = enhance_facts(batch)
        enhanced.extend(batch_result)
        time.sleep(1.2)

    # Save to enhanced folder
    output_path = os.path.join(SORTED_DIR, Path(input_path).stem + "_enhanced.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved enhanced facts to: {output_path}")
    sys.stdout.write('\a')


if __name__ == "__main__":
    files = list_json_files(FACTS_DIR)
    selected_file = choose_file(files)
    
    print(f"\n📂 Processing file: {selected_file}")

    input_path = os.path.join(FACTS_DIR, selected_file)

    process_file(input_path)


