import json
import requests
import os
import logging
import re
from difflib import SequenceMatcher
from collections import defaultdict, Counter

# Wikipedia API URL
WIKI_API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/"

# Month mapping
MONTH_MAPPING = {
    "January": "01", "February": "02", "March": "03", "April": "04", "May": "05", "June": "06",
    "July": "07", "August": "08", "September": "09", "October": "10", "November": "11", "December": "12"
}

# Logging setup
LOG_FILE = "debug.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG
)

def log_message(level, message):
    print(message)
    getattr(logging, level)(message)

def format_date(month, day):
    if month in MONTH_MAPPING:
        return f"{MONTH_MAPPING[month]}/{int(day):02d}"
    log_message("error", f"❌ Invalid month entered: {month}")
    return None

def is_pg_text(text):
    banned_keywords = [
        "killed", "murder", "assassinated", "war", "massacre", "terrorist",
        "suicide", "executed", "dead", "death", "hanged", "bomb", "rape",
        "shooting", "violence", "attack", "explosion", "genocide"
    ]
    return not any(word in text.lower() for word in banned_keywords)

def normalize_fact_text(text):
    return re.sub(r'\W+', '', text.strip().lower())

def is_semantic_duplicate(text1, text2, threshold=0.85):
    ratio = SequenceMatcher(None, normalize_fact_text(text1), normalize_fact_text(text2)).ratio()
    return ratio >= threshold

