import json
import os
from pathlib import Path

# Define base folders
BASE_DIR = Path("C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber")
ENHANCED_DIR = BASE_DIR / "c_enhanced"
CATEGORISED_DIR = BASE_DIR / "5_catagorised"
OUTPUT_DIR = BASE_DIR / "6_final"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path):
    if not path.exists():
        print(f"❌ File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    # Prompt for date input
    month = input("Enter month (e.g., March): ").strip()
    day = input("Enter day (e.g., 29): ").strip()

    # Format base filename
    base_name = f"{month}_{day}"

    # Build full paths
    path1 = ENHANCED_DIR / f"{base_name}_Holidays_scored_enhanced.json"
    path2 = CATEGORISED_DIR / f"{base_name}_culled_enhanced_catagorised.json"
    output_path = OUTPUT_DIR / f"{base_name}_Final.json"

    print(f"\n📂 Combining:\n- {path1.name}\n- {path2.name}")

    # Load both files
    facts1 = load_json(path1)
    facts2 = load_json(path2)

    # Combine
    combined = facts1 + facts2
    print(f"✅ Combined {len(facts1)} + {len(facts2)} = {len(combined)} facts")

    # Save output
    save_json(output_path, combined)
    print(f"\n💾 Saved to: {output_path}")

if __name__ == "__main__":
    main()
