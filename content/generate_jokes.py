import json
import os
import sys
import time
from pathlib import Path

from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import JOKES_JSON

# Anthropic API setup
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL_NAME = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

CATEGORIES = [
    "Today’s Vibe Check - What’s the mood today? Think weird weather, dramatic animals, and random seasonal chaos.",
    "History’s Mic Drop Moments - Big turning points that made the world go ‘WHAAAT?!’ — epic wars, revolutions, and game-changing deals.",
    "World Shakers & Icon Makers - Meet the legends who changed everything — rulers, rebels, geniuses, and icons who made their mark.",
    "Big Brain Energy - Mind-blowing inventions, wild science, genius ideas, and epic ‘aha!’ moments.",
    "Beyond Earth - Stuff that’s out of this world — space launches, alien signals, meteor showers, and cosmic mysteries.",
    "Creature Feature - Fur, fins, feathers and fangs — meet nature’s wildest creatures and their coolest superpowers.",
    "Vibes, Beats & Brushes - Where art meets attitude — music, dance, trends, and creativity that made the world pop.",
    "Days That Slay - Holidays and celebrations that bring the party — from the wacky to the wonderful.",
    "Full Beast Mode - Sports, stunts, and mega records — where humans (and animals) go all out.",
    "Mother Nature’s Meltdowns - Earth doing the most — volcanoes, wild weather, and nature’s power on full blast.",
    "The What Zone - Wait... what? The strangest, silliest, and most head-scratching facts you never knew you needed.",
]

def generate_jokes_for_category(category):
    prompt = f"""
    Find 20 real or classic jokes related to the theme of **{category}**.

    Guidelines:
    - The jokes can be historical, widely told, or themed around real people, places, or events in that category.
    - They should be appropriate and funny for kids aged around 12.
    - Avoid dark, mean, or inappropriate humor.
    - Use puns, playful logic, or classic-style joke structure.
    - Each joke should be on a single line or a two-line Q&A format.

    Output ONLY a JSON list like:
    ["Joke 1...", "Joke 2...", ..., "Joke 20..."]
    No extra explanations, notes, or formatting — just the JSON list.
    """


    response = anthropic.messages.create(
        model=MODEL_NAME,
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

    JOKES_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(JOKES_JSON, "w", encoding="utf-8") as f:
        json.dump(joke_data, f, indent=4, ensure_ascii=False)
    print(f"\n✅ All jokes saved to {JOKES_JSON}")

if __name__ == "__main__":
    main()
