import os
import json
from glob import glob

def count_facts_in_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return len(data.get("Facts", []))  # ← changed from "Events" to "Facts"


def main():
    folder = "facts"
    if not os.path.exists(folder):
        print(f"❌ Folder '{folder}' not found.")
        return

    fact_counts = []
    for filepath in glob(os.path.join(folder, "OnThisDay_*.json")):
        try:
            count = count_facts_in_file(filepath)
            day = os.path.basename(filepath).replace("OnThisDay_", "").replace(".json", "")
            fact_counts.append((day, count))
        except Exception as e:
            print(f"⚠️ Failed to read {filepath}: {e}")

    fact_counts.sort(key=lambda x: x[1])  # sort by number of facts

    print("\n📉 Bottom 10 days with fewest facts:")
    for day, count in fact_counts[:10]:
        print(f"{day}: {count} facts")

    print("\n📈 Top 10 days with most facts:")
    for day, count in fact_counts[-10:][::-1]:
        print(f"{day}: {count} facts")

if __name__ == "__main__":
    main()
