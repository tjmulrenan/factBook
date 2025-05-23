import json
import os
import re
import time
import openai
from pathlib import Path

# Set your OpenAI API key (assumes it's set in environment variables)
openai.api_key = os.getenv("OPENAI_API_KEY")

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

# Rewrites and classifies a batch of facts using OpenAI (new API syntax)

def enhance_facts_with_openai(batch):
    prompt = (
        "You're helping create a children's fun fact book for ages 8–12. For each historical fact below, do the following:\n"
        "- Rewrite it as a one-paragraph story that's fun, friendly, and easy to understand.\n"
        "- Speak directly to the reader using an engaging hook or intro, but vary your tone and don't repeat phrases.\n"
        "- Use simple language with no complicated words.\n"
        "- Add a fun or surprising twist to each fact (like a comparison, wow moment, or strange detail).\n"
        "- Make each story feel unique and not like the others. Avoid using the same formula or sentence structures repeatedly.\n"
        "- Gently explain anything that might be unfamiliar to a kid.\n"
        "- Fit each fact into one of these categories: " + ", ".join(CATEGORIES) + ".\n"
        "Format your response as JSON like this:\n"
        "[{\"story\": \"...\", \"category\": \"...\"}, ...]"
    )

    facts_text = "\n".join([f"- {fact}" for fact in batch])
    full_prompt = prompt + "\nFacts:\n" + facts_text

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": full_prompt}
        ],
        temperature=0.9
    )

    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("❌ Failed to parse OpenAI response:", content)
        return []

# Main function to process a file

def process_file(filename, batch_size=5, max_batches=1):
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
        print(f"🧠 Processing batch {i // batch_size + 1}...")
        result = enhance_facts_with_openai(batch)
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