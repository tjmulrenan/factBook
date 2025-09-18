import json
import os
import re
from anthropic import Anthropic
import time
import html
import sys
import math
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

try:
    # Optional, depending on SDK version
    from anthropic import RateLimitError, APIError, APIStatusError, APIConnectionError
except Exception:
    RateLimitError = APIError = APIStatusError = APIConnectionError = ()

# ---- Anthropic client (modern SDK) ----
API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY is not set. In PowerShell: `$env:ANTHROPIC_API_KEY='YOUR_KEY'`")
anthropic = Anthropic(api_key=API_KEY)
# ---------------------------------------

# ---- debug toggles ----
PRINT_MODEL_JSON = False          # print the model's raw JSON array text
PRINT_PARSED_JSON = False        # pretty-print the parsed Python list
PRINT_ENRICHED = False            # print each enriched object you save
# ------------------------
# --- add near your imports ---
import threading

_retry_gate_lock = threading.Lock()
_next_retry_earliest = 0.0  # used to space out herd retries

BATCH_SIZE = 1
MAX_CONCURRENCY = 5   # fire off 50 at a time 🚀
PIVOT_DAY_OF_YEAR = 274  # Oct 1 pivot (non-leap). Rotates order to Oct→Nov→Dec→Jan→…→Sep.
# Path setup
FACTS_DIR = r"C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/1_raw"
SCORED_DIR = r"C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/2_scored"
os.makedirs(SCORED_DIR, exist_ok=True)

def retry_backoff_sleep(attempt: int):
    """
    Infinite backoff: gentle growth to appease acceleration limit.
    attempt: 0,1,2,...
    """
    base = 1.6 ** attempt          # slower than 2**n (nicer for ramp limits)
    jitter = random.uniform(0.6, 1.4)
    time.sleep(base * jitter)

def is_retryable_error(e: Exception) -> bool:
    msg = str(e).lower()
    code = getattr(e, "status_code", None)
    # Anthropic SDK can raise APIError-like types, but string matching still helps
    if code in (429, 500, 502, 503, 504):
        return True
    return (
        "rate_limit" in msg
        or "429" in msg
        or "timeout" in msg
        or "temporarily unavailable" in msg
        or "connection aborted" in msg
        or "connection reset" in msg
        or "connection error" in msg
        or "remote end closed connection" in msg
        or "bad gateway" in msg
        or "service unavailable" in msg
        or "gateway timeout" in msg
    )


def backoff_sleep(attempt):
    # attempt = 0, 1, 2...
    base = 2 ** attempt
    jitter = random.uniform(0, 1)
    wait = base + jitter
    print(f"⏳ Backing off {wait:.1f}s (attempt {attempt+1})...")
    time.sleep(wait)

def already_scored_filename(input_filename: str) -> str:
    base, _ = os.path.splitext(os.path.basename(input_filename))  # e.g. "123_May_2"
    return os.path.join(SCORED_DIR, f"{base}_scored.json")

def is_already_done(input_filename: str) -> bool:
    out = already_scored_filename(input_filename)
    if not os.path.exists(out):
        return False
    try:
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            isinstance(data, list) and len(data) > 0
            and all(isinstance(x, dict) and "original" in x for x in data)
        )
    except Exception:
        return False

def list_json_files(directory):
    files = [f for f in os.listdir(directory) if f.lower().endswith(".json")]

    # Month helpers (fallback if no leading day-of-year number is present)
    month_names = [
        "january","february","march","april","may","june",
        "july","august","september","october","november","december"
    ]
    # Desired rotation: Oct, Nov, Dec, Jan, …, Sep
    rotated_months = ["october","november","december"] + month_names[:9]
    month_rank = {m: i for i, m in enumerate(rotated_months)}

    def leading_int(fname: str):
        m = re.match(r"\s*(\d+)_", fname)
        return int(m.group(1)) if m else None

    def month_in_name(fname: str):
        low = fname.lower()
        for m in month_names:
            # match month as a whole word somewhere in the filename
            if re.search(rf"\b{m}\b", low):
                return m
        return None

    def key_fn(fname: str):
        n = leading_int(fname)
        if n is not None:
            # Try to guess whether your numbering is 1..366 or 1..365. 366 is fine for your 366-book plan.
            base = 366 if 1 <= n <= 366 else 365
            rotated = (n - PIVOT_DAY_OF_YEAR) % base
            return (0, rotated, fname.lower())

        # Fallback: use month name if present
        m = month_in_name(fname)
        if m is not None:
            return (1, month_rank.get(m, 999), fname.lower())

        # Final fallback: plain filename
        return (2, fname.lower())

    files.sort(key=key_fn)

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

