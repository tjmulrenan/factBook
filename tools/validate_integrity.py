#!/usr/bin/env python3
"""
Validate that each factbook folder exists and has all required output files.

Checks:
  1. Every expected day-of-year folder exists (1..366, leap year).
  2. Each existing expected folder contains:
        - book_cover.pdf
        - front_cover.png
        - full_manuscript.pdf
        - spine.png

Prints:
  - Missing folders (days that never generated a folder)
  - Folders that exist but are missing one or more files
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import FINAL_OUTPUT_DIR, LEAP_YEAR

# --- config -------------------------------------------------------------

BASE_DIR = FINAL_OUTPUT_DIR

REQUIRED_FILES = [
    "book_cover.pdf",
    "front_cover.png",
    "full_manuscript.pdf",
    "spine.png",
]

# LEAP_YEAR is imported from config above


# --- helpers ------------------------------------------------------------

def generate_expected_folder_names():
    """
    Generate all expected folder names for a leap year in the format:
        "<DOY>_<MonthName>_<DayNumber>"
    e.g. "1_January_1", "46_February_15", "159_June_7"
    """
    start = date(LEAP_YEAR, 1, 1)
    names = []
    for offset in range(366):  # 0..365 → DOY 1..366
        d = start + timedelta(days=offset)
        doy = offset + 1
        month_name = d.strftime("%B")  # "January", "February", etc.
        day = d.day
        folder_name = f"{doy}_{month_name}_{day}"
        names.append(folder_name)
    return names


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


# --- main ---------------------------------------------------------------

def main():
    if not BASE_DIR.is_dir():
        print(f"ERROR: Base directory does not exist: {BASE_DIR}")
        return

    print(f"Checking folders in: {BASE_DIR}")
    print(f"Required files: {', '.join(REQUIRED_FILES)}")
    print("-" * 70)

    expected_folders = generate_expected_folder_names()
    existing_folder_names = {
        entry.name for entry in BASE_DIR.iterdir() if entry.is_dir()
    }

    missing_folders = []  # expected folders that don't exist at all
    missing_files_summary = {}  # folder_name -> list of missing files
    checked_folders = 0

    for folder_name in expected_folders:
        folder_path = BASE_DIR / folder_name

        if not folder_path.is_dir():
            # Folder for this DOY is completely missing
            missing_folders.append(folder_name)
            continue

        # Folder exists → validate its files
        checked_folders += 1
        missing_files = validate_folder(folder_path)
        if missing_files:
            missing_files_summary[folder_name] = missing_files

    # --- report ---------------------------------------------------------

    print()
    print(f"Expected folders (leap year): {len(expected_folders)}")
    print(f"Existing expected folders checked: {checked_folders}")

    # 1. Report completely missing folders (e.g. June 7)
    print()
    if not missing_folders:
        print("All expected day folders exist.")
    else:
        print("Missing day folders (folder does not exist at all):")
        print("-" * 70)
        for name in missing_folders:
            print(name)
        print("-" * 70)
        print(f"Total missing folders: {len(missing_folders)}")

    # 2. Report folders that exist but are missing files
    print()
    if not missing_files_summary:
        print("All existing expected folders contain all required files.")
    else:
        print("Folders with missing files:")
        print("-" * 70)
        for folder_name, missing_files in missing_files_summary.items():
            print(f"{folder_name}: missing {', '.join(missing_files)}")
        print("-" * 70)
        print(f"Total folders missing files: {len(missing_files_summary)}")


if __name__ == "__main__":
    main()
