import os
import json
import time
from anthropic import Anthropic

# Anthropic API setup
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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

def generate_jokes_for_category(category):
    prompt = f"""
Create 20 original, lighthearted jokes themed around **{category}**, each between 15–30 words.

The jokes should:
- Be written for kids around 12 years old
- Be fun, silly, or surprising — never dark or inappropriate
- Use wordplay, playful logic, or silly comparisons
- Fit on a single line if possible

Respond with a JSON list like:
["Joke 1...", "Joke 2...", ..., "Joke 20..."]
"""

    response = anthropic.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=1024,
        temperature=0.8,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        raw = response.content[0].text.strip()
        jokes = json.loads(raw) if raw.startswith("[") else json.loads(raw.split("```json")[-1].split("```")[0])
        if isinstance(jokes, list) and len(jokes) == 20:
            return jokes
    except Exception as e:
        print(f"⚠️ Failed to parse jokes for {category}: {e}")
    return []

def main():
    joke_data = {}
    for idx, category in enumerate(CATEGORIES, 1):
        print(f"✨ Generating jokes for: {category} ({idx}/{len(CATEGORIES)})")
        jokes = generate_jokes_for_category(category)
        if jokes:
            joke_data[category] = jokes
        else:
            print(f"❌ No jokes returned for {category}")
        time.sleep(1)

    with open("generatedJokes.json", "w", encoding="utf-8") as f:
        json.dump(joke_data, f, indent=4, ensure_ascii=False)
    print("\n✅ All jokes saved to generatedJokes.json")

if __name__ == "__main__":
    main()