# Anthropic client (modern SDK)

PROMPT_HEADER = """
You are helping create a fun and exciting fact book for children aged 8–12 in the year 2025. You’ll be given a list of historical events.

For each event, do the following:

1) Rate how interesting and exciting the fact would be to a smart, curious 12-year-old in 2025. Use a scale from 1 to 100:
   - 90–100 = Absolutely awesome — kids would want to share it, laugh about it, or be amazed by it
   - 70–89  = Pretty cool — fun, odd, educational, or inspiring
   - 40–69  = Meh — appropriate but not exciting without rewriting
   - 1–39   = Boring — too dry, confusing, or just not for kids
   - Boring, flat stories with no twist or “wow” MUST score under 40.

2) Decide if the fact is kid-friendly for ages 8–12:
   - Return true if it’s fun, weird, or educational and clearly age-appropriate.
   - Return false if it involves war, violence, politics, adult themes, or is simply not appealing to kids.
   - ⚠️ Do NOT include anything that isn’t clearly appropriate for ages 8–12 — no adult content, mature themes,
     rude/profane language, slurs, violent or scary material, or anything else unsuitable for kids — even if it appears
     in names, titles, lyrics, or quotes. If any such content is present, set is_kid_friendly to false.

3) Categorize the event: pick EXACTLY THREE categories from the list below and give a 0.0–1.0 score for each
   showing how strong the fit is:
   - History’s Mic Drop Moments — wars, revolutions, treaties, global turning points
   - World Shakers & Icon Makers — powerful leaders, world changers, inspiring people
   - Big Brain Energy — discoveries, breakthroughs, tech, biology, chemistry
   - Beyond Earth — astronomy, space missions, meteorology
   - Creature Feature — cool creatures, conservation, animal records or traits
   - Vibes, Beats & Brushes — creativity, artists, music, cultural trends
   - Full Beast Mode — competitions, record-breakers, sporting firsts
   - Mother Nature’s Meltdowns — volcanoes, climate, ecosystems, nature wonders
   - The What Zone — oddities, mysteries, unusual facts

   Scoring guide:
   - 1.0 = perfect match
   - 0.7 = pretty good fit
   - below 0.5 = weak fit — only use if there’s no better option

STRICT DOWN-WEIGHTS (score low and/or set not kid-friendly when applicable):
- “Firsts” that are just media/appearance/admin moments with no kid-wow: first radio show, TV debut, award win,
  concert performance, song/album release, album or movie “hits” or chart success. These are NOT enough on their own.
  Only score higher if something genuinely special happened (wild record, viral cultural moment kids recognize, funny twist,
  science tie-in, etc.).
- Generic concerts, song releases, album/movie “hits”, and routine award wins should score low unless there’s a spectacular twist.
- Boring adult milestones (talks, hires, promotions, ceremonies) should score low.
- **Controversial celebrity figures (e.g., known for adult themes, explicit content, scandals, or slur-based names) should always
  be marked not kid-friendly and scored low.**

MEDIA & PROMO (usually NOT kid-friendly unless there’s a true kid-relevant twist):
- Releases, re-releases, chart milestones
- Magazine covers, talk-show appearances, interviews
- TV pilots/premieres/finales
- Advertising campaigns, endorsements, product launches

POLITICS & PUBLICITY (usually NOT kid-friendly):
- Speeches, campaign announcements, election wins, becoming a leader
- Memoirs/autobiographies/adult-focused books
- Honorary degrees, commencement speeches, lifetime awards
- Appointments to boards/committees/institutions
- Launching a foundation/organization (unless it instantly did something kids would find amazing)

BIRTHDAYS:
- Birthdays are OK to include ONLY if the person is clearly relevant to kids today (e.g., still widely known/famous),
  or is a super-interesting inventor/creator whose work kids still recognize. Otherwise score low.

Kids today love:
- Animals, records, space, inventions, surprising/funny twists
- Sports, music, pop culture, and “whoa I didn’t know that!” moments

Return a single JSON array. For each fact include:
- id
- original (same text you were given)
- score (1–100) — OMIT this field entirely if the fact was rejected due to being release/appearance/award-only
- is_kid_friendly (true or false)
- categories (an array of EXACTLY 3 objects, each: { "category": <name>, "score": <0.0–1.0> })

EXAMPLES (compact):
[
  { "id": 1, "original": "Neil Armstrong walks on the Moon.", "score": 98, "is_kid_friendly": true,
    "categories": [
      { "category": "Beyond Earth", "score": 1.0 },
      { "category": "Big Brain Energy", "score": 0.8 },
      { "category": "World Shakers & Icon Makers", "score": 0.6 }
    ]
  },
  { "id": 2, "original": "World’s oldest cat turns 38.", "score": 100, "is_kid_friendly": true,
    "categories": [
      { "category": "Creature Feature", "score": 1.0 },
      { "category": "The What Zone", "score": 0.6 },
      { "category": "Big Brain Energy", "score": 0.4 }
    ]
  },
  { "id": 3, "original": "A TV show debuts on a major network.", "score": 12, "is_kid_friendly": false,
    "categories": [
      { "category": "Vibes, Beats & Brushes", "score": 0.3 },
      { "category": "World Shakers & Icon Makers", "score": 0.2 },
      { "category": "The What Zone", "score": 0.1 }
    ]
  }
]
"""


