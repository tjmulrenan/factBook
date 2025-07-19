import json
import os
import re
from anthropic import Client
from pathlib import Path
import time
import html
import sys
import math
import datetime
from tqdm import tqdm


# Path setup
FACTS_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/3_culled"
SORTED_DIR = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/4_enhanced"
BATCH_SIZE = 1  # or 1 if you want to test smaller batches
os.makedirs(SORTED_DIR, exist_ok=True)

def list_json_files(directory):
    files = [f for f in os.listdir(directory) if f.endswith(".json")]
    files.sort()
    for i, file in enumerate(files, 1):
        print(f"{i}: {file}")
    return files

def choose_file(files):
    while True:
        try:
            choice = int(input("\nEnter the number of the file to process: "))
            if 1 <= choice <= len(files):
                return files[choice - 1]
        except ValueError:
            pass
        print("Invalid choice. Try again.")

# Claude client setup
client = Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPT_HEADER = """
You're helping write a fun fact book for curious kids aged 8 to 12.

Write at a level they can understand: simple words, short sentences, clear ideas. Avoid fancy vocabulary or long explanations.

Each fact has an "id", a "fact", a "score" (which also sets the max word count), and sometimes a "year". Your job is to turn it into a fun, easy-to-read story.

Use a playful tone when the topic allows — humor, surprise, or quirky wording is great for lighter facts. If the topic is serious, keep it respectful and easy to follow.

---

**1. Write the story:**

Follow these exact rules:

- Your story must be **between (score - 30) and score** words. The `score` is also your max word count.  
- ⚠️ A tiny range of ±2 words is okay, but don't go outside that unless absolutely necessary.
- If the story is **under the minimum**, that’s an error. **Do not submit it. Fix it first.**  
- Always write a story — never skip one.  

- Add a **short, fun title**.  
  - Keep it under 8 words. Make it punchy and engaging — something that makes a kid want to read more!

- Write a **single-paragraph story** with a strong, attention-grabbing first sentence.  
  - Don’t begin with “Imagine...”, “In [year]...”, or any generic setup.  
  - Make the opening fresh and exciting.  

- Use a lively, simple style — like you're telling something cool to a smart 10-year-old.  
  - If you use a big or tricky word, quickly explain it in a way a smart 12-year-old would get.

-⚠️ Your story must clearly show when the event happened — including both the year and the fact that it took place on this exact calendar date.

-The date reference must feel natural and woven into the story, not robotic or copy-pasted.

-❌ Don’t just start every story with “On March 29th, [year]…” — that’s too repetitive and flat.

-✅ Instead, invent a fresh, creative way to mention the date and year within the context of the story — as if you were telling it aloud to a curious kid. The phrasing should change every time and never sound formulaic.

- ⚠️ If the fact is about someone’s **birth**, clearly say something like “they were born in 1969” or “she was born that year.”

- ⚠️ The reader should always feel like this moment is part of what makes **today special** — but never in a repetitive or formulaic way.
- ⚠️ The `score` is not just a rating — it directly determines the story's word limit. So if the score is 85, the story must be between 55 and 85 words.  

- ⚠️ Do not include anything that isn’t clearly appropriate for ages 8–12 — that means no adult content, mature themes, rude language, violent or scary material, or anything else unsuitable for kids, **even if it appears in names, titles, lyrics, or quotes**. 

- ⚠️ Do not use record releases, album drops, or movie premieres as standalone events — they are not exciting or meaningful enough for this book.

- ⚠️ Skip stories that are just about a performer’s **first radio show**, **TV debut**, or **award win**, unless something truly unusual or surprising happened.

- ⚠️ Avoid boring or flat stories that have no real twist. “They were born and got famous” isn’t enough — we want curious, quirky, or wow moments.

- ⚠️ If the fact involves a name, title, lyric, or band with any **inappropriate or adult-themed language**, skip it entirely — even if it’s indirect (like certain band names or shows).

- ⚠️ Your story must clearly show that the event happened on the **same calendar date** — today in history.  
  - Avoid saying “on this day” or anything too formulaic. Find natural, varied ways to show the date connection.

---

**2. Add a trivia question:**

- `activity_question`: A multiple-choice question based on something clearly in the story.
- `activity_choices`: 4 answers total.
  - For fun topics, include one silly or unexpected wrong answer.
  - For serious topics, keep all answers realistic.
- `activity_answer`: The correct one.

---

**3. Add one bonus (only if it adds value):**

⚠️ Pick **only one**, and keep it **under 20 words**:
- `follow_up_question`: A curious, open-ended question to get kids thinking.
- `bonus_fact`: A fun or surprising detail that isn’t already in the story.

⚠️ Don’t include a bonus if it doesn’t help. Leave it out instead of forcing it.

Include:
- `"optional_type"` — either `"follow_up_question"`, or `"bonus_fact"`

---

**4. Add 3 categories:**

Each should include:
- `"category"` — choose from the list below
- `"score"` — from 0.0 to 1.0 showing how well it fits  
  - 1.0 = perfect match  
  - 0.7 = pretty good fit  
  - below 0.5 = weak fit — only use if there’s no better option

🎯 Valid categories:
- History’s Mic Drop Moments — wars, revolutions, treaties, global turning points  
- World Shakers & Icon Makers — powerful leaders, world changers, inspiring people  
- Big Brain Energy — discoveries, breakthroughs, tech, biology, chemistry  
- Beyond Earth — astronomy, space missions, meteorology  
- Creature Feature — cool creatures, conservation, animal records or traits  
- Vibes, Beats & Brushes — creativity, artists, music, cultural trends  
- Full Beast Mode — competitions, record-breakers, sporting firsts  
- Mother Nature’s Meltdowns — volcanoes, climate, ecosystems, nature wonders  
- The What Zone — oddities, mysteries, unusual facts

---

Return ONLY valid JSON with:

- `id`  
- `title`  
- `story`  
- `activity_question`  
- `activity_choices` (4 total)  
- `activity_answer`  
- `categories` (3 total, each with `category` and `score`)  
- `suitable_for_8_to_12_year_old` (true or false)

✅ Include just ONE of the following:
- `follow_up_question`  
- `bonus_fact`  
...with the matching `optional_type`.

Only use straight quotes ("). Escape internal quotes as \\".
"""




