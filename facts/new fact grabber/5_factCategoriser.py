import json
from collections import Counter
import os

# Config
INPUT_FILE = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\4_enhanced\March_29_culled_enhanced.json"
OUTPUT_FILE = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\5_catagorised\March_29_culled_enhanced_catagorised.json"
CATEGORY_CAP = 20
MIN_CATEGORY_SIZE = 6
FALLBACK_CATEGORY = "The What Zone"

def reassign_facts(facts, assignments, counts, from_cats, to_cat, min_required, reassigned_log):
    needed = min_required - counts[to_cat]
    candidates = []

    for fact in facts:
        fact_id = fact["id"]
        current_cat = assignments.get(fact_id)
        if not current_cat or current_cat == to_cat or current_cat not in from_cats:
            continue
        if counts[current_cat] <= MIN_CATEGORY_SIZE or (to_cat != FALLBACK_CATEGORY and counts[to_cat] >= CATEGORY_CAP):
            continue


        for c in fact["categories"]:
            if c["category"] == to_cat:
                candidates.append((fact_id, current_cat, to_cat, c["score"]))
                break

    candidates.sort(key=lambda x: next(
        (c["score"] for f in facts if f["id"] == x[0]
         for c in f["categories"] if c["category"] == x[1]), 0.0))

    for fact_id, from_cat, to_cat, to_score in candidates[:needed]:
        assignments[fact_id] = to_cat
        counts[from_cat] -= 1
        counts[to_cat] += 1
        reassigned_log.append({
            "id": fact_id,
            "original_category": from_cat,
            "original_score": next(c["score"] for f in facts if f["id"] == fact_id
                                   for c in f["categories"] if c["category"] == from_cat),
            "new_category": to_cat,
            "new_score": to_score
        })

# --- Main script ---
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    facts = json.load(f)

assignments = {}
category_counter = Counter()
reassigned_facts = []

# First pass: assign top categories within caps
for fact in facts:
    categories = sorted(fact.get("categories", []), key=lambda c: c["score"], reverse=True)
    if not categories:
        continue
    top_cat = categories[0]
    for cat in categories:
        if cat["category"] == FALLBACK_CATEGORY or (cat["category"] != FALLBACK_CATEGORY and category_counter[cat["category"]] < CATEGORY_CAP):
            assignments[fact["id"]] = cat["category"]
            category_counter[cat["category"]] += 1
            if cat["category"] != top_cat["category"]:
                reassigned_facts.append({
                    "id": fact["id"],
                    "original_category": top_cat["category"],
                    "original_score": top_cat["score"],
                    "new_category": cat["category"],
                    "new_score": cat["score"]
                })
            break
    else:
        # If no valid category under cap found, assign to fallback
        assignments[fact["id"]] = FALLBACK_CATEGORY
        category_counter[FALLBACK_CATEGORY] += 1
        reassigned_facts.append({
            "id": fact["id"],
            "original_category": top_cat["category"],
            "original_score": top_cat["score"],
            "new_category": FALLBACK_CATEGORY,
            "new_score": 0.0
        })


# Pass 2: raise all categories to min size if possible
all_categories = set(c["category"] for f in facts for c in f.get("categories", []))
target_categories = [c for c in all_categories if c != FALLBACK_CATEGORY]

while True:
    underfilled = [cat for cat in target_categories if category_counter[cat] < MIN_CATEGORY_SIZE]
    if not underfilled:
        break
    prev = sum(category_counter[cat] for cat in underfilled)
    for cat in underfilled:
        reassign_facts(facts, assignments, category_counter, from_cats=target_categories, to_cat=cat,
                       min_required=MIN_CATEGORY_SIZE, reassigned_log=reassigned_facts)
    if sum(category_counter[cat] for cat in underfilled) == prev:
        break

# Final redistribution: force facts in sub-6 categories to move
final_counts = Counter(assignments.values())
final_underfilled = [cat for cat in final_counts if final_counts[cat] < MIN_CATEGORY_SIZE and cat != FALLBACK_CATEGORY]

for fact in facts:
    current_cat = assignments.get(fact["id"])
    if current_cat in final_underfilled:
        sorted_cats = sorted(fact.get("categories", []), key=lambda c: c["score"], reverse=True)
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
                    "original_score": next((sc["score"] for sc in fact["categories"] if sc["category"] == current_cat), 0.0),
                    "new_category": new_cat,
                    "new_score": c["score"]
                })
                reassigned = True
                break
        # Force fallback if still not reassigned
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

# Apply final assignments to fact data
for fact in facts:
    assigned_cat = assignments.get(fact["id"])
    fact["categories"] = [assigned_cat] if assigned_cat else []

# Write output
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(facts, f, indent=2, ensure_ascii=False)

# Final summary output
print("\n📊 Final Category Counts (sorted):\n")
final_counts = Counter(assignments.values())

for category, count in final_counts.most_common():
    flag = ""
    if category != FALLBACK_CATEGORY and count > CATEGORY_CAP:
        flag = f" ⚠️ EXCEEDED CAP ({count} > {CATEGORY_CAP})"
    print(f"{category}: {count}{flag}")

print(f"\n🔁 Total Reassignments: {len(reassigned_facts)}")
print(f"\n✅ Categorised file written to:\n{OUTPUT_FILE}")