def extract_json_from_markdown(text):
    m = re.search(r"```json\s*(\[\s*{.*?}\s*\])\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

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
                continue
            else:
                if ch == '"':
                    in_str = True
                    continue
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i+1]
                        return candidate.strip()
        start = text.find("[", start + 1)

    m = re.search(r"(\[\s*{.*?}\s*\])", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()

def log_retry_error(error_message, batch, attempt):
    with open("retry_log.txt", "a", encoding="utf-8") as log_file:
        timestamp = datetime.datetime.now().isoformat()
        ids = ", ".join(str(f["id"]) for f in batch)
        log_file.write(f"[{timestamp}] Attempt {attempt + 1} failed for IDs: {ids}\nError: {error_message}\n\n")

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

def normalize_categories(cat_list):
    if not isinstance(cat_list, list):
        return []
    cleaned = []
    for item in cat_list:
        if isinstance(item, dict) and "category" in item and "score" in item:
            try:
                s = float(item["score"])
            except (TypeError, ValueError):
                s = 0.0
            s = max(0.0, min(1.0, s))
            cleaned.append({"category": str(item["category"]), "score": s})
    cleaned.sort(key=lambda x: x["score"], reverse=True)
    return cleaned[:3]

def enhance_facts(facts):
    """
    facts: list of one fact (BATCH_SIZE=1) but works for any len.
    Retries indefinitely for retryable errors; bails for permanent ones.
    """
    attempt = 0
    while True:
        try:
            facts_block = "\n".join([f'{fact["id"]}: {fact["fact"]}' for fact in facts])
            full_prompt = (
                PROMPT_HEADER
                + f"""

            NOW RATE ONLY THE FOLLOWING {len(facts)} FACTS. Do NOT make up your own. Stick exactly to this list:

            {facts_block}

            Respond with ONLY a single valid JSON array. No code fences, no extra text, no trailing notes.
            The array must include one object per input fact."""
            )

            # small global gate to avoid “retry waves” across threads
            if attempt > 0:
                with _retry_gate_lock:
                    global _next_retry_earliest
                    now = time.time()
                    delay = max(0.0, _next_retry_earliest - now)
                    if delay > 0:
                        time.sleep(delay)
                    # schedule the next slot 40–80 ms later
                    _next_retry_earliest = max(now, _next_retry_earliest) + random.uniform(0.04, 0.08)

            response = anthropic.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4000,
                temperature=0.2,
                system="You are a strict JSON generator. You must output ONLY a single valid JSON array and nothing else. No code fences, no commentary.",
                messages=[{"role": "user", "content": full_prompt}]
            )

            raw_output_parts = []
            for block in getattr(response, "content", []) or []:
                txt = getattr(block, "text", None) if not isinstance(block, dict) else block.get("text")
                if txt:
                    raw_output_parts.append(txt)
            raw_output = html.unescape("\n".join(raw_output_parts)).strip()
            if not raw_output:
                raise RuntimeError("Empty response from Claude.")

            json_text = extract_json_from_markdown(raw_output)
            if PRINT_MODEL_JSON:
                print("\n================== RAW MODEL JSON ==================")
                print(json_text)
                print("====================================================\n")

            enhanced, success = safe_parse_json(json_text)
            if not success or not isinstance(enhanced, list):
                print("📨 Prompt that caused the failure:\n" + full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else ""))
                # Parsing issues usually are model/transient – treat as retryable
                raise RuntimeError("Parse failure")

            if PRINT_PARSED_JSON:
                print("\n--------------- PARSED PYTHON LIST ----------------")
                print(json.dumps(enhanced, indent=2, ensure_ascii=False))
                print("---------------------------------------------------\n")

            matched = []
            for i, result in enumerate(enhanced):
                if ("is_kid_friendly" in result) or ("score" in result) or ("categories" in result):
                    enriched = {
                        "id": facts[i]["id"],
                        "year": facts[i]["year"],
                        "original": facts[i]["original"],
                        **({"score": result["score"]} if "score" in result else {}),
                        "is_kid_friendly": result.get("is_kid_friendly"),
                        "categories": normalize_categories(result.get("categories", [])),
                    }
                    matched.append(enriched)
                    if PRINT_ENRICHED:
                        print(json.dumps(enriched, indent=2, ensure_ascii=False))

            return matched

        except Exception as e:
            # Decide if we should retry forever or bail
            if is_retryable_error(e):
                print(f"❌ Retryable error (attempt {attempt + 1}): {e}")
                log_retry_error(str(e), facts, attempt)
                retry_backoff_sleep(attempt)
                attempt += 1
                continue
            else:
                # Non-retryable — log and return empty; prevents true infinite loop on permanent errors
                print(f"❌ Non-retryable error, giving up for this fact: {e}")
                log_retry_error(str(e), facts, attempt)
                return []
            
