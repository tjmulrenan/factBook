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
        "You are rewriting historical facts for a fun children's fact book. Each fact should:\n"
        "- Be rewritten in an engaging, natural style for 12-year-olds.\n"
        "- Embed the year naturally into the sentence (don't start with it).\n"
        "- Include a fun or interesting extra detail that makes the fact more exciting.\n"
        "- End as a complete story in one paragraph.\n"
        "- Suggest the most appropriate category from this list: " + ", ".join(CATEGORIES) + ".\n"
        "Respond in JSON like this:\n"
        "[{\"story\": \"...\", \"category\": \"...\"}, ...]"
    )

    facts_text = "\n".join([f"- {fact}" for fact in batch])
    full_prompt = prompt + "\nFacts:\n" + facts_text

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": full_prompt}
        ],
        temperature=0.7
    )

    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("❌ Failed to parse OpenAI response:", content)
        return []

# Main function to process a file

def process_file(filename, batch_size=5, max_batches=3):
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)

    all_facts = []
    all_facts.extend(data.get("Wikipedia", {}).get("Events", []))
    all_facts.extend(data.get("Wikipedia", {}).get("Births", []))
    all_facts.extend(data.get("Fun Facts", []))

    cleaned_facts = list(set(normalize_fact_format(fact) for fact in all_facts))

    enriched = []
    for i in range(0, min(len(cleaned_facts), batch_size * max_batches), batch_size):
        batch = cleaned_facts[i:i + batch_size]
        print(f"🧠 Processing batch {i // batch_size + 1}...")
        result = enhance_facts_with_openai(batch)
        enriched.extend(result)
        time.sleep(1)  # Respect API rate limits

    output_file = filename.replace(".json", "_AI_rewritten_sorted.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=4, ensure_ascii=False)

    print(f"✅ Finished processing. Saved to {output_file}")

# Run the script
if __name__ == "__main__":
    for file in os.listdir():
        if file.endswith(".json") and not file.endswith("_AI_rewritten_sorted.json"):
            process_file(file)
