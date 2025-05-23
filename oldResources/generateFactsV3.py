import json
import openai
import requests
from dotenv import load_dotenv
import os
from difflib import SequenceMatcher
from urllib.parse import quote

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    raise ValueError("⚠️ OpenAI API key is missing! Set it as an environment variable.")

# Optimized categories for better fact availability
CATEGORIES = [
    "Incredible Buildings & Places", "Super Cool Science & Space"
]

# Function to search the web for fact validation
def search_web(query, month, day):
    """ Searches the web for a query and ensures the event happened on the exact date. """
    search_url = f"https://www.google.com/search?q={quote(query + f' {month} {day} in history')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=5)
        if response.status_code == 200:
            content = response.text.lower()
            return (f"{month.lower()} {day}" in content)  # Check if the date appears in results
    except Exception as e:
        print(f"Error searching web: {e}")
    
    return False  # If no results, discard fact

# Remove similar facts to prevent redundancy
def remove_similar_facts(facts, threshold=0.8):
    unique_facts = []
    for fact in facts:
        if not any(SequenceMatcher(None, fact, existing_fact).ratio() > threshold for existing_fact in unique_facts):
            unique_facts.append(fact)
    return unique_facts

# AI-generated historical facts with strict date validation
def generate_ai_content(category, month, day, num_facts=20, max_words=800):
    print(f"🤖 Generating AI content for category: {category}...")

    prompt = f"""
    Generate {num_facts} kid-friendly historical facts that occurred **strictly** on {month} {day} in history for the category "{category}".

    ⚠️ **FACT REQUIREMENTS**:  
    - Facts **must** be confirmed by reliable sources (e.g., BBC, Smithsonian, NASA, History.com).  
    - Provide **only the year** in the fact text (not the full date).  
    - Do NOT mention {month} {day} in the fact text itself, but ensure the event **only** happened on this date.  
    - Facts that **cannot** be confirmed on {month} {day} **must NOT be included**.

    ⚡ **Verification Rule**:  
    - AI must **check historical archives** to verify that each event happened on this date.
    - If a fact is **associated with a different date**, it must be **discarded**.

    🎯 **Output Format**:  
    - Each fact should be **concise, engaging, and factually accurate**.
    - No speculation or approximations—only real, recorded events.

    🚀 **Limit response to 800 words max.**
    """

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You create fun, engaging, and educational content for children's books."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1200  # Ensures ~800 words max
    )

    # Convert response into a list of facts
    facts = response.choices[0].message.content.strip().split("\n")
    facts = [fact.strip("- ") for fact in facts if fact.strip()]

    # Fact-check against online sources
    verified_facts = []
    for fact in facts:
        query = f"{fact.split(',')[0]} {month} {day}"  # Use only the year + date
        if search_web(query, month, day):  # Ensure the date is in search results
            verified_facts.append(fact)

    # Enforce strict word limit
    filtered_facts = []
    word_count = 0
    for fact in verified_facts:
        words = fact.split()
        if word_count + len(words) <= max_words:
            filtered_facts.append(fact)
            word_count += len(words)
        else:
            break  # Stop adding facts once we hit 800 words

    return remove_similar_facts(filtered_facts)  # Remove duplicates

# Fetch and store all category facts
def fetch_and_store_facts(month, day):
    print(f"📅 Collecting historical facts for {month} {day}...")

    # Generate content using AI per category
    all_facts = {}
    for category in CATEGORIES:
        print(f"📖 Processing: {category}")
        all_facts[category] = generate_ai_content(category, month, day, num_facts=20, max_words=800)

    # Store in JSON format
    facts = {"date": f"{month} {day}", "categories": all_facts}

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
