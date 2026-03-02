import datetime
import json
import math
import os
import re
import traceback
import string
import sys
import time
from pathlib import Path

from anthropic import Anthropic
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CULLED_FACTS_DIR, ENHANCED_FACTS_DIR, LOGS_DIR
FACTS_DIR = str(CULLED_FACTS_DIR)
SORTED_DIR = str(ENHANCED_FACTS_DIR)
BATCH_SIZE = 1  # or 1 if you want to test smaller batches
os.makedirs(SORTED_DIR, exist_ok=True)
MODEL_NAME = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")  # or your preferred working ID


def story_missing_month_or_day(story: str, today_str: str) -> bool:
    """
    Return True if the story is missing either the month or the day token.
    Month must appear as a whole word (e.g., 'September').
    Day may appear as 7, 07, 7th, 7ST, etc. (case-insensitive).
    """
    if not story or not today_str:
        return True

    parts = today_str.split()
    if len(parts) != 2:
        return True

    month, day_str = parts[0], str(int(parts[1]))  # normalize '07' -> '7'

    # Month present as a whole word (case-insensitive)
    month_ok = re.search(rf"\b{re.escape(month)}\b", story, flags=re.IGNORECASE) is not None

    # Day present as 7 / 07 / 7th / 7ST etc. (case-insensitive)
    day_ok = re.search(rf"\b0*{re.escape(day_str)}(?:st|nd|rd|th)?\b", story, flags=re.IGNORECASE) is not None

    return not (month_ok and day_ok)

def _norm(s: str) -> str:
    # lowercase, strip punctuation for robust substring checks
    table = str.maketrans("", "", string.punctuation)
    return s.lower().translate(table)

def digits_in(text: str) -> set:
    return set(re.findall(r"\d+", text or ""))

def contains_forbidden_how_many(text: str) -> bool:
    t = text.lower()
    # block “how many / how long / how much / how far / how old” unless numbers exist in story
    return any(k in t for k in ["how many", "how long", "how much", "how far", "how old"])

def validate_item(item: dict, story: str, year: str|int|None):
    errors = []

    # 1) answer must be substring of story (loose punctuation-insensitive check)
    if item.get("activity_answer") and story:
        if _norm(item["activity_answer"]) not in _norm(story):
            errors.append("Answer is not a verbatim substring of the story.")
    else:
        errors.append("Missing answer or story.")

    # 2) all digits in Q/choices/answer must be present in story or equal to year
    allowed_digits = digits_in(story)
    if year:
        allowed_digits.add(str(year))

    def check_digits(field_name, text):
        for d in digits_in(text or ""):
            if d not in allowed_digits:
                errors.append(f"Digit {d} in {field_name} not present in story/year.")

    check_digits("activity_question", item.get("activity_question", ""))
    for i, ch in enumerate(item.get("activity_choices", [])):
        check_digits(f"activity_choices[{i}]", ch)
    check_digits("activity_answer", item.get("activity_answer", ""))

    # 3) discourage derived “how many/how long/…”
    if contains_forbidden_how_many(item.get("activity_question","")) and not digits_in(story):
        errors.append("Question asks for counts/durations not stated in story.")

    # 4) answer must match one of the choices exactly
    if item.get("activity_answer") not in (item.get("activity_choices") or []):
        errors.append("Answer is not one of the choices.")

    return errors

def get_text_from_response(resp):
    """Works with both dict-like and SDK object responses."""
    try:
        # Anthropic SDK v1 style
        parts = getattr(resp, "content", None) or []
        texts = []
        for p in parts:
            t = getattr(p, "text", None)
            if t is None and isinstance(p, dict):
                t = p.get("text")
            if t:
                texts.append(t)
        return "\n".join(texts).strip()
    except Exception:
        pass
    # Fallbacks
    try:
        return resp["content"][0]["text"].strip()
    except Exception:
        return ""

NUMERIC_PREFIX_RE = re.compile(r"^\s*(\d+)_.*_culled\.json$", re.IGNORECASE)

