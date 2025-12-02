import json
from pathlib import Path
from datetime import datetime
import re

NUMERIC_PREFIX_RE = re.compile(r"^\s*(\d+)_([A-Za-z]+)_(\d{1,2})_.*enhanced.*\.json$", re.IGNORECASE)

def list_enhanced_by_prefix(enhanced_dir: Path):
    items = []
    for f in enhanced_dir.iterdir():
        if not f.is_file():
            continue
        m = NUMERIC_PREFIX_RE.match(f.name)
        if m:
            items.append((int(m.group(1)), m.group(2), int(m.group(3)), f.name))
    items.sort(key=lambda t: (t[0], t[3].lower()))
    if not items:
        print("No numeric *_enhanced*.json files found in 4_enhanced.")
        return []
    print("Valid enhanced files (choose by the NUMBER at start of filename):")
    seen = set()
    for day_num, month, day, fname in items:
        if day_num in seen:
            continue
        seen.add(day_num)
        print(f"{day_num}: {fname}")
    return items

def choose_file_by_daynum(items):
    by_num = {}
    for day_num, month, day, fname in items:
        by_num.setdefault(day_num, (month, day, fname))
    while True:
        raw = input("\nEnter the day number (e.g., 251): ").strip()
        if not raw.isdigit():
            print("Please enter a numeric day number (e.g., 251).")
            continue
        n = int(raw)
        if n in by_num:
            return n, *by_num[n]
        print(f"No file starting with '{n}_' was found. Try again.")


LEAP_YEAR = 2024  # always treat as leap year for DOY

BASE_DIR = Path(r"C:/Personal/factBook/facts/new fact grabber")
ENHANCED_DIR = BASE_DIR / "4_enhanced"
HOLIDAYS_DIR = BASE_DIR / "c_enhanced"
OUTPUT_DIR = BASE_DIR / "6_final"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {path}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error in {path}: {e}")
        return []

def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def month_name_to_number(month_name: str) -> int:
    try:
        return datetime.strptime(month_name.strip(), "%B").month
    except ValueError:
        return datetime.strptime(month_name.strip(), "%b").month

def dedupe_preserve_order(items):
    """First occurrence wins (keeps holidays on top if listed first)."""
    seen = set()
    out = []
    for it in items:
        key = str(it.get("id"))
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out

def main():
    # Pick by numeric prefix from 4_enhanced
    items = list_enhanced_by_prefix(ENHANCED_DIR)
    if not items:
        return

    doy, month_input, day, _fname = choose_file_by_daynum(items)

    # Double-check DOY against computed calendar value
    try:
        month_num = month_name_to_number(month_input)
        date_obj = datetime(LEAP_YEAR, month_num, day)
        doy_check = date_obj.timetuple().tm_yday
        if doy_check != doy:
            print(f"⚠️ Filename DOY {doy} vs computed DOY {doy_check}. Using computed.")
            doy = doy_check
    except ValueError as e:
        print(f"❌ Date error: {e}")
        return

    # Output file name
    output_name = f"{doy}_{month_input}_{day}_Final.json"
    output_path = OUTPUT_DIR / output_name

    # Gather inputs from 4_enhanced
    enhanced_pattern = f"*{month_input}_{day}*enhanced*.json"
    enhanced_matches = sorted(ENHANCED_DIR.glob(enhanced_pattern))

    print("\n📂 Looking for input files")
    print("  • From 4_enhanced:", ENHANCED_DIR)
    print("  • Pattern:", enhanced_pattern)
    if not enhanced_matches:
        print("  ⚠️ No matching files found in 4_enhanced.")
    else:
        for p in enhanced_matches:
            print(f"    - {p.name}")

    # Holidays file from c_enhanced with DOY prefix
    holidays_name = f"{doy}_{month_input}_{day}_Holidays_scored_enhanced.json"
    holidays_path = HOLIDAYS_DIR / holidays_name
    if holidays_path.exists():
        print("  • Holidays file found in c_enhanced:")
        print(f"    - {holidays_path.name}")
        holidays_items = load_json(holidays_path)
    else:
        print("  ⚠️ Holidays file not found in c_enhanced:", holidays_name)
        holidays_items = []

    # Load enhanced items
    enhanced_items = []
    for p in enhanced_matches:
        enhanced_items.extend(load_json(p))

    # ✅ Holidays first, then enhanced; de-dup keeps FIRST occurrence
    combined_ordered = holidays_items + enhanced_items
    deduped = dedupe_preserve_order(combined_ordered)

    print(f"\n✅ Combined {len(enhanced_matches)} enhanced file(s)"
          f"{' + holidays' if holidays_items else ''}"
          f" → {len(combined_ordered)} items before de-dup → {len(deduped)} items after de-dup")
    if holidays_items:
        print(f"📌 Holidays pinned at top: {min(len(holidays_items), len(deduped))} item(s)")

    save_json(output_path, deduped)
    print(f"💾 Saved to: {output_path}")
    print(f"📅 Day-of-year (leap): {doy}")

if __name__ == "__main__":
    main()
