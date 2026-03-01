import requests
import json
import openai  # Install with: pip install openai
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    raise ValueError("⚠️ OpenAI API key is missing! Set it as an environment variable.")

# Wikipedia API to fetch events and birthdays
def get_wikipedia_data(month, day):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{month}_{day}"
    print(f"🔍 Fetching Wikipedia data for {month} {day}...")
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("extract", "No events found.")
    return "No events found."

# Function to generate AI-enhanced content
def generate_ai_content(category, month, day, num_facts=20):
    print(f"🤖 Generating AI content for category: {category}...")
    prompt = f"Generate {num_facts} fun, kid-friendly historical facts for the category '{category}' on {month} {day}. Keep it engaging and educational."
    
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You create fun, engaging, and educational content for children's books."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1000
    )
    return response.choices[0].message.content.strip()

# Expanded categories based on book structure
CATEGORIES = [
    "Historic Landmarks", "Scientific Discoveries", "Famous Portraits", "Musical Milestones", "Technology Advances", "Sporting Achievements", "Space Exploration", "Fashion Trends", "Artistic Movements", "Literary Anniversaries", "Global Conflicts", "Natural Wonders", "Animal Conservation", "Cultural Celebrations", "Holidays and Traditions", "Architectural Milestones", "Political History", "Medical Breakthroughs", "World Records", "Environmental Moments",
    "Famous Inventions", "Humanitarian Efforts", "Great Explorations", "Famous Speeches", "Unusual World Events", "Breakthroughs in Physics", "Historic Laws & Policies", "Famous Paintings & Artworks", "Important Archaeological Finds", "Famous Battles & Military Strategies", "Space Missions & Discoveries", "Historical Fashion Statements", "Pioneers of Medicine", "Engineering Feats", "Maritime History", "Aviation Milestones", "Mythological & Folklore Events", "Historical Crime & Justice", "Famous Culinary Moments", "Broadcasting & Media History"
]

# Function to fetch and generate all categories
def fetch_and_store_facts(month, day):
    print(f"📅 Starting fact collection for {month} {day}...")
    events = get_wikipedia_data(month, day)
    
    # Generate additional content using AI per category
    all_facts = {}
    for category in CATEGORIES:
        print(f"📖 Processing: {category}")
        all_facts[category] = generate_ai_content(category, month, day, num_facts=20)
    
    # Store in JSON format
    facts = {"date": f"{month} {day}", "events": events, "categories": all_facts}
    
    filename = f"facts/{month}_{day}.json"
    
    # Ensure directory exists
    os.makedirs("facts", exist_ok=True)
    
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(facts, file, indent=4, ensure_ascii=False)
    
    print(f"✅ Facts saved for {month} {day}: {filename}")
    print("🎉 Fact collection complete!")

# Run the script
if __name__ == "__main__":
    month = input("Enter the month (e.g., March): ").strip()
    day = input("Enter the day (e.g., 20): ").strip()
    
    fetch_and_store_facts(month, day)
