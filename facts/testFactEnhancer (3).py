import json
import os
import re
import time
import unicodedata
from anthropic import Anthropic
from pathlib import Path

# Set your Anthropic API key
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Categories for classification
CATEGORIES = [
    "Space Exploration",
    "Sporting Achievements",
    "Scientific Discoveries",
    "Famous Portraits",
    "Political History",
    "Global Conflicts",
    "Artistic Movements",
    "Technological Advances",
    "Cultural Celebrations",
    "Environmental Moments"
]

def normalize_fact_format(fact):
    match = re.match(r"^[A-Za-z]+\s\d{1,2}(st|nd|rd|th)? is the day in (\d{3,4}) that (.+)", fact)
    if match:
        year = match.group(2)
        event = match.group(3).strip()
        return f"{year} - {event}"
    return fact.strip()

def extract_json_from_markdown(text):
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()

def enhance_facts_with_claude(batch, batch_index=0):
    print(f"⚙️  Enhancing batch {batch_index + 1} with {len(batch)} facts...")
    
    prompt = f"""You're helping create a children's fun fact book for ages 8–12.

Each day’s book includes 100–200 fun historical facts. For the facts below, do the following:

1. Rewrite the fact as a fun, one-paragraph story that kids will enjoy.
   - Make it sound playful, curious, and age-appropriate.
   - Vary your hooks and avoid repeating phrases like "On this day...".
   - Use fun comparisons and highlight geography if relevant.
   - Always include a short, catchy title.
2. Assign a category to each fact:
   - Space Exploration, Sporting Achievements, Scientific Discoveries, Famous Portraits, Political History, Global Conflicts, Artistic Movements, Technological Advances, Cultural Celebrations, Environmental Moments

3. After the facts, include just 3 True/False questions and 1 imaginative “What if?” question.

Format the entire response as a JSON list:
[
  { "title": "...", "story": "...", "category": "..." },
  ...
  { "type": "true_false", "question": "...", "answer": true },
  { "type": "what_if", "prompt": "..." }
]

Facts:
""" + "\n".join([f"- {fact}" for fact in batch])

    response = anthropic.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=4096,
        temperature=0.8,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        raw_output = response.content[0].text.strip()
        if not raw_output:
            print(f"❌ Claude returned an empty response for batch {batch_index + 1}. Skipping.")
            return [], False
    except (IndexError, AttributeError) as e:
        print(f"❌ Claude response missing or malformed for batch {batch_index + 1}: {e}")
        return [], False

    raw_output = extract_json_from_markdown(raw_output)
    raw_output = unicodedata.normalize("NFKC", raw_output)

    # Save to logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    raw_path = log_dir / f"claude_batch_{batch_index + 1}_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_output)

    try:
        parsed = json.loads(raw_output)
        return parsed, len(parsed) == len(batch)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse Claude response (string): {raw_output[:120]}...")
        print(f"🔎 Error: {e}")
        print(f"📝 Raw output saved to {raw_path} for inspection.")
        print("🧪 Printing preview of the broken JSON:")
        print(raw_output[:1000])

        cleaned_output = raw_output
        cleaned_output = cleaned_output.replace('“', '"').replace('”', '"').replace('’', "'")
        cleaned_output = re.sub(r',\s*}', '}', cleaned_output)
        cleaned_output = re.sub(r',\s*\]', ']', cleaned_output)
        cleaned_output = re.sub(r'\\(?!["\\/bfnrt])', r'', cleaned_output)

        try:
            parsed = json.loads(cleaned_output)
            return parsed, len(parsed) == len(batch)
        except json.JSONDecodeError:
            print("❌ Still failed after cleaning. Trying object-by-object salvage...")

        object_blocks = re.findall(r'{.*?}', cleaned_output, re.DOTALL)
        parsed = []
        for obj_text in object_blocks:
            try:
                obj = json.loads(obj_text)
                if all(k in obj for k in ("title", "story", "category")):
                    parsed.append(obj)
            except json.JSONDecodeError:
                continue

        if parsed:
            print(f"⚠️ Parsed {len(parsed)} valid objects from partial recovery.")
            return parsed, False

        print("❌ No usable facts could be recovered.")
        return [], False

def process_file(filename, batch_size = 3, max_batches = 1):
    print(f"\n📂 Starting file: {filename}")
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)

    all_facts = []

    if isinstance(data, dict):
        all_facts.extend(data.get("Wikipedia", {}).get("Events", []))
        all_facts.extend(data.get("Wikipedia", {}).get("Births", []))
        all_facts.extend(data.get("Fun Facts", []))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                all_facts.append(item)
            elif isinstance(item, dict) and "story" in item:
                continue
            elif isinstance(item, dict) and "fact" in item:
                all_facts.append(item["fact"])

    cleaned_facts = list(set(normalize_fact_format(fact) for fact in all_facts))
    print(f"📄 Total input facts: {len(cleaned_facts)}")

    enriched = []
    seen_facts = set()
    retry_queue = []

    for i in range(0, min(10, batch_size * max_batches), batch_size):
        batch = cleaned_facts[i:i + batch_size]
        print(f"\n🚀 Processing batch {i // batch_size + 1} of {len(cleaned_facts) // batch_size + 1}")
        batch = [fact for fact in batch if fact not in seen_facts]
        if not batch:
            print("🔁 All facts in this batch already processed. Skipping.")
            continue

        result, success = enhance_facts_with_claude(batch, batch_index=i // batch_size)
        if result:
            enriched.extend(result)
            for fact in batch:
                seen_facts.add(fact)
        if not success:
            retry_queue.append(batch)
        time.sleep(1)

    if retry_queue:
        print(f"\n🔁 Retrying {len(retry_queue)} failed batches...")
        for retry_index, batch in enumerate(retry_queue):
            print(f"⏳ Retrying batch {retry_index + 1} of {len(retry_queue)}")
            batch = [fact for fact in batch if fact not in seen_facts]
            if not batch:
                continue
            result, _ = enhance_facts_with_claude(batch, batch_index=999 + retry_index)
            if result:
                enriched.extend(result)
                for fact in batch:
                    seen_facts.add(fact)
            time.sleep(1)

    print(f"\n✨ Enriched items before deduplication: {len(enriched)}")

    unique_enriched = []
    seen_stories = set()
    for item in enriched:
        story_key = item["story"][:80]
        if story_key not in seen_stories:
            unique_enriched.append(item)
            seen_stories.add(story_key)

    for idx, item in enumerate(unique_enriched, start=1):
        item["id"] = idx

    print(f"📦 Final unique facts: {len(unique_enriched)}")

    output_dir = Path("sorted")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / filename.replace(".json", "_AI_rewritten_sorted.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(unique_enriched, f, indent=4, ensure_ascii=False)

    print(f"✅ Done! Saved to {output_file}\n")

if __name__ == "__main__":
    process_file("March_29.json")