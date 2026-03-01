#!/usr/bin/env python3

from pathlib import Path

# Root folder to scan
ROOT = Path(r"C:\Personal\What Happened On... (The Complete Collection)")

# File names to delete (case-insensitive)
TARGET_NAMES = {"full_manuscript.pdf", "book_cover.pdf"}

def main():
    if not ROOT.exists():
        print(f"Root folder does not exist: {ROOT}")
        return

    deleted = 0
    skipped = 0

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if path.name.lower() in TARGET_NAMES:
            try:
                print(f"Deleting: {path}")
                path.unlink()
                deleted += 1
            except Exception as e:
                print(f"Could not delete {path}: {e}")
        else:
            skipped += 1

    print(f"\nDone. Deleted {deleted} files. Skipped {skipped} other files.")

if __name__ == "__main__":
    main()