# Fun flag system
CATEGORY_FLAGS = {
    "space": [
        "nasa", "mars", "moon", "apollo", "space", "shuttle", "astronaut", "satellite",
        "orbit", "rocket", "telescope", "cosmos", "planet", "galaxy", "launch", "module",
        "probe", "cosmonaut", "spacex", "mission", "venus", "mercury", "iss", "hubble",
        "exploration", "spaceflight", "solar", "station", "milky way", "crater", "landing",
        "rover", "helium", "comet", "meteor", "universe", "observatory", "eclipse", "asteroid"
    ],
    "sports": [
        "football", "olympics", "basketball", "tennis", "cricket", "hockey", "athlete", "rugby",
        "championship", "goal", "team", "win", "medal", "tournament", "match", "score",
        "race", "runner", "boxing", "golf", "coach", "stadium", "fifa", "world cup",
        "pitch", "track", "swimmer", "game", "contest", "wrestling", "nba", "nfl",
        "baseball", "soccer", "ice skating", "marathon", "bobsled", "formula 1", "medalist", "esports"
    ],
    "politics": [
        "president", "prime minister", "parliament", "election", "government", "congress", "leader", "vote",
        "senate", "mayor", "governor", "diplomat", "policy", "constitution", "coalition", "legislation",
        "politician", "cabinet", "resign", "administration", "ambassador", "monarchy", "republic", "chancellor",
        "state", "nation", "treaty", "minister", "referendum", "campaign", "dictator", "democracy",
        "inauguration", "justice department", "political", "law reform", "autonomy", "regime", "authority", "federal"
    ],
    "technology": [
        "internet", "computer", "software", "device", "ai", "cyber", "web", "robot",
        "digital", "network", "hardware", "engineer", "gadget", "code", "tech", "binary",
        "chip", "processor", "algorithm", "machine", "application", "virtual", "online", "innovation",
        "android", "iphone", "cloud", "email", "smartphone", "html", "database", "server",
        "firmware", "blockchain", "data", "encryption", "malware", "programming", "startup", "wearable"
    ],
    "music": [
        "singer", "song", "music", "band", "guitar", "piano", "album", "concert",
        "record", "hit", "melody", "tune", "orchestra", "opera", "musician", "composer",
        "rap", "rock", "pop", "jazz", "hip hop", "folk", "violin", "chorus",
        "grammy", "dj", "instrument", "soundtrack", "symphony", "festival", "lyrics", "performance",
        "harmony", "anthem", "remix", "track", "bass", "vocal", "recording", "note"
    ],
    "movies_tv": [
        "movie", "film", "actor", "actress", "tv", "director", "cinema", "screenplay",
        "blockbuster", "series", "broadcast", "award", "oscar", "drama", "comedy", "animated",
        "scene", "producer", "theater", "hollywood", "celebrity", "box office", "studio", "camera",
        "premiere", "netflix", "trailer", "episode", "documentary", "filmmaker", "script", "soap opera",
        "biopic", "sitcom", "channel", "cast", "voice actor", "lead role", "special effects", "set"
    ],
    "disasters": [
        "earthquake", "tsunami", "fire", "flood", "crash", "accident", "hurricane", "tornado",
        "eruption", "landslide", "disaster", "storm", "cyclone", "explosion", "wildfire", "drought",
        "sinking", "emergency", "tragedy", "hazard", "blackout", "avalanche", "wreck", "blast",
        "epicenter", "rescue", "evacuate", "chaos", "survivor", "natural disaster", "snowstorm", "collapse",
        "toxic", "leak", "quake", "epidemic", "aftershock", "aid", "fatal", "surge"
    ],
    "royalty": [
        "king", "queen", "royal", "monarch", "crowned", "emperor", "coronation", "palace",
        "dynasty", "throne", "prince", "princess", "succession", "reign", "duke", "duchess",
        "castle", "regent", "royalty", "crown", "court", "heir", "realm", "imperial",
        "noble", "hereditary", "peer", "enthroned", "regal", "lineage", "tiara", "jewel",
        "serf", "scepter", "vassal", "knighthood", "nobility", "baron", "house", "empire"
    ],
    "exploration": [
        "explorer", "discovery", "journey", "expedition", "voyage", "navigate", "adventure", "map",
        "territory", "colonize", "path", "charted", "landed", "archipelago", "crossing", "pole",
        "globe", "ocean", "landfall", "terrain", "frontier", "navigate", "pioneer", "region",
        "sail", "travel", "outpost", "found", "route", "coast", "deep sea", "compass",
        "exploration", "drift", "mission", "border", "trail", "circumnavigate", "latitude", "longitude"
    ],
    "education": [
        "school", "university", "college", "education", "student", "teacher", "professor", "classroom",
        "degree", "campus", "curriculum", "graduate", "scholar", "exam", "tuition", "academic",
        "lecturer", "diploma", "learning", "knowledge", "textbook", "schooling", "institution", "subject",
        "research", "homework", "enroll", "bachelor", "master", "phd", "primary", "secondary",
        "class", "lesson", "library", "taught", "academy", "alumni", "coursework", "education reform"
    ],
    "inventions": [
        "inventor", "invention", "create", "engineer", "technology", "breakthrough", "discovery", "patent",
        "prototype", "machine", "innovation", "design", "tool", "mechanism", "blueprint", "developed",
        "engine", "gadget", "electric", "motor", "wireless", "robotics", "scientist", "experiment",
        "generator", "transform", "device", "science", "chemistry", "physics", "laboratory", "test",
        "formula", "material", "engineered", "industrial", "appliance", "lightbulb", "magnet", "thermodynamics"
    ],
    "literature": [
        "book", "author", "novel", "poet", "writing", "story", "essay", "published",
        "manuscript", "fiction", "literary", "editor", "poetry", "literature", "prose", "chapter",
        "read", "volume", "verse", "narrative", "autobiography", "biography", "fable", "tale",
        "journal", "diary", "classic", "fairy tale", "legend", "epic", "plot", "page",
        "critique", "review", "playwright", "bibliography", "publisher", "award", "paper", "scribe"
    ],
    "environment": [
        "climate", "pollution", "forest", "nature", "environment", "conservation", "wildlife", "green",
        "carbon", "recycle", "deforestation", "habitat", "ocean", "ecosystem", "air", "water",
        "sustainability", "plant", "tree", "renewable", "earth", "bio", "ecology", "energy",
        "organic", "natural", "emissions", "species", "land", "environmentalist", "climate change", "preserve",
        "fossil", "cleanup", "marine", "smog", "waste", "rainforest", "soil", "solar"
    ],
    "fashion": [
        "fashion", "style", "design", "clothing", "trend", "runway", "couture", "wardrobe",
        "outfit", "attire", "model", "fabric", "textile", "accessory", "dressed", "gown",
        "jewelry", "sewing", "tailor", "glamour", "appearance", "footwear", "couture", "apparel",
        "ensemble", "brand", "suit", "costume", "skirt", "shirt", "tie", "jacket",
        "vogue", "trendy", "look", "beauty", "icon", "hat", "bling", "designer"
    ],
    "transport": [
        "car", "plane", "train", "airline", "transport", "flight", "travel", "vehicle",
        "bus", "ship", "automobile", "highway", "bridge", "rail", "subway", "driver",
        "crash", "ferry", "boeing", "airbus", "metro", "pilot", "taxi", "road",
        "traffic", "motor", "wagon", "helicopter", "transit", "station", "tram", "navigation",
        "fleet", "engine", "drive", "aviation", "airfield", "cab", "runway", "commute"
    ],
    "catch_all": []  # fallback
}