def extract_json_from_markdown(text):
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()

def safe_parse_json(raw_output):
    try:
        return json.loads(raw_output), True
    except json.JSONDecodeError:
        print("❌ JSON parse failed — trying salvage mode...")
        cleaned = raw_output.replace('“', '"').replace('”', '"').replace("’", "'").replace("\r", "").replace("\n", " ")
        cleaned = re.sub(r'(?<!\\)"(?=[^,{]*:)', r'\\"', cleaned)
        try:
            return json.loads(cleaned), True
        except json.JSONDecodeError:
            print("❌ Still failed after escaping. No valid full parse.")
            return [], False

def log_retry_error(error_message, batch, attempt):
    with open("retry_log.txt", "a", encoding="utf-8") as log_file:
        timestamp = datetime.datetime.now().isoformat()
        ids = ", ".join(f["id"] for f in batch)
        log_file.write(f"[{timestamp}] Attempt {attempt + 1} failed for IDs: {ids}\nError: {error_message}\n\n")


def enhance_facts(facts, retries=2):
    # Check all required fields are present
    if any("score" not in f for f in facts):
        raise ValueError("One or more facts are missing 'score'.")

    for attempt in range(retries + 1):
        try:
            fact_texts = [
                f'- id: {f["id"]}\n  fact: {f["fact"]}\n  score: {f["score"]}\n  year: {f.get("year", "unknown")}'
                for f in facts
            ]
            facts_block = "\n".join(fact_texts)
            full_prompt = PROMPT_HEADER + f"\nFacts:\n{facts_block}"

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.7,
                timeout=90,
                messages=[{"role": "user", "content": full_prompt}]
            )
            
            print("🔢 Claude usage:",
                  f"\n  input_tokens:  {response.usage.input_tokens}",
                  f"\n  output_tokens: {response.usage.output_tokens}")

            raw_output = response.content[0].text
            print("\n🧾 RAW RESPONSE:\n" + raw_output[:1000] + ("..." if len(raw_output) > 1000 else ""))
            raw_output = html.unescape(raw_output)

            if not raw_output.strip():
                raise ValueError("Empty response from Claude.")

            json_text = extract_json_from_markdown(raw_output)
            enhanced, success = safe_parse_json(json_text)

            if not success:
                print("📨 Prompt that caused the failure:\n" + full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""))

            id_map = {str(f["id"]): f for f in facts}
            matched = []
            if isinstance(enhanced, dict):
                enhanced = [enhanced]  # wrap in a list if it's a single object

            for new in enhanced:
                orig = id_map.get(str(new.get("id")))
                if orig:
                    new["id"] = orig["id"]
                    new["score"] = orig["score"]  # ✅ Add the score back in
                    matched.append(new)

                else:
                    print(f"⚠️ No ID match found for: {new.get('title', '[No title]')}")


            return matched

        except Exception as e:
            print(f"❌ Claude error (attempt {attempt + 1}): {e}")
            log_retry_error(str(e), facts, attempt)
            if attempt < retries:
                time.sleep(2)
            else:
                return []


# choose_input_file and process_file stay unchanged

def process_file(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Adjust for new structure
    input_facts = [
        {
            "id": str(fact["id"]),
            "fact": fact["original"],
            "score": fact["score"],
            "year": fact.get("year")
        }
        for fact in data
        if fact.get("is_kid_friendly") is True
    ]

    if not input_facts:
        print("No kid-friendly facts found.")
        return

    enhanced = []
    total_batches = math.ceil(len(input_facts) / BATCH_SIZE)
    for i in tqdm(range(0, len(input_facts), BATCH_SIZE), desc="Enhancing", unit="batch"):
        batch = input_facts[i:i + BATCH_SIZE]
        batch_result = enhance_facts(batch)
        enhanced.extend(batch_result)
        time.sleep(1.2)

    # Save to enhanced folder
    output_path = os.path.join(SORTED_DIR, Path(input_path).stem + "_enhanced.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved enhanced facts to: {output_path}")
    sys.stdout.write('\a')


if __name__ == "__main__":
    files = list_json_files(FACTS_DIR)
    selected_file = choose_file(files)
    
    print(f"\n📂 Processing file: {selected_file}")

    input_path = os.path.join(FACTS_DIR, selected_file)

    process_file(input_path)