def list_json_files_by_prefix(directory):
    items = []
    for f in os.listdir(directory):
        m = NUMERIC_PREFIX_RE.match(f)
        if m:
            items.append((int(m.group(1)), f))
    items.sort(key=lambda t: (t[0], t[1].lower()))
    if not items:
        print("No numeric *_culled.json files found.")
        return []
    print("Valid *_culled.json files (choose by the NUMBER at start of filename):")
    for day_num, fname in items:
        print(f"{day_num}: {fname}")
    return items

def choose_file_by_daynum(items):
    valid_numbers = {day_num: fname for day_num, fname in items}
    while True:
        raw = input("\nEnter the day number (e.g., 251): ").strip()
        if not raw.isdigit():
            print("Please enter a numeric day number (e.g., 251).")
            continue
        n = int(raw)
        if n in valid_numbers:
            return valid_numbers[n]
        print(f"No file starting with '{n}_' was found. Try again.")


# Claude client setup (guarded)
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY is not set.")
client = Anthropic(api_key=api_key)

def build_prompt_with_date(today_str: str) -> str:
    date_lock = f"""
IMPORTANT — FIXED CALENDAR DATE FOR THIS BOOK
- Today’s fixed calendar date is **{today_str}**.
- If you name the month/day in the story, it must be exactly “{today_str}”.
- Never write any other specific month/day (e.g., “August 13”). If unsure, use varied phrasing like “on this date in <YEAR>…”.
- Do NOT add new factual claims (e.g., “first,” “record,” name origins, times, distances, attendance, locations) unless they are clearly present in the given fact text.
- Do NOT introduce digits other than the given YEAR or digits already in the fact text. If you hint at quantity, use words only (“about”, “nearly”, “a few”) with **no digits**.
- Do NOT use double quotes inside any text fields (title, story, questions, choices, answers). If you need to quote a word, use single quotes (e.g., 'superhenge'). Never include a raw " character inside those fields.
"""
    return date_lock + "\n" + PROMPT_HEADER

PROMPT_HEADER = """
You're helping write a fun fact book for curious kids aged 8–12.

You will receive facts as objects with: "id", "fact", "score" (which sets the MAX word count), and sometimes "year".
Write at a level kids understand: simple words, short sentences, clear ideas, playful where appropriate.

---
1) Write the story

Rules:
- Length: between (score - 30) and score words. If score is 85, story must be 55–85 words. ±2 words tolerance max.
- One paragraph. Add a short, punchy title under 8 words.
- Strong, fresh first sentence to hook the reader. Do not start with the date or phrases like “On…”, “In…”, “Today…”, or “Imagine…”. Each fact must begin in a different style from the others (action, surprise, question, vivid scene, etc.), so openings never repeat.
- Clearly weave in the event's year AND that it happened on this same calendar date (today in history). Vary phrasing each time; avoid “on this day”.
- If it’s a birth, clearly say they were born that year.
- Do NOT invent new numbers. Only use numbers already in the fact or the given year. If you need to hint at size/quantity, use words like “about”, “nearly”, “a few” without digits.
- Disasters/accidents/conflict: do not specify death tallies. Keep neutral to gently positive where natural (do not force it). Highlight helpers, resilience, or lessons learned. Never glamorize danger; for stunts, add a clear “don’t try this” safety idea.
- Absolutely no adult content, rude language, slurs, or scary/graphic material. Keep it safe for 8–12.

Content suitability flags:
- If the core topic is an album/movie/TV show release, premiere, or standard TV channel launch, set "suitable_for_8_to_12_year_old": false. (Exception: only set true if the channel/show is historically special for kids and you clearly explain why.)
- Controversial celebrity figures (e.g., adult themes, explicit reputations, slur-based names, or content not kid-appropriate) => set "suitable_for_8_to_12_year_old": false.

(You should still produce the full object following all rules; the suitability flag controls downstream filtering.)

---
2) Add a trivia question

- activity_question: a multiple-choice question answerable **directly and explicitly** from the STORY TEXT.
- The correct answer must be a **verbatim substring** of the story (case-insensitive, ignoring punctuation). Do not paraphrase the correct answer.
- Do not ask for counts, streaks, totals, firsts/records, durations, distances, ages, or superlatives **unless those exact details (including any numbers) are already written in the story**.
- Do NOT introduce any new digits. Every digit in the question, choices, and answer must already appear in the story or be the given YEAR.
- activity_choices: exactly 4 options. For fun topics, one may be a silly wrong answer; for serious topics, keep all realistic.
- activity_answer: must exactly match one of the choices **and** appear verbatim in the story.
- Do not ask about details that weren’t mentioned in the story. Mirror the story’s wording/units so the correct answer matches cleanly.

---
3) Add ONE optional bonus (only if it adds value)

- optional_type: "follow_up_question" OR "bonus_fact"
- If included, content must be under 20 words.
- If neither helps, omit both and do not include optional_type.

---
Output format

Each object must have:

- "id"
- "title"
- "story"
- "activity_question"
- "activity_choices"  (array of 4 strings)
- "activity_answer"
- "suitable_for_8_to_12_year_old" (true/false)

Include at most ONE of:
- "follow_up_question"  (and set "optional_type": "follow_up_question")
- "bonus_fact"          (and set "optional_type": "bonus_fact")

Return ONLY a single JSON array. No headings, no explanations, no code fences.
Use straight quotes ("). Escape internal quotes as \\".
"""