def flag_fact(text):
    flags = []
    text_lower = text.lower()
    for category, keywords in CATEGORY_FLAGS.items():
        if category == "catch_all":
            continue
        if any(keyword in text_lower for keyword in keywords):
            flags.append(category)
    return flags

def assign_categories(facts_by_section):
    categorized_facts = defaultdict(list)

    for section, facts in facts_by_section.items():
        for text in facts:
            flags = flag_fact(text)
            assigned = flags[0] if flags else "catch_all"
            categorized_facts[assigned].append({
                "text": text,
                "flags": flags,
                "category": assigned
            })

    # Only keep categories with 5+ items
    final_categorized = {cat: items for cat, items in categorized_facts.items() if len(items) >= 5}
    log_message("info", f"Categories selected: {list(final_categorized.keys())}")
    return final_categorized

def fetch_wikipedia_api_facts(month, day):
    date = format_date(month, day)
    if not date:
        return {}

    url = f"{WIKI_API_URL}{date}"
    headers = {"User-Agent": "Factbook-Project (your-email@example.com)"}
    log_message("info", f"Fetching Wikipedia API events from {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "Events": [f"{item['year']} - {item['text']}" for item in data.get("events", []) if is_pg_text(item['text'])],
            "Births": [f"{item['year']} - {item['text']}" for item in data.get("births", []) if is_pg_text(item['text'])]
        }

    except requests.RequestException as e:
        log_message("error", f"⚠️ Wikipedia API request failed: {e}")
        return {}

def fetch_and_store_facts(month, day):
    log_message("info", f"📅 Collecting historical facts for {month} {day}...")
    raw_data = fetch_wikipedia_api_facts(month, day)
    enriched = assign_categories(raw_data)

    output = {
        "Wikipedia": enriched
    }

    if not enriched:
        output["Note"] = ["Oops! Looks like today is a quiet day in history. Try another one!"]

    total = sum(len(v) for v in enriched.values())
    log_message("info", f"✅ Total PG-rated and categorized events collected: {total}")

    filename = f"facts/{month}_{day}.json"
    os.makedirs("facts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=4, ensure_ascii=False)

    log_message("info", f"✅ Facts saved: {filename}")

if __name__ == "__main__":
    month = input("Enter the month (e.g., January): ").strip()
    day = input("Enter the day (e.g., 14): ").strip()

    if month not in MONTH_MAPPING:
        log_message("error", "❌ Invalid month name. Please enter a valid month.")
    else:
        fetch_and_store_facts(month, day)
