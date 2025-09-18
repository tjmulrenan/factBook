import json
from collections import Counter
import os
import re

# === CONFIG: folders only (file is chosen interactively) ===
INPUT_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\4_enhanced"
OUTPUT_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\5_catagorised"

CATEGORY_CAP = 20
MIN_CATEGORY_SIZE = 6
FALLBACK_CATEGORY = "The What Zone"

FILENAME_RE = re.compile(r'^(?P<month>[A-Za-z]+)_(?P<day>\d{1,2})_culled_enhanced\.json$', re.IGNORECASE)

def pick_input_file():
    files = []
    for fname in os.listdir(INPUT_DIR):
        if not fname.lower().endswith(".json"):
            continue
        m = FILENAME_RE.match(fname)
        if m:
            month = m.group("month")
            day = int(m.group("day"))
            files.append((month, day, fname))

    if not files:
        raise SystemExit(f"❌ No files like '*_culled_enhanced.json' found in:\n{INPUT_DIR}")

    # Sort by month name then day (alphabetical month is fine; adjust if you prefer calendar order)
    files.sort(key=lambda x: (x[0].lower(), x[1]))

    print("\n📂 Pick a file to categorise:\n")
    for i, (month, day, fname) in enumerate(files, start=1):
        print(f"{i:>3}. {month}_{day}  —  {fname}")

    while True:
        choice = input("\nType the number of the file to process: ").strip()
        if not choice.isdigit():
            print("Please enter a number from the list.")
            continue
        idx = int(choice)
        if not (1 <= idx <= len(files)):
            print(f"Please choose a number between 1 and {len(files)}.")
            continue
        month, day, fname = files[idx - 1]
        input_path = os.path.join(INPUT_DIR, fname)
        output_name = f"{month}_{day}_culled_enhanced_catagorised.json"
        output_path = os.path.join(OUTPUT_DIR, output_name)
        return input_path, output_path, f"{month}_{day}"

def reassign_facts(facts, assignments, counts, from_cats, to_cat, min_required, reassigned_log):
    needed = min_required - counts[to_cat]
    if needed <= 0:
        return

    candidates = []
    for fact in facts:
        fact_id = fact["id"]
        current_cat = assignments.get(fact_id)
        if not current_cat or current_cat == to_cat or current_cat not in from_cats:
            continue
        if counts[current_cat] <= MIN_CATEGORY_SIZE or (to_cat != FALLBACK_CATEGORY and counts[to_cat] >= CATEGORY_CAP):
            continue

        for c in fact.get("categories", []):
            if c["category"] == to_cat:
                candidates.append((fact_id, current_cat, to_cat, c["score"]))
                break

    # Prefer moving facts that are weakest for their CURRENT category
    def current_score(fid, curr_cat):
        for f in facts:
            if f["id"] == fid:
                for c in f.get("categories", []):
                    if c["category"] == curr_cat:
                        return c.get("score", 0.0)
        return 0.0

    candidates.sort(key=lambda x: current_score(x[0], x[1]))

    for fact_id, from_cat, to_cat, to_score in candidates[:needed]:
        assignments[fact_id] = to_cat
        counts[from_cat] -= 1
        counts[to_cat] += 1
        reassigned_log.append({
            "id": fact_id,
            "original_category": from_cat,
            "original_score": current_score(fact_id, from_cat),
            "new_category": to_cat,
            "new_score": to_score
        })

