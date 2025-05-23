import os
import json
from pathlib import Path

def assign_ids_to_facts_in_folder():
    folder = Path(__file__).parent
    json_files = [f for f in folder.iterdir() if f.suffix == '.json']

    for file in json_files:
        print(f"📂 Processing: {file.name}")
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        all_facts = []
        for section in ("Events", "Births"):
            facts = data.get(section, [])
            for fact in facts:
                all_facts.append({
                    "fact": fact,
                    "id": len(all_facts) + 1
                })

        # Save new format
        output_path = file.with_name(file.stem + "_with_ids.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_facts, f, indent=4, ensure_ascii=False)
        print(f"✅ Saved with IDs → {output_path.name}\n")

if __name__ == "__main__":
    assign_ids_to_facts_in_folder()
