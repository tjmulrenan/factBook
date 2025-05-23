import json
import os
import re
import time
from anthropic import Client
from pathlib import Path

# Set up Anthropic client
anthropic = Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Prompt template
USED_OPENERS = []

PROMPT_HEADER = """
You're helping create a children's fun fact book for curious kids aged 8 to 12.

For each historical fact below:

1. Start by **analyzing the fact** and identifying key traits:
   - Is it about someone quirky or unexpected?
   - Is it historically important or serious?
   - Is it adventurous, mysterious, or funny?
   - Could it be emotionally powerful or inspiring?

2. Based on that analysis, give the fact these scores (1–10):
   - "quirkiness": How odd, funny, or surprising is it?
   - "importance": How significant was it in history?
   - "kidAppeal": How likely is it to make a 12-year-old say “Whoa, cool!”?
   - "storyPotential": Does it have enough detail or energy to become a great story?
   - "inspiration": Could it make a kid feel brave, clever, or curious?

3. Use these scores to decide how to tell the story:
   - Quirky facts should be playful or weird — lean into the odd stuff.
   - Important facts can be more serious, inspiring, or dramatic.
   - High kidAppeal means fun details, wild comparisons, or jokes.
   - High inspiration means highlight bravery, creativity, or perseverance.

4. Then **rewrite the fact** as a fun, one-paragraph story:
   - Use vivid, energetic language and a variety of hooks.
   - Avoid using the same opening style more than once per batch. Record the opening phrase or style used for each story in an `opener` field. You’ll be given a list of previously used openers to help you avoid repeats:

Previously used openers: {USED_OPENERS}
   - Tie it to something cool if it fits — but don’t force it.
   - End with a reminder that it happened on this day in history.

5. Give the story a short, catchy title.

Use the total score to guide how detailed the story should be:
- Total score 4–12: short version (~60–80 words)
- Total score 13–24: medium version (~100–130 words)
- Total score 25–30: long, vivid version (up to 180–200 words)
Keep all stories to a single paragraph.
"""

UNSORTED_DIR = Path("C:/Users/tmulrenan/Desktop/Factbook Project/facts/unsorted")
OUTPUT_DIR = Path("C:/Users/tmulrenan/Desktop/Factbook Project/facts/sorted")

def extract_json_from_markdown(text):
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()

def safe_parse_json(raw_output):
    try:
        return json.loads(raw_output), True
    except json.JSONDecodeError as e:
        print("❌ JSON parse failed — trying salvage mode...")
        print(f"🔍 Parse error: {e}")
        print(f"🔎 Offending string starts with:\n{raw_output[:300]}...\n")

        cleaned_output = raw_output
        cleaned_output = cleaned_output.replace('“', '"').replace('”', '"').replace("’", "'")
        cleaned_output = re.sub(r',\s*}', '}', cleaned_output)
        cleaned_output = re.sub(r',\s*]', ']', cleaned_output)

        object_blocks = re.findall(r'{.*?}', cleaned_output, re.DOTALL)
        parsed = []
        for obj_text in object_blocks:
            try:
                obj = json.loads(obj_text)
                if all(k in obj for k in ("title", "story")):
                    parsed.append(obj)
            except json.JSONDecodeError:
                continue

        if parsed:
            print(f"⚠️ Recovered {len(parsed)} valid objects.")
            return parsed, False
        else:
            print("❌ No usable facts recovered.")
            return [], False

def enhance_batch(batch, batch_index):
    print(f"🧠 Sending batch {batch_index + 1} to Claude with {len(batch)} facts...")

    used_openers_text = f"Previously used openers: {json.dumps(USED_OPENERS)}"
    facts_text = "".join([f"- {fact}\n" for fact in batch])
    full_prompt = PROMPT_HEADER.replace("{USED_OPENERS}", used_openers_text) + f"\nFacts:\n{facts_text}"

    try:
        response = anthropic.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            temperature=0.7,
            messages=[
                {"role": "user", "content": full_prompt}
            ]
        )

        raw_output = response.content[0].text
        json_text = extract_json_from_markdown(raw_output)
        facts, clean_parse = safe_parse_json(json_text)

        if facts:
            for fact in facts:
                if 'opener' in fact:
                    USED_OPENERS.append(fact['opener'])
            return facts
        else:
            print(f"❌ Failed to process batch {batch_index + 1}")
            return []

    except Exception as e:
        print(f"❌ Error processing batch {batch_index + 1}: {str(e)}")
        return []

def process_files():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for file_path in UNSORTED_DIR.glob("*.txt"):
        print(f"\n📖 Processing {file_path.name}...")

        with open(file_path, 'r', encoding='utf-8') as f:
            facts = [line.strip() for line in f if line.strip()]

        batch_size = 5
        all_enhanced_facts = []

        for i in range(0, len(facts), batch_size):
            batch = facts[i:i + batch_size]
            enhanced_facts = enhance_batch(batch, i // batch_size)
            all_enhanced_facts.extend(enhanced_facts)
            time.sleep(1)

        if all_enhanced_facts:
            output_file = OUTPUT_DIR / f"enhanced_{file_path.name}"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_enhanced_facts, f, indent=2)
            print(f"✅ Saved {len(all_enhanced_facts)} enhanced facts to {output_file}")

if __name__ == "__main__":
    process_files()