def main():
    INPUT_FILE, OUTPUT_FILE, label = pick_input_file()
    print(f"\n➡️  Processing: {label}")
    print(f"   Input : {INPUT_FILE}")
    print(f"   Output: {OUTPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        facts = json.load(f)

    assignments = {}
    category_counter = Counter()
    reassigned_facts = []

    # Pass 1: assign best available category under caps (avoid fallback unless necessary)
    for fact in facts:
        categories = sorted(fact.get("categories", []), key=lambda c: c.get("score", 0.0), reverse=True)
        if not categories:
            continue
        top_cat = categories[0]
        picked = False
        for cat in categories:
            cname = cat["category"]
            # Prefer non-fallback categories under cap; allow fallback only if none fit
            if cname != FALLBACK_CATEGORY and category_counter[cname] < CATEGORY_CAP:
                assignments[fact["id"]] = cname
                category_counter[cname] += 1
                if cname != top_cat["category"]:
                    reassigned_facts.append({
                        "id": fact["id"],
                        "original_category": top_cat["category"],
                        "original_score": top_cat.get("score", 0.0),
                        "new_category": cname,
                        "new_score": cat.get("score", 0.0)
                    })
                picked = True
                break

        if not picked:
            # If we couldn't place in a non-fallback under cap, try fallback (or top_cat if it's still under cap)
            fallback_pick = None
            for cat in categories:
                cname = cat["category"]
                if cname == FALLBACK_CATEGORY:
                    fallback_pick = cat
                    break

            chosen = fallback_pick or top_cat
            assignments[fact["id"]] = chosen["category"]
            category_counter[chosen["category"]] += 1
            if chosen["category"] != top_cat["category"]:
                reassigned_facts.append({
                    "id": fact["id"],
                    "original_category": top_cat["category"],
                    "original_score": top_cat.get("score", 0.0),
                    "new_category": chosen["category"],
                    "new_score": chosen.get("score", 0.0)
                })

    # Pass 2: try to raise all non-fallback categories to MIN_CATEGORY_SIZE
    all_categories = set(c["category"] for f in facts for c in f.get("categories", []))
    target_categories = [c for c in all_categories if c != FALLBACK_CATEGORY]

    while True:
        underfilled = [cat for cat in target_categories if category_counter[cat] < MIN_CATEGORY_SIZE]
        if not underfilled:
            break
        before = sum(category_counter[c] for c in underfilled)
        for cat in underfilled:
            reassign_facts(
                facts=facts,
                assignments=assignments,
                counts=category_counter,
                from_cats=target_categories,
                to_cat=cat,
                min_required=MIN_CATEGORY_SIZE,
                reassigned_log=reassigned_facts
            )
        after = sum(category_counter[c] for c in underfilled)
        if after == before:
            # No progress; stop trying
            break

    # Pass 3: force-move any facts still in sub-6 categories (except fallback)
    final_counts = Counter(assignments.values())
    final_underfilled = [cat for cat in final_counts if final_counts[cat] < MIN_CATEGORY_SIZE and cat != FALLBACK_CATEGORY]

    for fact in facts:
        current_cat = assignments.get(fact["id"])
        if current_cat in final_underfilled:
            sorted_cats = sorted(fact.get("categories", []), key=lambda c: c.get("score", 0.0), reverse=True)
            reassigned = False
            for c in sorted_cats:
                new_cat = c["category"]
                if new_cat != FALLBACK_CATEGORY and final_counts[new_cat] >= CATEGORY_CAP:
                    continue
                if new_cat != current_cat and (new_cat == FALLBACK_CATEGORY or final_counts[new_cat] < CATEGORY_CAP):
                    assignments[fact["id"]] = new_cat
                    final_counts[current_cat] -= 1
                    final_counts[new_cat] += 1
                    reassigned_facts.append({
                        "id": fact["id"],
                        "original_category": current_cat,
                        "original_score": next((sc.get("score", 0.0) for sc in fact.get("categories", []) if sc["category"] == current_cat), 0.0),
                        "new_category": new_cat,
                        "new_score": c.get("score", 0.0)
                    })
                    reassigned = True
                    break
            if not reassigned and current_cat != FALLBACK_CATEGORY:
                assignments[fact["id"]] = FALLBACK_CATEGORY
                final_counts[current_cat] -= 1
                final_counts[FALLBACK_CATEGORY] += 1
                reassigned_facts.append({
                    "id": fact["id"],
                    "original_category": current_cat,
                    "original_score": 0.0,
                    "new_category": FALLBACK_CATEGORY,
                    "new_score": 0.0
                })

    # Apply final assignments: replace categories array with a single chosen category
    for fact in facts:
        assigned_cat = assignments.get(fact["id"])
        fact["categories"] = [assigned_cat] if assigned_cat else []

    # Write output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)

    # Final summary
    print("\n📊 Final Category Counts (sorted):\n")
    final_counts = Counter(assignments.values())
    for category, count in final_counts.most_common():
        flag = ""
        if category != FALLBACK_CATEGORY and count > CATEGORY_CAP:
            flag = f" ⚠️ EXCEEDED CAP ({count} > {CATEGORY_CAP})"
        print(f"{category}: {count}{flag}")

    print(f"\n🔁 Total Reassignments: {len(reassigned_facts)}")
    print(f"\n✅ Categorised file written to:\n{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
