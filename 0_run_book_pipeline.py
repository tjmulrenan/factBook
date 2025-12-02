# 0_run_book_pipeline.py
# Batch runner: scan FINAL/*, find which days don't have full_manuscript.pdf,
# and run the full pipeline for those days only.

import os
import sys
import time
import subprocess
from typing import List, Tuple
import shutil  # for deleting build_docs
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = r"C:\Personal\factBook"
FINAL_ROOT = r"C:\Personal\What Happened On... (The Complete Collection)"

# tweak this if you still want a gap between stages (within one day)
PAUSE_BETWEEN_STEPS_SECONDS = 5  # was 15

# 🔢 how many days to process per run (and also max parallel days)
MAX_DAYS_PER_RUN = 3
MAX_PARALLEL_DAYS = 3
MAX_RETRIES_PER_DAY = 2

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
        msg = f"❌ {step_name} for {book_number} failed with exit code {e.returncode}."
        print(msg)
        # raise instead of sys.exit so parallel runs can keep going
        raise RuntimeError(msg) from e


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


def run_pipeline_for_day(
    day_num: str,
    folder_path: str,
    step1: str,
    step2: str,
    step3: str,
    step4: str,
) -> None:
    """
    Run the full 4-step pipeline for a single day (sequential for that day).
    This is what we run in parallel for different days.
    """
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

    # Clean up build_docs now that everything is generated
    build_docs_path = os.path.join(folder_path, "build_docs")
    if os.path.exists(build_docs_path):
        print(f"Removing build_docs folder for day {day_num}: {build_docs_path}")
        shutil.rmtree(build_docs_path, ignore_errors=False)
    else:
        print(f"No build_docs folder found for day {day_num}; nothing to clean.")

    print(f"✅ Finished {day_num}")

def run_pipeline_with_retries(
    day_num: str,
    folder_path: str,
    step1: str,
    step2: str,
    step3: str,
    step4: str,
    max_retries: int = MAX_RETRIES_PER_DAY,
) -> None:
    """
    Wrapper that retries the full pipeline for a day up to max_retries times.
    Raises if all attempts fail.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n🔁 Day {day_num}: attempt {attempt}/{max_retries}")
            run_pipeline_for_day(day_num, folder_path, step1, step2, step3, step4)
            print(f"✅ Day {day_num} succeeded on attempt {attempt}")
            return
        except Exception as e:
            last_error = e
            print(f"⚠️ Day {day_num} failed on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                print("   ↪️ Will retry...")
                time.sleep(5)  # small pause before next attempt

    # If we get here, all attempts failed
    raise last_error

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

    batch_index = 1
    failed_days_overall = []  # keep track of any days that never succeeded

    while True:
        day_folders = detect_day_folders()
        if not day_folders:
            print("❌ No day folders found inside FINAL.")
            sys.exit(1)

        # figure out which days are still missing full_manuscript.pdf
        to_process = [(day_num, path) for (day_num, path) in day_folders if not is_day_done(path)]

        if not to_process:
            print("✅ All days already have full_manuscript.pdf. Nothing left to do.")
            break

        total_remaining = len(to_process)

        # take the next batch of up to MAX_DAYS_PER_RUN
        batch = to_process[:MAX_DAYS_PER_RUN]

        print("\n==============================")
        print(f"🧮 Batch {batch_index}: {len(batch)} day(s) (out of {total_remaining} remaining)")
        print("==============================")
        for day_num, path in batch:
            print(f"   - {day_num}: {path}")

        print(f"\n🚀 Starting batch {batch_index} with up to {MAX_PARALLEL_DAYS} in parallel...\n")

        results = {}

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_DAYS) as executor:
            future_to_day = {
                executor.submit(
                    run_pipeline_with_retries,
                    day_num,
                    folder_path,
                    step1,
                    step2,
                    step3,
                    step4,
                ): day_num
                for day_num, folder_path in batch
            }

            for future in as_completed(future_to_day):
                day_num = future_to_day[future]
                try:
                    future.result()
                    results[day_num] = "ok"
                except BaseException as e:
                    print(f"❌ Pipeline for day {day_num} failed even after retries: {e}")
                    results[day_num] = f"failed: {e}"
                    failed_days_overall.append(day_num)

        print("\n📊 Batch summary:")
        for day_num in sorted(results, key=lambda d: int(d)):
            print(f"  • Day {day_num}: {results[day_num]}")

        print(f"\n✅ Batch {batch_index} finished. Checking for more days...\n")
        batch_index += 1

    # Final overall summary
    if failed_days_overall:
        failed_days_overall = sorted(set(failed_days_overall), key=lambda d: int(d))
        print("\n⚠ These days failed even after retries and will need manual attention:")
        print("   " + ", ".join(failed_days_overall))
    else:
        print("\n✅ All days succeeded.")

    print("\n🏁 All done.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Cancelled by user.")
