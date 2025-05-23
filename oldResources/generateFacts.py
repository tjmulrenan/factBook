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
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("extract", "No events found.")
    return "No events found."

# Function to generate AI-enhanced content
def generate_ai_content(category, month, day, context=""):
    prompt = f"Generate a children's book-style {category} for {month} {day}. {context}"
    
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an assistant that creates fun, educational content for children."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200
    )
    return response.choices[0].message.content.strip()

# Function to fetch and generate all categories
def fetch_and_store_facts(month, day):
    events = get_wikipedia_data(month, day)
    
    # Generate additional content using AI
    famous_birthdays = generate_ai_content("list of famous birthdays", month, day, "Include historical and pop culture figures.")
    science_facts = generate_ai_content("science or technology breakthroughs", month, day, "Describe important discoveries.")
    pop_culture = generate_ai_content("pop culture events", month, day, "Include movies, books, or music releases.")
    sports_highlights = generate_ai_content("sports highlights", month, day, "List major sports events.")
    fun_facts = generate_ai_content("weird or fun fact", month, day, "Find something unusual or quirky.")
    holiday = generate_ai_content("holiday or observance", month, day, "Include worldwide or lesser-known holidays.")
    inspirational_quote = generate_ai_content("inspirational quote of the day", month, day, "Make it motivational.")
    animal_fact = generate_ai_content("animal of the day", month, day, "Pick an animal and give fun facts.")
    word_of_the_day = generate_ai_content("word of the day", month, day, "Make it educational and fun for kids.")
    joke_of_the_day = generate_ai_content("joke or riddle", month, day, "Make it fun and child-friendly.")

    # Store in JSON format
    facts = {
        "date": f"{month} {day}",
        "events": events,
        "famous_birthdays": famous_birthdays,
        "science_tech": science_facts,
        "pop_culture": pop_culture,
        "sports": sports_highlights,
        "fun_facts": fun_facts,
        "holiday": holiday,
        "quote": inspirational_quote,
        "animal_of_the_day": animal_fact,
        "word_of_the_day": word_of_the_day,
        "joke_of_the_day": joke_of_the_day
    }

    filename = f"facts/{month}_{day}.json"
    
    # Ensure directory exists
    os.makedirs("facts", exist_ok=True)

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(facts, file, indent=4, ensure_ascii=False)
    
    print(f"✅ Facts saved for {month} {day}: {filename}")

# Run the script
if __name__ == "__main__":
    month = input("Enter the month (e.g., March): ").strip()
    day = input("Enter the day (e.g., 20): ").strip()
    
    fetch_and_store_facts(month, day)
