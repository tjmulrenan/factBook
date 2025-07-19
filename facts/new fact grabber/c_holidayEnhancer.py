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
FACTS_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/b_scored"
SORTED_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/c_enhanced"
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

Each fact is about a real or unusual holiday that’s celebrated on a specific day of the year. Your job is to turn that fact into a short, playful story that explains:
- what the holiday is about,
- how people celebrate it today,
- and why it’s fun, quirky, or meaningful to mark on this day.

Write at a level kids can easily understand: short sentences, clear ideas, and simple words. Avoid fancy vocabulary, long explanations, or overly formal phrasing.

Each fact includes:
- an "id"
- a "fact" (about the holiday)
- a "score" (which sets your word count)
- sometimes a "year"

Use the score to guide your story length:
- If the score is 100, your story must be **between 80 and 100 words**
- If the score is 70, it must be **between 50 and 70 words**
- If the score is 40, it must be **between 20 and 40 words**

⚠️ Never write fewer than (score - 20) words, and never go over the score.

---

**1. Write the story:**

Follow these exact rules:

- Focus **mostly on how the holiday is celebrated today** — what people do, eat, wear, say, post, or share on this exact day.
- You may include fun facts or history about the holiday **only if it helps explain the celebration**.
- The story must **clearly say** the holiday is celebrated on *this specific calendar day* (not just “sometime” or “every year”).
- If room allows, end with a fun twist, modern trend, or curious tradition people enjoy.

- Add a **clever, catchy, or funny title** that:
  - Includes the name or idea of the holiday
  - Feels like it belongs in a fun kids’ trivia book
  - Uses wordplay, rhyme, exaggeration, or puns if they fit the vibe
  - Keep it under 8 words

- Write a **single-paragraph story** with a strong, attention-grabbing first sentence.
  - Don’t begin with “Imagine...”, “In [year]...”, or any vague setup.
  - Start with something **lively, weird, bold, or straight into the action**.

- Use a **fun, curious tone** — like you're telling your best friend the coolest thing you just found out.
  - For silly holidays, lean into goofiness!
  - For meaningful or serious days, stay respectful but still friendly and engaging.

- ⚠️ If a **specific year** is mentioned in the fact, work it naturally into the story.
  - Weave the year into a sentence smoothly — don’t tack it on awkwardly.

- ⚠️ Do not include anything that isn’t clearly appropriate for ages 8–12 — no adult themes, rude language, scary material, or mature content.

---

**2. Add a trivia question:**

- `activity_question`: A multiple-choice question based on something clearly in the story.
- `activity_choices`: 4 answers total.
  - For fun topics, include one silly or unexpected wrong answer.
  - For serious topics, keep all answers realistic.
- `activity_answer`: The correct one.

---

**3. Add one bonus (only if it adds value):**

⚠️ Pick **only one**, and keep it **under 20 words**:
- `follow_up_question`: A curious, open-ended question to get kids thinking.
- `bonus_fact`: A fun or surprising detail that isn’t already in the story.

⚠️ Don’t include a bonus if it doesn’t help. Leave it out instead of forcing it.

Include:
- `"optional_type"` — either `"follow_up_question"`, or `"bonus_fact"`

---

Return ONLY valid JSON with:

- `id`  
- `title`  
- `story`  
- `activity_question`  
- `activity_choices` (4 total)  
- `activity_answer`  
- `suitable_for_8_to_12_year_old` (true or false)

✅ Include just ONE of the following:
- `follow_up_question`  
- `bonus_fact`  
...with the matching `optional_type`.

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
                if not orig:
                    print(f"⚠️ No ID match found for: {new.get('title', '[No title]')}")
                    continue

                # Keep id and score from original
                new["id"] = orig["id"]
                new["score"] = orig["score"]

                # Handle optional_type
                if "bonus_fact" in new and new["bonus_fact"].strip():
                    new["optional_type"] = "bonus_fact"
                elif "follow_up_question" in new and new["follow_up_question"].strip():
                    new["optional_type"] = "follow_up_question"

                # Prefer one: drop follow_up if both exist
                if "bonus_fact" in new and "follow_up_question" in new:
                    del new["follow_up_question"]

                # Always use the fixed category
                new["categories"] = ["Days That Slay"]

                # Ensure all required fields exist
                required_fields = [
                    "title", "story", "activity_question", "activity_choices",
                    "activity_answer", "suitable_for_8_to_12_year_old", "categories"
                ]
                for key in required_fields:
                    if key not in new:
                        new[key] = "" if key != "activity_choices" else []

                matched.append(new)



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
    # Start IDs from 901 even if originals are 1, 2, 3...
    kid_friendly = [fact for fact in data if fact.get("is_kid_friendly") is True]
    input_facts = []

    start_id = 901
    for i, fact in enumerate(kid_friendly):
        input_facts.append({
            "id": str(start_id + i),  # Override with new ID
            "fact": fact["original"],
            "score": fact["score"],
            "max_word_limit": fact.get("max_word_limit"),
            "year": fact.get("year")
        })


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
    # Sort keys into preferred order
    field_order = [
        "id", "title", "story",
        "activity_question", "activity_choices", "activity_answer",
        "bonus_fact", "follow_up_question", "optional_type",
        "categories", "suitable_for_8_to_12_year_old", "score"
    ]

    ordered = []
    for fact in enhanced:
        ordered_fact = {k: fact[k] for k in field_order if k in fact}
        ordered.append(ordered_fact)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved enhanced facts to: {output_path}")
    sys.stdout.write('\a')


if __name__ == "__main__":
    files = list_json_files(FACTS_DIR)
    selected_file = choose_file(files)
    
    print(f"\n📂 Processing file: {selected_file}")

    input_path = os.path.join(FACTS_DIR, selected_file)

    process_file(input_path)


