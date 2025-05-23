import json
import os
import re
import time
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

# Normalize fact format
def normalize_fact_format(fact):
    match = re.match(r"^[A-Za-z]+\s\d{1,2}(st|nd|rd|th)? is the day in (\d{3,4}) that (.+)", fact)
    if match:
        year = match.group(2)
        event = match.group(3).strip()
        return f"{year} - {event}"
    return fact.strip()

# Claude enhancement logic
def enhance_facts_with_claude(batch):
    prompt = f"""
You're helping create a children's fun fact book for ages 8–12.

For each historical fact below, do the following:
- Rewrite it as a fun, friendly one-paragraph story that kids can understand.
- Use varied hooks like "Imagine", "Guess what", or "Back in the day" (but not the same each time).
- Use simple, playful language — avoid complex words.
- Add a fun or surprising twist — a comparison, mini-story, or strange detail.
- Tie it into things kids relate to (sports, animals, fairness, games, creativity, food, etc.) — but only when it fits naturally.
- Make each one sound different and engaging — not formulaic.
- Categorize each fact into one of these categories: {", ".join(CATEGORIES)}.

Format your response in JSON like this:
[{{"story": "...", "category": "..."}}, ...]
Facts:
""" + "\n".join([f"- {fact}" for fact in batch])

    response = anthropic.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=4096,
        temperature=0.8,
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.content[0].text.strip()

    # Remove markdown-style JSON wrapping (```json ... ```)
    if content.startswith("```") and content.endswith("```"):
        content = "\n".join(line for line in content.splitlines() if not line.startswith("```"))

    try:
        return json.loads(content)
    except Exception as e:
        print("❌ Failed to parse Claude response:", content)
        return []

# Main function to process file
def process_file(filename, batch_size=5, max_batches=3):
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

    enriched = []
    for i in range(0, min(len(cleaned_facts), batch_size * max_batches), batch_size):
        batch = cleaned_facts[i:i + batch_size]
        print(f"🤖 Processing batch {i // batch_size + 1}...")
        result = enhance_facts_with_claude(batch)
        enriched.extend(result)
        time.sleep(1)

    output_file = filename.replace(".json", "_AI_rewritten_sorted.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=4, ensure_ascii=False)

    print(f"✅ Finished processing. Saved to {output_file}")

# Run the script
if __name__ == "__main__":
    for file in os.listdir():
        if file.endswith(".json") and not file.endswith("_AI_rewritten_sorted.json"):
            process_file(file)