def extract_json_from_markdown(text: str) -> str:
    # Prefer fenced JSON
    m = re.search(r"```json\s*(\[\s*{.*?}\s*\])\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Find first top-level array
    start = text.find("[")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(text[start:], start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1].strip()
        start = text.find("[", start + 1)

    # Last resort: any array-ish block
    m = re.search(r"(\[\s*{.*?}\s*\])", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()

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

def repair_trivia_for_item(bad_item: dict, story: str, year):
    repair_rules = """
You will receive one JSON object with fields including "title", "story", "activity_question",
"activity_choices", "activity_answer", etc.

TASK: Fix ONLY the trivia fields (activity_question, activity_choices, activity_answer) to satisfy ALL rules:

- Question must be answerable directly and explicitly from the STORY text provided.
- The correct answer must be a verbatim substring of the story (case-insensitive, ignore punctuation).
- Do NOT introduce new digits. Every digit must already appear in the story or be the given YEAR.
- No counts/streaks/firsts/durations/superlatives unless those exact details are already in the story text.
- Exactly 4 choices; the answer must exactly match one of them.

Do not change title, story, bonus fields, categories, suitability, id, or score.
Return ONLY the single corrected JSON object, no code fences, no prose.
"""
    packed = json.dumps(bad_item, ensure_ascii=False)
    msg = f"{repair_rules}\n\nYEAR: {year}\n\nSTORY:\n{story}\n\nOBJECT TO FIX:\n{packed}"
    resp = client.messages.create(
        model=MODEL_NAME,
        max_tokens=800,
        temperature=0.2,
        system="Return only a single valid JSON object, no code fences.",
        messages=[{"role": "user", "content": msg}]
    )
    fixed_raw = get_text_from_response(resp)
    obj_text = extract_json_from_markdown(fixed_raw)
    obj, ok = safe_parse_json(obj_text)
    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    return obj if ok and isinstance(obj, dict) else bad_item

def log_retry_error(error_message, batch, attempt):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOGS_DIR / "retry_log.txt", "a", encoding="utf-8") as log_file:
        timestamp = datetime.datetime.now().isoformat()
        ids = ", ".join(str(f["id"]) for f in batch)
        log_file.write(f"[{timestamp}] Attempt {attempt + 1} failed for IDs: {ids}\nError: {error_message}\n\n")

def enhance_facts(facts, retries=2, today_str=None):
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
            date_prompt = build_prompt_with_date(today_str or "this date")
            full_prompt = date_prompt + f"\nFacts:\n{facts_block}"

            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=4000,
                temperature=0.0,   # was 0.4
                top_p=0.3,
                system="Output ONLY a single valid JSON array. No code fences. No explanations.",
                messages=[{"role": "user", "content": full_prompt}]
            )

            try:
                print("🔢 Claude usage:",
                      f"\n  input_tokens:  {getattr(getattr(response, 'usage', None), 'input_tokens', 'n/a')}",
                      f"\n  output_tokens: {getattr(getattr(response, 'usage', None), 'output_tokens', 'n/a')}")
            except Exception:
                pass

            raw_output = get_text_from_response(response)
            if not raw_output.strip():
                raise ValueError("Empty response from Claude.")

            json_text = extract_json_from_markdown(raw_output)
            enhanced, success = safe_parse_json(json_text)

            if not success:
                print("📨 RAW OUTPUT (first 1200 chars):\n" + raw_output[:1200])
                print("📨 Prompt that caused the failure:\n" + full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""))

            # Map original facts by string id, including category
            id_map = {str(f["id"]): f for f in facts}
            matched = []
            if isinstance(enhanced, dict):
                enhanced = [enhanced]

            for new in enhanced:
                orig = id_map.get(str(new.get("id")))
                if not orig:
                    print(f"⚠️ No ID match found for: {new.get('title', '[No title]')}")
                    continue

                # Preserve original typed id & score
                new["id"] = orig["id"]
                new["score"] = orig["score"]

                # ✨ Always set categories from input file's single 'category'
                orig_cat = (orig.get("category") or "").strip()
                if orig_cat:
                    new["categories"] = [orig_cat]
                else:
                    new.pop("categories", None)

                matched.append(new)
                try:
                    print(json.dumps(new, indent=2, ensure_ascii=False))
                except Exception:
                    print(new)

            # 🔎 Debug: confirm month & day presence per item
            for it in matched:
                story = it.get("story", "") or ""
                month, day = (today_str or "").split()
                month_ok = re.search(rf"\b{re.escape(month)}\b", story, flags=re.IGNORECASE) is not None
                day_ok   = re.search(rf"\b0*{re.escape(str(int(day)))}(?:st|nd|rd|th)?\b", story, flags=re.IGNORECASE) is not None
                print(f"🧩 id={it['id']}: month_ok={month_ok} day_ok={day_ok} (expecting '{today_str}')")

            # ✅ Simple month/day presence check from filename date
            bad_ids = [
                it["id"] for it in matched
                if story_missing_month_or_day(it.get("story", ""), today_str or "")
            ]
            if bad_ids:
                print(f"🗓️ Date check failed for ids={bad_ids} — story missing month/day for '{today_str}'.")
                if attempt < retries:
                    time.sleep(1.0)
                    continue
                else:
                    print("⚠️ Still missing after retries; keeping current results.")

            # 🧪 Validate & auto-repair trivia once per item
            repaired = []
            for item in matched:
                story = item.get("story", "")
                year  = id_map[str(item["id"])].get("year")
                errs  = validate_item(item, story, year)
                if errs:
                    print(f"🧪 Trivia check failed for id={item['id']}: {errs}")
                    fixed = repair_trivia_for_item(item, story, year)
                    errs2 = validate_item(fixed, story, year)
                    if errs2:
                        print(f"❌ Still failing after repair for id={item['id']}: {errs2}")
                        repaired.append(item)
                    else:
                        repaired.append(fixed)
                else:
                    repaired.append(item)

            return repaired


        except Exception as e:
            print(f"❌ Claude error (attempt {attempt + 1}): {e}")
            print(traceback.format_exc())
            log_retry_error(str(e), facts, attempt)
            if attempt < retries:
                time.sleep(2)
            else:
                return []

