# 7_factChecker_simple.py
import os
import json
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import sys
from typing import Any, Dict, List, Tuple

# ---------------------- CONFIG ----------------------
BASE_DIR = Path(r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber")
FINAL_DIR = BASE_DIR / "6_final"
CHECKED_DIR = BASE_DIR / "7_checked"
CHECKED_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_MODEL = "claude-3-5-sonnet-20240620"   # change to "claude-3-5-sonnet-latest" if needed
API_KEY = os.getenv("ANTHROPIC_API_KEY")

MAX_RETRIES = 2
TEMPERATURE = 0.1
TIMEOUT_SLEEP = 2.0

ALLOWED_FIELDS = {"title","story","activity_question","activity_choices","activity_answer"}

# ---------------------- FILE / DATE HELPERS ----------------------
def doy_to_date(doy: int) -> Tuple[str, int, str]:
    """
    Build a long date from DOY in leap-year 2024 to match your filenames.
    """
    base = datetime(2024, 1, 1) + relativedelta(days=doy - 1)
    month_name = base.strftime("%B")
    day = int(base.strftime("%-d")) if os.name != "nt" else int(base.strftime("%#d"))
    iso = base.strftime("%Y-%m-%d")
    return month_name, day, iso

def find_final_file(doy: int, month_name: str, day: int) -> Path:
    """
    Looks for `DOY_Month_Day_Final.json` first, or any file starting with `DOY_`.
    """
    expected = FINAL_DIR / f"{doy}_{month_name}_{day}_Final.json"
    if expected.exists():
        return expected
    for c in FINAL_DIR.glob(f"{doy}_*_*_Final.json"):
        return c
    raise FileNotFoundError(f"Could not find file for DOY {doy}: expected {expected}")

def load_json(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def divider():
    print("-" * 78)

# ---------------------- LLM CORE ----------------------
def extract_first_json_obj(text: str) -> Dict[str, Any]:
    """
    Pull the first top-level JSON object from a model response.
    Handles ```json ... ``` fences and small prefaces. Lightweight & robust.
    """
    t = (text or "").strip()
    if t.startswith("```"):
        # strip codefences
        if t.lower().startswith("```json"):
            t = t[7:]
        else:
            t = t[3:]
        if t.endswith("```"):
            t = t[:-3]
        t = t.strip()

    start = t.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model output.")
    depth = 0
    for i in range(start, len(t)):
        c = t[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i+1])
    raise ValueError("No complete JSON object found in model output.")

def call_llm(system: str, user: str) -> str:
    from anthropic import Anthropic
    if not API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    client = Anthropic(api_key=API_KEY, timeout=40)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=900,
                temperature=TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join([blk.text for blk in resp.content if getattr(blk, "type", "") == "text"]).strip()
            if not text:
                raise RuntimeError("Empty LLM response.")
            return text
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(TIMEOUT_SLEEP)
    # give up
    raise last_err

# ---------------------- PASS 1: VERIFY + SUGGEST ----------------------
SYSTEM_PASS1 = """You are a meticulous children's non-fiction line editor (ages 8–12) for an on-this-day factbook.

Your job for EACH SINGLE RECORD:
1) Verify the entry truly belongs on THE GIVEN DATE (from filename), and that it describes the correct event for that date (avoid "close but wrong" mix-ups).
2) If anything feels off (wrong date, wrong event for that date, attribution uncertain, or the activity asks about the date), provide concise, surgical SUGGESTIONS (micro-edits) to fix/soften.
3) Keep suggestions short and surgical: swaps/tightening/soften claims. No expansions.

Hard constraints:
- 1–4 bullets total, ≤120 words for the entire suggestion.
- If the entry is fine as-is, set needs_change=false and an empty suggestion.
- If suggesting a new activity, it must be a single factual question about the story (not the date) with EXACTLY 4 choices (1 correct, 2 plausible wrong, 1 silly wrong) and include the correct answer inline.

Return JSON ONLY:
{
  "needs_change": true/false,
  "suggestion": "<bullet list or empty>",
  "notes": "<very short reason if needs_change=true>"
}
"""

USER_PASS1_TEMPLATE = """File name: {file_name}
Date context: {long_date} (ISO {iso_date})

Original record (single item):
{record_json}

Return ONLY this JSON:
{{
  "needs_change": true/false,
  "suggestion": "- On-this-day alignment: …\\n- (Optional) Title: …\\n- (Optional) Lead: …\\n- (Optional) Activity: …",
  "notes": "<why it needs change in one short sentence>"
}}
Rules:
- 1–4 bullets, ≤120 words.
- Focus on whether the event truly belongs on {long_date} and is the correct one for that date.
"""

def pass1_verify_and_suggest(record: Dict[str,Any], long_date: str, iso_date: str, file_name: str) -> Tuple[bool, str, str]:
    user = USER_PASS1_TEMPLATE.format(
        file_name=file_name,
        long_date=long_date,
        iso_date=iso_date,
        record_json=json.dumps(record, ensure_ascii=False, indent=2)
    )
    raw = call_llm(SYSTEM_PASS1, user)
    data = extract_first_json_obj(raw)
    needs_change = bool(data.get("needs_change"))
    suggestion = str(data.get("suggestion") or "").strip()
    notes = str(data.get("notes") or "").strip()
    # normalize "looks good" cases
    if not needs_change or suggestion.lower().startswith("looks good"):
        return False, "", ""
    return needs_change, suggestion, notes

# ---------------------- PASS 2: APPLY ----------------------
SYSTEM_PASS2 = "You apply micro-edits precisely and minimally."

APPLY_PROMPT = """You are editing a single fact entry for a children's 8–12 on-this-day book.

TASK: Apply the following suggestion bullets as MINIMAL textual edits to the original record. Keep meaning intact and length similar.

Rules:
- Edit ONLY these fields if needed: title, story, activity_question, activity_choices, activity_answer.
- Do NOT change the id or structure.
- Keep title within ±3 words of the original; keep story within ±5% words.
- The activity must NOT ask for the date; it must be answerable from the story.
- If you replace the activity, provide EXACTLY 4 choices: 1 correct, 2 plausible wrong, 1 silly wrong, and set activity_answer to the correct one.
- If an item doesn’t need change, leave it as-is.

Date context: {long_date} (ISO {iso_date})
Suggestion bullets:
{suggestion}

Original record:
{record_json}

Return ONLY this JSON:
{{
  "applied_edits": {{
    // include ONLY the fields that change; or {{}}
  }}
}}
"""

def pass2_apply_edits(record: Dict[str,Any], suggestion: str, long_date: str, iso_date: str) -> Dict[str,Any]:
    user = APPLY_PROMPT.format(
        long_date=long_date,
        iso_date=iso_date,
        suggestion=suggestion,
        record_json=json.dumps(record, ensure_ascii=False, indent=2)
    )
    raw = call_llm(SYSTEM_PASS2, user)
    data = extract_first_json_obj(raw)
    edits = data.get("applied_edits") or {}
    if not isinstance(edits, dict):
        return {}
    # Keep only allowed fields
    return {k:v for k,v in edits.items() if k in ALLOWED_FIELDS}

# ---------------------- REPORT ----------------------
def show_before_after(rec: Dict[str, Any], edits: Dict[str, Any]) -> None:
    for f in ALLOWED_FIELDS:
        if f in edits:
            print(f"\n{f}:")
            print("  BEFORE:")
            before_val = rec.get(f, "")
            if isinstance(before_val, list):
                for i, v in enumerate(before_val, 1):
                    print(f"    {i}. {v}")
            else:
                print(f"    {before_val}")
            print("  AFTER:")
            after_val = edits[f]
            if isinstance(after_val, list):
                for i, v in enumerate(after_val, 1):
                    print(f"    {i}. {v}")
            else:
                print(f"    {after_val}")

# ---------------------- MAIN ----------------------
def main():
    if not API_KEY:
        print("❌ ANTHROPIC_API_KEY environment variable is not set.")
        sys.exit(1)

    try:
        raw = input("Enter day-of-year (leap year; e.g., 251 for Sep 7): ").strip()
        doy = int(raw)
        if not (1 <= doy <= 366):
            raise ValueError("DOY must be 1..366")
    except Exception as e:
        print(f"❌ Invalid input: {e}")
        sys.exit(1)

    month_name, day, iso = doy_to_date(doy)
    long_date = f"{month_name} {day}"

    try:
        src = find_final_file(doy, month_name, day)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"📂 Loaded file: {src.name}  (Date: {long_date}, {iso})")
    data = load_json(src)
    if not isinstance(data, list):
        print("❌ File must contain a list of facts (list).")
        sys.exit(1)

    # PASS 1 — verify + suggest
    print("🔎 Pass 1: verifying date & event correctness via LLM…")
    divider()
    flagged_indexes: List[int] = []
    for idx, rec in enumerate(data):
        rec_id = rec.get("id", f"row{idx+1}")
        title = (rec.get("title") or "").strip() or "(untitled)"
        try:
            needs_change, suggestion, notes = pass1_verify_and_suggest(rec, long_date, iso, src.name)
            if needs_change:
                data[idx]["suggestion"] = suggestion
                flagged_indexes.append(idx)
                print(f"🛠 Needs improvement  id={rec_id} | {title}")
                if notes:
                    print(f"   ↳ {notes}")
            else:
                print(f"✅ OK  id={rec_id} | {title}")
        except Exception as e:
            # If Pass 1 fails for this record, keep it unchanged
            print(f"[WARN] id={rec_id}: verification failed ({type(e).__name__}: {e}). Skipping.")
    divider()
    print(f"📋 Items needing improvement: {len(flagged_indexes)} of {len(data)}")

    # PASS 2 — apply suggestions
    print("\n🛠 Pass 2: applying micro-edits via LLM…")
    applied_count = 0
    for idx in flagged_indexes:
        rec = data[idx]
        rec_id = rec.get("id", f"row{idx+1}")
        title = (rec.get("title") or "").strip() or "(untitled)"
        suggestion = rec.get("suggestion","").strip()
        if not suggestion:
            continue
        try:
            edits = pass2_apply_edits(rec, suggestion, long_date, iso)
            if edits:
                print("\n" + "─" * 78)
                print(f"ID: {rec_id} | {title}")
                show_before_after(rec, edits)
                for k, v in edits.items():
                    rec[k] = v
                applied_count += 1
                print("✅ Applied.")
            else:
                print(f"ℹ️ id={rec_id}: model proposed no concrete edits (kept suggestion only).")
        except Exception as e:
            print(f"⚠️  id={rec_id}: apply failed ({type(e).__name__}: {e}). Suggestion kept; text unchanged.")

    print(f"\n✅ Applied edits to {applied_count} item(s).")

    # Save output
    out_path = CHECKED_DIR / src.name.replace("_Final.json", "_Checked.json")
    save_json(out_path, data)
    print(f"📦 Wrote checked JSON: {out_path}")

if __name__ == "__main__":
    main()