# --- replace your process_file with this safer version ---
def process_file(input_path):
    filename = os.path.basename(input_path)  # e.g., "123_May_2.json"
    base, _ = os.path.splitext(filename)
    output_path = os.path.join(SCORED_DIR, f"{base}_scored.json")

    if is_already_done(input_path):
        print(f"⏭️  Skipping (already scored): {output_path}")
        return
    else:
        print(f"🛠️  Processing -> {output_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("Facts", [])
    if not events:
        print("No 'Facts' found in JSON.")
        return

    input_facts = [
        {
            "id": i + 1,
            "fact": fact["text"],
            "year": fact["year"],
            "original": fact["text"]
        }
        for i, fact in enumerate(events)
    ]

    enhanced = []

    # one “batch” per fact (since BATCH_SIZE=1), but submit many at once
    index_batches = [(i, [input_facts[i]]) for i in range(0, len(input_facts), BATCH_SIZE)]
    results_map = {}

    # Optional: simple progress counter instead of tqdm (tqdm + threads gets messy)
    total = len(index_batches)
    done = 0

    workers = min(MAX_CONCURRENCY, len(index_batches)) or 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        future_map = {ex.submit(enhance_facts, batch): idx for idx, batch in index_batches}
        for fut in as_completed(future_map):
            idx = future_map[fut]
            try:
                res = fut.result() or []
            except Exception as e:
                print(f"❌ Batch at index {idx} failed: {e}")
                res = []
            results_map[idx] = res
            done += 1
            if done % 10 == 0 or done == total:
                print(f"✅ Progress: {done}/{total} single-fact requests finished")

    # Reassemble results in input order
    for idx, _ in index_batches:
        enhanced.extend(results_map.get(idx, []))


    if not enhanced:
        print(f"⚠️  No results produced. Not writing {output_path} so it can be retried later.")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved rated facts to: {output_path}")
    sys.stdout.write('\a')  # Beep

    # Score summary
    score_90_100 = sum(1 for e in enhanced if "score" in e and 90 <= e["score"] <= 100)
    score_70_89  = sum(1 for e in enhanced if "score" in e and 70 <= e["score"] <= 89)
    score_40_69  = sum(1 for e in enhanced if "score" in e and 40 <= e["score"] <= 69)
    score_1_39   = sum(1 for e in enhanced if "score" in e and 1 <= e["score"] <= 39)

    print("\n📊 Score Summary:")
    print(f"🎉 90–100: {score_90_100}")
    print(f"✅ 70–89: {score_70_89}")
    print(f"🤔 40–69: {score_40_69}")
    print(f"🚫 1–39:  {score_1_39}")

    # Kid-friendliness summary
    kid_friendly_count = sum(1 for e in enhanced if e.get("is_kid_friendly") is True)
    not_kid_friendly_count = sum(1 for e in enhanced if e.get("is_kid_friendly") is False)

    print("\n🧒 Kid-Friendliness Summary:")
    print(f"👍 Kid-Friendly (true): {kid_friendly_count}")
    print(f"👎 Not Kid-Friendly (false): {not_kid_friendly_count}")


if __name__ == "__main__":
    files = list_json_files(FACTS_DIR)

    to_process = []
    for fname in files:
        # Only consider .json files in FACTS_DIR
        full_path = os.path.join(FACTS_DIR, fname)
        if not fname.lower().endswith(".json"):
            continue
        if is_already_done(full_path):
            print(f"⏭️  Already done: {fname}")
        else:
            to_process.append(full_path)

    if not to_process:
        print("✅ Nothing to do — all files already have *_scored.json outputs.")
        sys.exit(0)

    print(f"\n📦 Will process {len(to_process)} file(s).")
    for path in to_process:
        print(f"\n📂 Processing file: {os.path.basename(path)}")
        process_file(path)
