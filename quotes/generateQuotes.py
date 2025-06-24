import os
import json
import time
import re
import ast
from anthropic import Anthropic

# Anthropic API setup
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CATEGORIES = {
    "Today's Vibe Check - What’s the mood today? Think weird weather, dramatic animals, and random seasonal chaos.",
    "History's Mic Drop Moments - Big turning points that made the world go 'WHAAAT?!' — epic wars, revolutions, and game-changing deals.",
    "World Shakers & Icon Makers - Meet the legends who changed everything — rulers, rebels, geniuses, and icons who made their mark.",
    "Big Brain Energy - Mind-blowing inventions, wild science, genius ideas, and epic 'aha!' moments.",
    "Beyond Earth - Stuff that’s out of this world — space launches, alien signals, meteor showers, and cosmic mysteries.",
    "Creature Feature - Fur, fins, feathers and fangs — meet nature’s wildest creatures and their coolest superpowers.",
    "Vibes, Beats & Brushes - Where art meets attitude — music, dance, trends, and creativity that made the world pop.",
    "Days That Slay - Holidays and celebrations that bring the party — from the wacky to the wonderful.",
    "Full Beast Mode - Sports, stunts, and mega records — where humans (and animals) go all out.",
    "Mother Nature's Meltdowns - Earth doing the most — volcanoes, wild weather, and nature’s power on full blast.",
    "The What Zone - Wait... what? The strangest, silliest, and most head-scratching facts you never knew you needed.",
}

def generate_quotes_for_category(category):
    prompt = f"""
Give me 10 short real quotes that match this theme: **{category}**

Guidelines:
- Each quote must be authentic and from a real person.
- Keep it short — max 15 words.
- Format like: Name: "Quote."
- Make them appropriate, inspiring, curious, or funny for ages 8–12.
- Output ONLY a JSON list of strings:
["Name: \\"Quote.\\"", ...]
No notes, no explanations, no code blocks.
"""

    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0.4,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        raw = response.content[0].text.strip()
        print(f"\n📜 Raw response for {category}:\n{raw}\n")

        # Step 1: Find the JSON-like list in the response
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not json_match:
            raise ValueError("No list structure found in response.")

        list_text = json_match.group()

        # Step 2: Normalize smart quotes and ensure escape sequences are valid
        list_text = list_text.replace("“", "\"").replace("”", "\"")

        # Step 3: First try json.loads
        try:
            return json.loads(list_text)
        except json.JSONDecodeError:
            print("⚠️ json.loads failed, trying ast.literal_eval...")
            return ast.literal_eval(list_text)

    except Exception as e:
        print(f"⚠️ Failed to parse quotes for {category}: {e}")
    return []




def main():
    quote_data = {}
    for idx, category in enumerate(CATEGORIES, 1):
        print(f"✨ Generating quotes for: {category} ({idx}/{len(CATEGORIES)})")
        quotes = generate_quotes_for_category(category)
        if quotes:
            quote_data[category] = quotes
        else:
            print(f"❌ No quotes returned for {category}")
        time.sleep(1)

    with open("generatedquotes.json", "w", encoding="utf-8") as f:
        json.dump(quote_data, f, indent=4, ensure_ascii=False)
    print("\n✅ All quotes saved to generatedquotes.json")

if __name__ == "__main__":
    main()
