#!/usr/bin/env python3

from pathlib import Path

# Root folder to scan
ROOT = Path(r"C:\Personal\What Happened On... (The Complete Collection)")

# Map of old name -> new name (all lowercase keys for case-insensitive match)
NAME_MAP = {
    "full_manuscript_2.pdf": "full_manuscript_3.pdf",
    "book_cover_2.pdf": "book_cover_3.pdf",
}

def main():
    if not ROOT.exists():
        print(f"Root folder does not exist: {ROOT}")
        return

    renamed = 0
    skipped = 0
    conflicts = 0

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        old_name_lower = path.name.lower()
        if old_name_lower in NAME_MAP:
            new_name = NAME_MAP[old_name_lower]
            new_path = path.with_name(new_name)

            if new_path.exists():
                print(f"⚠️  Skipping (target already exists): {new_path}")
                conflicts += 1
                continue

            try:
                print(f"Renaming: {path} -> {new_path}")
                path.rename(new_path)
                renamed += 1
            except Exception as e:
                print(f"Could not rename {path}: {e}")
        else:
            skipped += 1

    print(f"\nDone. Renamed {renamed} files. Skipped {skipped} other files. Conflicts: {conflicts}.")

if __name__ == "__main__":
    main()
