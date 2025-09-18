# 0_run_book_pipeline.py
# Run the full book pipeline: 1_generateBook -> 2_gapFill -> 3_generateSpeechBubbles
# Adds a 15-second pause between each step and passes the chosen book number to each script.

import os
import sys
import time
import subprocess

def run_step(step_name: str, script_path: str, book_number: str) -> None:
    print(f"\n===== 🚀 {step_name} =====")
    print(f"▶ Running: {script_path}")
    try:
        # Feed the number to the child process' stdin so it doesn't prompt you again.
        completed = subprocess.run(
            [sys.executable, script_path],
            input=book_number + "\n",
            text=True,
            cwd=os.path.dirname(script_path),  # run inside script's folder (optional)
            check=True
        )
        print(f"✅ {step_name} completed.")
    except subprocess.CalledProcessError as e:
        print(f"❌ {step_name} failed with exit code {e.returncode}. Aborting.")
        sys.exit(e.returncode)

def main():
    # Root of your project (this file should live here too)
    PROJECT_ROOT = r"C:\Users\timmu\Documents\repos\Factbook Project"

    # Script paths
    step1 = os.path.join(PROJECT_ROOT, "1_generateBook.py")
    step2 = os.path.join(PROJECT_ROOT, "2_gapFill.py")
    step3 = os.path.join(PROJECT_ROOT, "3_generateSpeechBubbles.py")

    # Basic presence check so we fail fast if something is missing
    for p in (step1, step2, step3):
        if not os.path.exists(p):
            print(f"❌ Not found: {p}")
            sys.exit(1)

    # Ask once for the book number
    book_number = input("Type the book number (e.g., 89): ").strip()
    if not book_number.isdigit():
        print("❌ Please enter a valid number, e.g., 89")
        sys.exit(1)

    # Step 1
    run_step("Step 1: Generate base PDF (1.pdf) + overlays", step1, book_number)
    print("⏳ Waiting 15 seconds before next step...")
    time.sleep(15)

    # Step 2
    run_step("Step 2: Visually fill transparent gaps (-> 2.pdf)", step2, book_number)
    print("⏳ Waiting 15 seconds before next step...")
    time.sleep(15)

    # Step 3
    run_step("Step 3: Add speech bubbles + compress (-> 3.pdf & full_manuscript.pdf)", step3, book_number)
    print("⏳ Waiting 15 seconds before next step...")
    time.sleep(15)

    # Step 4 (NEW): Build paperback cover (uses FINAL/<DOY>_* folder)
    step4 = os.path.join(PROJECT_ROOT, "b_coverBuild_paperback.py")  # <-- adjust if filename differs
    if not os.path.exists(step4):
        print(f"❌ Not found: {step4}")
        sys.exit(1)

    run_step("Step 4: Build paperback cover (book_cover.pdf)", step4, book_number)

    print("\n🎉 All steps finished!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Cancelled by user.")
