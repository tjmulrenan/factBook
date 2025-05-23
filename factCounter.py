import json
import os
from collections import defaultdict, Counter

# 📁 Path to your sorted facts directory
fact_dir = r"C:\Users\tmulrenan\Desktop\Factbook Project\facts\newsorted"

def find_duplicate_answers(directory):
    answer_map = defaultdict(list)
    total_answers = 0

    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            path = os.path.join(directory, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    facts = json.load(f)

                for fact in facts:
                    answer = fact.get("activity_answer")
                    if answer:
                        answer_map[answer].append({
                            "title": fact.get("title", "[No title]"),
                            "file": filename
                        })
                        total_answers += 1

            except Exception as e:
                print(f"❌ Error reading {filename}: {e}")

    duplicates = {ans: entries for ans, entries in answer_map.items() if len(entries) > 1}

    print("🎯 Duplicate Activity Answers Found:")
    for answer, occurrences in duplicates.items():
        print(f"\n• \"{answer}\" → {len(occurrences)} times")
        for item in occurrences:
            print(f"   ↳ {item['title']} ({item['file']})")

    print(f"\n🧾 Total answers found: {total_answers}")
    print(f"🔢 Unique answers: {len(answer_map)}")

if __name__ == "__main__":
    find_duplicate_answers(fact_dir)
