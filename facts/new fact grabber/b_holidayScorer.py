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
FACTS_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/a_raw"
SCORED_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/b_scored"
BATCH_SIZE = 1  # or 1 if you want to test smaller batches
os.makedirs(SCORED_DIR, exist_ok=True)

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
You are helping create a fun and exciting fact book for children aged 8–12 in the year 2025. You’ll be given a list of holiday names.

For each holiday, do the following:

1. Rate how interesting and exciting the holiday would be to a smart, curious 12-year-old in 2025. Use a scale from 1 to 100, where:
   - 90–100 = Absolutely awesome — kids would want to share it, laugh about it, or be amazed by it
   - 70–89 = Pretty cool — fun, odd, educational, or inspiring
   - 40–69 = Meh — appropriate but not exciting without rewriting
   - 1–39 = Boring — too dry, confusing, or just not for kids

2. Decide if the holiday is kid-friendly for ages 8–12:
   - Return true if it’s fun, weird, or educational
   - Return false if it involves war, violence, politics, or adult themes

Kids today love:
- Animals, records, space, inventions, anything funny or surprising
- Sports, music, pop culture, and totally unexpected twists

⚠️ Score **low (under 40)** if:
- It’s about someone becoming a leader, with no fun twist
- It’s a treaty, law, or milestone with no “wow”
- It names someone most kids wouldn’t know, and nothing wild happened

⚠️ These must **NEVER score above 50** unless they are truly bizarre or hilarious:
- Someone on the cover of a magazine
- Someone announces a campaign or political intention
- Someone gives a speech or is reported on by the news
- A political party is formed or someone becomes a leader
- Any “notable” adult doing something normal or expected

Also: don’t be fooled by vague words like “eccentric” or “notable.” That doesn’t make it fun for kids unless the **action** was weird, wild, or funny.

Don’t reward adult-important events. Only reward what kids would actually care about.

Now rate the following holidays.

Return a JSON array. For each holiday include:
- id
- original (same text you were given)
- score (1–100)
- is_kid_friendly (true or false)

EXAMPLES:
[
  { "id": 1, "original": "National Pizza Day", "score": 95, "is_kid_friendly": true },
  { "id": 2, "original": "National Tax Day", "score": 22, "is_kid_friendly": false }
]
"""



def extract_json_from_markdown(text):
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()

def extract_json_from_markdown(text):
    # First try: inside ```json block
    match = re.search(r"```json\s*(\[\s*{.*?}\s*\])\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: any JSON array in text
    match = re.search(r"(\[\s*{.*?}\s*\])", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return text.strip()

def log_retry_error(error_message, batch, attempt):
    with open("retry_log.txt", "a", encoding="utf-8") as log_file:
        timestamp = datetime.datetime.now().isoformat()
        ids = ", ".join(f["id"] for f in batch)
        log_file.write(f"[{timestamp}] Attempt {attempt + 1} failed for IDs: {ids}\nError: {error_message}\n\n")

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

def enhance_facts(facts, retries=2):
    for attempt in range(retries + 1):
        try:
            facts_block = "\n".join([f'{fact["id"]}: {fact["fact"]}' for fact in facts])
            full_prompt = PROMPT_HEADER + f"""

            NOW RATE ONLY THE FOLLOWING {len(facts)} FACTS. Do NOT make up your own. Stick exactly to this list:

            {facts_block}

            Respond ONLY with the JSON array of scores. Nothing else."""

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4000,
                temperature=0.7,
                timeout=90,
                messages=[{"role": "user", "content": full_prompt}]
            )

            print("🔢 Claude usage:",
                  f"\n  input_tokens:  {response.usage.input_tokens}",
                  f"\n  output_tokens: {response.usage.output_tokens}")

            raw_output = response.content[0].text
            raw_output = html.unescape(raw_output)

            if not raw_output.strip():
                raise ValueError("Empty response from Claude.")

            json_text = extract_json_from_markdown(raw_output)
            enhanced, success = safe_parse_json(json_text)

            if not success:
                print("📨 Prompt that caused the failure:\n" + full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""))
                return []

            # Merge Claude's result with your original IDs
            matched = []
            print("\n🧾 RAW RESPONSE WITH ID:")
            for i, result in enumerate(enhanced):
                if "score" in result and "is_kid_friendly" in result:
                    enriched = {
                        "id": facts[i]["id"],
                        "original": result.get("original", facts[i]["original"]),
                        "score": result["score"],
                        "is_kid_friendly": result["is_kid_friendly"]
                    }

                    matched.append(enriched)
                    print(json.dumps(enriched, indent=2, ensure_ascii=False))

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
    filename = os.path.basename(input_path).replace(".json", "")
    output_path = os.path.join(SCORED_DIR, f"{filename}_scored.json")

    print(f"🔁 Overwriting any existing file: {output_path}")


    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ Expected a JSON list of holidays.")
        return

    input_facts = [
        {
            "id": i + 1,
            "fact": holiday["name"],
            "original": holiday["name"],
            "year": "2025"  # Placeholder, since year is implicit
        }
        for i, holiday in enumerate(data)
    ]

    # input_facts = [{"id": f"{fact['year']}_{i}", "fact": fact["text"]} for i, fact in enumerate(events[:8])]


    enhanced = []
    total_batches = math.ceil(len(input_facts) / BATCH_SIZE)
    for i in tqdm(range(0, len(input_facts), BATCH_SIZE), desc="Enhancing", unit="batch"):
        batch = input_facts[i:i + BATCH_SIZE]
        batch_result = enhance_facts(batch)
        enhanced.extend(batch_result)
        time.sleep(1.2)

        # # Only process 2 batches for testing
        # if len(enhanced) >= 2 * BATCH_SIZE:
        #     break

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved rated facts to: {output_path}")
    sys.stdout.write('\a')  # Beep

    # Score summary
    score_90_100 = sum(1 for e in enhanced if 90 <= e["score"] <= 100)
    score_70_89  = sum(1 for e in enhanced if 70 <= e["score"] <= 89)
    score_40_69  = sum(1 for e in enhanced if 40 <= e["score"] <= 69)
    score_1_39   = sum(1 for e in enhanced if 1 <= e["score"] <= 39)

    print("\n📊 Score Summary:")
    print(f"🎉 90–100: {score_90_100}")
    print(f"✅ 70–89: {score_70_89}")
    print(f"🤔 40–69: {score_40_69}")
    print(f"🚫 1–39:  {score_1_39}")

    # Kid-friendliness summary
    kid_friendly_count = sum(1 for e in enhanced if e.get("is_kid_friendly") is True)
    not_kid_friendly_count = sum(1 for e in enhanced if e.get("is_kid_friendly") is False)

    print("\n🧒 Kid-Friendliness Summary:")
    print(f"👍 Kid-Friendly (true): {kid_friendly_count}")
    print(f"👎 Not Kid-Friendly (false): {not_kid_friendly_count}")





if __name__ == "__main__":
    files = list_json_files(FACTS_DIR)
    selected_file = choose_file(files)
    
    print(f"\n📂 Processing file: {selected_file}")

    input_path = os.path.join(FACTS_DIR, selected_file)

    process_file(input_path)


