import os
import sys
import time
import subprocess
from datetime import datetime, timedelta

# ----- Environment (fix Windows emoji/Unicode) -----
ENV = os.environ.copy()
ENV["PYTHONUTF8"] = "1"
ENV["PYTHONIOENCODING"] = "utf-8"

# ----- Config -----
LEAP_YEAR = 2024                       # keep leap-year mapping (Sep 7 = 251 etc)
START_FROM_OCTOBER = True              # always sweep starting in October
OCT1_DOY = 275                         # Oct 1 in a leap year
END_DOY = 366                          # Dec 31
GAP_SECONDS = 5                        # delay between scripts

# Pipeline (unchanged; culler is interactive)
PIPELINE = [
    ("a_dayFactGrabber.py", False),
    ("a_holdayGrabber.py", False),   # spelling kept as provided
    ("b_holidayScorer.py", False),
    ("c_holidayEnhancer.py", False),
    ("3_factCuller.py", True),       # stays interactive
    ("4_factEnhancer.py", False),
    ("5_factCombiner.py", False),
]

# Relative to this script's folder
FINAL_DIR_REL = os.path.join("6_final")


# ----- Helpers -----
def doy_to_month_day(doy: int, year: int = LEAP_YEAR):
    base = datetime(year, 1, 1) + timedelta(days=doy - 1)
    return base.strftime("%B"), base.day


def final_json_path(root_folder: str, doy: int) -> str:
    """Return the expected final JSON path for this DOY: e.g. 275_October_1_Final.json"""
    month, day = doy_to_month_day(doy)
    fname = f"{doy}_{month}_{day}_Final.json"
    return os.path.join(root_folder, FINAL_DIR_REL, fname)


def countdown(seconds: int):
    for i in range(seconds, 0, -1):
        print(f"   …starting next step in {i}s", end="\r", flush=True)
        time.sleep(1)
    print(" " * 40, end="\r")


def run_script_with_input(py_exe: str, script_path: str, doy: int, cwd: str):
    """Non-interactive: feed DOY via stdin"""
    print(f"▶ Running: {os.path.basename(script_path)} (auto-feeding DOY={doy})")
    proc = subprocess.Popen(
        [py_exe, script_path],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        env=ENV,
    )
    out, _ = proc.communicate(input=f"{doy}\n")
    print(out, end="" if out.endswith("\n") else "\n")
    if proc.returncode != 0:
        raise RuntimeError(f"{os.path.basename(script_path)} exited with code {proc.returncode}")


def run_script_interactive(py_exe: str, script_path: str, cwd: str, doy: int):
    """Interactive: inherit console; also pass --doy so your script can auto-select the right file"""
    print(f"▶ Running interactively: {os.path.basename(script_path)}")
    print("   (Auto-passing DOY; the rest remains fully manual.)\n")
    rc = subprocess.call([py_exe, script_path, f"--doy={doy}"], cwd=cwd, env=ENV)
    if rc != 0:
        raise RuntimeError(f"{os.path.basename(script_path)} exited with code {rc}")


def run_pipeline_for_doy(folder: str, py_exe: str, doy: int) -> str:
    """
    Run the full pipeline for a single DOY if not already completed.
    Returns 'skipped', 'ok', or raises on error.
    """
    # Skip if Final JSON already exists
    final_path = final_json_path(folder, doy)
    if os.path.exists(final_path):
        print(f"⏭️  Skip DOY {doy}: final already exists -> {os.path.relpath(final_path, folder)}")
        return "skipped"

    month, day = doy_to_month_day(doy)
    print(f"\n================= DOY {doy} — {month} {day} =================")

    # Make DOY available to scripts that read ENV (e.g., 3_factCuller.py)
    ENV["FACTBOOK_DOY"] = str(doy)

    # Run the pipeline steps
    for idx, (script, interactive) in enumerate(PIPELINE, start=1):
        script_path = os.path.join(folder, script)
        if not os.path.exists(script_path):
            print(f"⚠️  Skipping missing file: {script}")
            continue

        step_label = f"[{idx}/{len(PIPELINE)}]"
        print(f"{step_label} Preparing to run {script} …")
        countdown(GAP_SECONDS)

        if interactive:
            run_script_interactive(py_exe, script_path, folder, doy)
        else:
            run_script_with_input(py_exe, script_path, doy, folder)
        print(f"✔ Finished: {script}\n")

    # After pipeline completes, re-check that Final JSON exists (optional sanity)
    if os.path.exists(final_path):
        print(f"✅ Completed DOY {doy}: created {os.path.relpath(final_path, folder)}")
    else:
        print(f"ℹ️  Note: {os.path.relpath(final_path, folder)} not found. "
              f"If your pipeline writes the final later, that's okay—just letting you know.")

    return "ok"


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    py_exe = sys.executable

    # Build sweep order: Oct 1 → Dec 31, then Jan 1 → Sep 30
    if START_FROM_OCTOBER:
        order = list(range(OCT1_DOY, END_DOY + 1)) + list(range(1, OCT1_DOY))
    else:
        # Fallback: ask for a single DOY (original behavior)
        print("Enter day-of-year number (1–366). Example: 251 for Sep 7.")
        raw = input("DOY: ").strip()
        try:
            single_doy = int(raw)
            if not (1 <= single_doy <= 366):
                raise ValueError
        except ValueError:
            print("❌ Invalid day-of-year.")
            sys.exit(1)
        order = [single_doy]

    # Ensure final dir exists (not required to run, but nice to have)
    os.makedirs(os.path.join(folder, FINAL_DIR_REL), exist_ok=True)

    results = {"ok": 0, "skipped": 0, "failed": 0}
    for doy in order:
        try:
            status = run_pipeline_for_doy(folder, py_exe, doy)
            results[status] += 1
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break
        except Exception as e:
            print(f"❌ Error on DOY {doy}: {e}")
            results["failed"] += 1
            # Stop on first error so you can inspect
            break

    # Summary
    print("\n========== SUMMARY ==========")
    print(f"Processed OK: {results['ok']}")
    print(f"Already done (skipped): {results['skipped']}")
    print(f"Failed: {results['failed']}")
    print("🎉 Sweep complete.")


if __name__ == "__main__":
    main()
