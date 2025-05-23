import json
import os
import re

# List of possible categories
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
    "Environmental Moments",
    "Uncategorized"
]

# Clean and normalize fact format
def normalize_fact_format(fact):
    match = re.match(r"^[A-Za-z]+\s\d{1,2}(st|nd|rd|th)? is the day in (\d{3,4}) that (.+)", fact)
    if match:
        year = match.group(2)
        event = match.group(3).strip()
        return f"{year} - {event}"
    return fact.strip()

# Simulate AI classification and add fun twist
def classify_and_enhance(fact):
    fact_lower = fact.lower()
    categories = []
    fun_twist = ""

    if any(word in fact_lower for word in ["space", "nasa", "probe", "moon", "mars", "astronaut"]):
        categories.append("Space Exploration")
        fun_twist = "Outer space adventure! This was a giant leap beyond Earth."

    if any(word in fact_lower for word in ["football", "baseball", "basketball", "tennis", "olympic", "skier"]):
        categories.append("Sporting Achievements")
        fun_twist = "Game on! This moment made sports history."

    if any(word in fact_lower for word in ["scientist", "discovery", "experiment", "research", "invented"]):
        categories.append("Scientific Discoveries")
        fun_twist = "Wow! A brainy breakthrough changed the world."

    if any(word in fact_lower for word in ["born", "musician", "artist", "poet", "actor", "singer"]):
        categories.append("Famous Portraits")
        fun_twist = "A star was born! Someone awesome entered the world."

    if any(word in fact_lower for word in ["president", "prime minister", "election", "government", "constitution"]):
        categories.append("Political History")
        fun_twist = "A big decision that shaped how countries work."

    if any(word in fact_lower for word in ["war", "rebellion", "uprising", "battle", "espionage"]):
        categories.append("Global Conflicts")
        fun_twist = "History wasn’t always peaceful. This was a turning point."

    if any(word in fact_lower for word in ["novel", "book", "composer", "film", "song", "painting"]):
        categories.append("Artistic Movements")
        fun_twist = "Creativity time! This moment made the world more colorful."

    if any(word in fact_lower for word in ["technology", "internet", "invention", "machine", "robot"]):
        categories.append("Technological Advances")
        fun_twist = "Beep boop! Tech leveled up on this day."

    if any(word in fact_lower for word in ["holiday", "celebration", "festival", "anniversary"]):
        categories.append("Cultural Celebrations")
        fun_twist = "Party time! People celebrated something special."

    if any(word in fact_lower for word in ["earth", "climate", "pollution", "nature", "environment"]):
        categories.append("Environmental Moments")
        fun_twist = "Go planet! This day was big for nature and the Earth."

    if not categories:
        categories.append("Uncategorized")
        fun_twist = "A curious moment in history with no clear category!"

    return {
        "fact": fact,
        "fun_twist": fun_twist,
        "categories": categories
    }

# Main AI sorting logic
def process_file(filename):
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)

    all_facts = []
    all_facts.extend(data.get("Wikipedia", {}).get("Events", []))
    all_facts.extend(data.get("Wikipedia", {}).get("Births", []))
    all_facts.extend(data.get("Fun Facts", []))

    enriched_facts = []
    for raw_fact in all_facts:
        cleaned = normalize_fact_format(raw_fact)
        enriched = classify_and_enhance(cleaned)
        enriched_facts.append(enriched)

    output_file = filename.replace(".json", "_AI_sorted.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(enriched_facts, f, indent=4, ensure_ascii=False)
    print(f"✅ Saved AI-sorted facts to: {output_file}")

# Run on all JSON files in the directory
if __name__ == "__main__":
    for file in os.listdir():
        if file.endswith(".json") and not file.endswith("_AI_sorted.json"):
            process_file(file)
