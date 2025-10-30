# 0_run_book_pipeline.py
# Batch runner: scan FINAL/*, find which days don't have full_manuscript.pdf,
# and run the full pipeline for those days only.

import os
import sys
import time
import subprocess
from typing import List, Tuple

PROJECT_ROOT = r"C:\Users\timmu\Documents\repos\Factbook Project"
FINAL_ROOT = os.path.join(PROJECT_ROOT, "FINAL")

# tweak this if you still want a gap between stages
PAUSE_BETWEEN_STEPS_SECONDS = 5  # was 15

def run_step(step_name: str, script_path: str, book_number: str) -> None:
    print(f"\n===== 🚀 {step_name} ({book_number}) =====")
    print(f"▶ Running: {script_path}")
    try:
        subprocess.run(
            [sys.executable, script_path],
            input=book_number + "\n",  # your scripts read the number from stdin
            text=True,
            cwd=os.path.dirname(script_path),
            check=True,
        )
        print(f"✅ {step_name} for {book_number} completed.")
    except subprocess.CalledProcessError as e:
        print(f"❌ {step_name} for {book_number} failed with exit code {e.returncode}. Aborting batch.")
        sys.exit(e.returncode)


def detect_day_folders() -> List[Tuple[str, str]]:
    """
    Look in FINAL and return a list of (day_number_str, full_folder_path).
    We assume folders are named like '1_January_1', '50_February_19', etc.
    """
    if not os.path.exists(FINAL_ROOT):
        print(f"❌ FINAL folder not found at {FINAL_ROOT}")
        sys.exit(1)

    day_folders: List[Tuple[str, str]] = []

    for name in os.listdir(FINAL_ROOT):
        folder_path = os.path.join(FINAL_ROOT, name)
        if not os.path.isdir(folder_path):
            continue

        # folder begins with number_
        parts = name.split("_", 1)
        if not parts:
            continue

        day_num = parts[0]
        if not day_num.isdigit():
            continue

        day_folders.append((day_num, folder_path))

    # sort by the numeric day so we run 1..366 in order
    day_folders.sort(key=lambda x: int(x[0]))
    return day_folders


def is_day_done(folder_path: str) -> bool:
    """
    A day is considered DONE if FINAL/<day>/full_manuscript.pdf exists.
    """
    manuscript_path = os.path.join(folder_path, "full_manuscript.pdf")
    return os.path.exists(manuscript_path)


def main():
    # script paths
    step1 = os.path.join(PROJECT_ROOT, "1_generateBook.py")
    step2 = os.path.join(PROJECT_ROOT, "2_gapFill.py")
    step3 = os.path.join(PROJECT_ROOT, "3_generateSpeechBubbles.py")
    step4 = os.path.join(PROJECT_ROOT, "b_coverBuild_paperback.py")

    for p in (step1, step2, step3, step4):
        if not os.path.exists(p):
            print(f"❌ Not found: {p}")
            sys.exit(1)

    day_folders = detect_day_folders()
    if not day_folders:
        print("❌ No day folders found inside FINAL.")
        sys.exit(1)

    print(f"🔎 Found {len(day_folders)} day folders under FINAL.")
    to_process = [(day_num, path) for (day_num, path) in day_folders if not is_day_done(path)]

    if not to_process:
        print("✅ All days already have full_manuscript.pdf. Nothing to do.")
        return

    print(f"🟡 {len(to_process)} day(s) need processing:")
    for day_num, path in to_process:
        print(f"   - {day_num}: {path}")

    # run pipeline per missing day
    for day_num, folder_path in to_process:
        print(f"\n==============================")
        print(f"📘 Processing day {day_num} ({folder_path})")
        print(f"==============================")

        # Step 1
        run_step("Step 1: Generate base PDF (1.pdf) + overlays", step1, day_num)
        time.sleep(PAUSE_BETWEEN_STEPS_SECONDS)

        # Step 2
        run_step("Step 2: Visually fill transparent gaps (-> 2.pdf)", step2, day_num)
        time.sleep(PAUSE_BETWEEN_STEPS_SECONDS)

        # Step 3
        run_step("Step 3: Add speech bubbles + compress (-> 3.pdf & full_manuscript.pdf)", step3, day_num)
        time.sleep(PAUSE_BETWEEN_STEPS_SECONDS)

        # Step 4
        run_step("Step 4: Build paperback cover (book_cover.pdf)", step4, day_num)

        print(f"🎯 Finished {day_num}")

    print("\n🎉 All missing days finished!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Cancelled by user.")
