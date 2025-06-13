import json
import os

# Define base paths
BASE_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber"
SCORED_DIR = os.path.join(BASE_DIR, "2_scored")
CULLED_DIR = os.path.join(BASE_DIR, "3_culled")

# Ensure output directory exists
os.makedirs(CULLED_DIR, exist_ok=True)

# Loop through all scored JSON files
for filename in os.listdir(SCORED_DIR):
    if filename.endswith("_scored.json"):
        input_path = os.path.join(SCORED_DIR, filename)
        output_filename = filename.replace("_scored.json", "_culled.json")
        output_path = os.path.join(CULLED_DIR, output_filename)

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                facts = json.load(f)

            # Filter only kid-friendly facts
            kid_friendly = [fact for fact in facts if fact.get("is_kid_friendly") is True]

            # Sort by score (desc) and then id (asc)
            sorted_facts = sorted(
                kid_friendly,
                key=lambda x: (-x.get("score", 0), x.get("id", float("inf")))
            )

            # Take top 100
            top_100 = sorted_facts[:100]

            # Optionally strip max_word_limit if it exists
            for fact in top_100:
                fact.pop("max_word_limit", None)

            # Write to culled file
            with open(output_path, "w", encoding="utf-8") as f_out:
                json.dump(top_100, f_out, indent=2, ensure_ascii=False)

            print(f"✅ {filename} → {output_filename} ({len(top_100)} facts)")

        except Exception as e:
            print(f"❌ Failed to process {filename}: {e}")
