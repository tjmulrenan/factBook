import json
import os
import sys
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RAW_FACTS_DIR, CULLED_FACTS_DIR

def count_facts_in_file(file_path, is_culled=False):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if is_culled:
        return len(data)  # List of fact dicts
    else:
        return len(data.get("Facts", []))  # Dict with "Facts" key

def choose_folder():
    options = {
        "1": ("raw", str(RAW_FACTS_DIR)),
        "2": ("culled", str(CULLED_FACTS_DIR))
    }

    print("Choose a folder:")
    for k, (label, _) in options.items():
        print(f"{k}. {label}")

    choice = input("Enter 1 or 2: ").strip()
    selected = options.get(choice)
    if not selected:
        print("❌ Invalid selection.")
        return None, None

    label, folder = selected
    if not os.path.exists(folder):
        print(f"❌ Folder not found: {folder}")
        return None, None

    return label, folder

def choose_file(files):
    print("\nAvailable files:")
    for i, file in enumerate(files):
        print(f"{i + 1}. {os.path.basename(file)}")

    choice = input("Enter the number of the file to scan: ").strip()
    try:
        index = int(choice) - 1
        if 0 <= index < len(files):
            return files[index]
    except ValueError:
        pass

    print("❌ Invalid file selection.")
    return None

def main():
    label, folder = choose_folder()
    if not folder:
        return

    pattern = "*.json" if label == "culled" else "OnThisDay_*.json"
    files = glob(os.path.join(folder, pattern))
    if not files:
        print("❌ No matching JSON files found.")
        return

    file_path = choose_file(files)
    if not file_path:
        return

    is_culled = label == "culled"

    try:
        count = count_facts_in_file(file_path, is_culled=is_culled)
        print(f"\n✅ {os.path.basename(file_path)} contains {count} facts.")
    except Exception as e:
        print(f"⚠️ Failed to read {file_path}: {e}")

if __name__ == "__main__":
    main()