def process_file(input_path, today_str):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ✅ Include single 'category' from the culled file (no AI choice here)
    input_facts = [
        {
            "id": str(fact["id"]),
            "fact": fact["original"],
            "score": fact["score"],
            "year": fact.get("year"),
            "category": fact.get("category")  # ✨ carry through
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
        batch_result = enhance_facts(batch, today_str=today_str)
        enhanced.extend(batch_result)
        time.sleep(1.2)

    output_path = os.path.join(SORTED_DIR, Path(input_path).stem + "_enhanced.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved enhanced facts to: {output_path}")
    sys.stdout.write('\a')


if __name__ == "__main__":
    items = list_json_files_by_prefix(FACTS_DIR)
    if not items:
        sys.exit(1)

    selected_file = choose_file_by_daynum(items)
    print(f"\n📂 Processing file: {selected_file}")

    input_path = os.path.join(FACTS_DIR, selected_file)

    m = re.match(r"^\s*\d+_([A-Za-z]+)_(\d{1,2})_culled\.json$", selected_file, re.IGNORECASE)
    if not m:
        raise SystemExit(f"❌ Could not parse month/day from filename: {selected_file}")
    TODAY_STR = f"{m.group(1)} {int(m.group(2))}"

    process_file(input_path, TODAY_STR)

