#!/usr/bin/env python3
"""
Validate that each factbook folder has all required output files.

Checks every subdirectory of BASE_DIR and verifies that it contains:
    - book_cover.pdf
    - front_cover.png
    - full_manuscript.pdf
    - spine.png

Prints a summary at the end listing any folders that are missing files.
"""

import os
from pathlib import Path

# --- config -------------------------------------------------------------

BASE_DIR = Path(r"C:\Personal\What Happened On... (The Complete Collection)")

REQUIRED_FILES = [
    "book_cover.pdf",
    "front_cover.png",
    "full_manuscript.pdf",
    "spine.png",
]


# --- logic --------------------------------------------------------------


def validate_folder(folder: Path):
    """
    Return a list of missing required files for a single folder.
    If all required files exist, returns an empty list.
    """
    missing = []
    for filename in REQUIRED_FILES:
        if not (folder / filename).is_file():
            missing.append(filename)
    return missing


def main():
    if not BASE_DIR.is_dir():
        print(f"ERROR: Base directory does not exist: {BASE_DIR}")
        return

    print(f"Checking folders in: {BASE_DIR}")
    print(f"Required files: {', '.join(REQUIRED_FILES)}")
    print("-" * 70)

    missing_summary = {}  # folder_name -> list of missing files
    checked_folders = 0

    # Iterate over all immediate subdirectories of BASE_DIR
    for entry in sorted(BASE_DIR.iterdir()):
        if entry.is_dir():
            checked_folders += 1
            missing = validate_folder(entry)
            if missing:
                missing_summary[entry.name] = missing

    # --- report ---------------------------------------------------------

    print()
    print(f"Checked {checked_folders} folder(s).")

    if not missing_summary:
        print("All folders contain all required files. ✅")
        return

    print()
    print("Folders with missing files:")
    print("-" * 70)

    for folder_name, missing_files in missing_summary.items():
        print(f"{folder_name}: missing {', '.join(missing_files)}")

    print("-" * 70)
    print(f"Total folders missing files: {len(missing_summary)}")


if __name__ == "__main__":
    main()
