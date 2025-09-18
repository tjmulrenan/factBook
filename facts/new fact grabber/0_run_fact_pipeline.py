import os
import sys
import time
import subprocess
from datetime import datetime, timedelta

# Force UTF-8 in child processes (fixes emoji/Unicode on Windows)
ENV = os.environ.copy()
ENV["PYTHONUTF8"] = "1"
ENV["PYTHONIOENCODING"] = "utf-8"

# ---- CONFIG ----
# Use a leap year so Sep 7 = 251, etc.
LEAP_YEAR = 2024

# The exact filenames you gave (kept as-is)
PIPELINE = [
    ("a_dayFactGrabber.py", False),
    ("a_holdayGrabber.py", False),   # (spelling kept exactly as provided)
    ("b_holidayScorer.py", False),
    ("c_holidayEnhancer.py", False),
    ("3_factCuller.py", True),       # stays interactive for manual input/steps
    ("4_factEnhancer.py", False),
    ("5_factCombiner.py", False),
]

GAP_SECONDS = 5  # gap between each script


def doy_to_month_day(doy: int, year: int = LEAP_YEAR):
    base = datetime(year, 1, 1) + timedelta(days=doy - 1)
    return base.strftime("%B"), base.day


def countdown(seconds: int):
    for i in range(seconds, 0, -1):
        print(f"   …starting next step in {i}s", end="\r", flush=True)
        time.sleep(1)
    print(" " * 40, end="\r")


def run_script_with_input(py_exe: str, script_path: str, doy: int, cwd: str):
    """
    Non-interactive run: feed the DOY then wait for completion.
    """
    print(f"▶ Running: {os.path.basename(script_path)} (auto-feeding DOY={doy})")
    proc = subprocess.Popen(
        [py_exe, script_path],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        env=ENV,  # <-- added
    )
    # Send DOY followed by newline, then close stdin
    out, _ = proc.communicate(input=f"{doy}\n")
    print(out, end="" if out.endswith("\n") else "\n")
    if proc.returncode != 0:
        raise RuntimeError(f"{os.path.basename(script_path)} exited with code {proc.returncode}")


def run_script_interactive(py_exe: str, script_path: str, cwd: str, doy: int):
    """
    Fully interactive run: inherits your console.
    We also pass the DOY (via arg) so the script can auto-select the right file.
    """
    print(f"▶ Running interactively: {os.path.basename(script_path)}")
    print("   (Auto-passing DOY; the rest remains fully manual.)\n")
    # Pass as CLI arg; you already set ENV["FACTBOOK_DOY"] too (belt & braces)
    rc = subprocess.call([py_exe, script_path, f"--doy={doy}"], cwd=cwd, env=ENV)
    if rc != 0:
        raise RuntimeError(f"{os.path.basename(script_path)} exited with code {rc}")

def main():
    # Ensure working directory is this file's directory
    folder = os.path.dirname(os.path.abspath(__file__))
    py_exe = sys.executable  # same interpreter you used to launch this orchestrator

    # Prompt once for DOY
    print("Enter day-of-year number (1–366). Example: 251 for Sep 7.")
    raw = input("DOY: ").strip()
    try:
        doy = int(raw)
        if not (1 <= doy <= 366):
            raise ValueError
    except ValueError:
        print("❌ Invalid day-of-year.")
        sys.exit(1)

    month, day = doy_to_month_day(doy)
    print(f"✅ You chose DOY {doy} → {month} {day} (using {LEAP_YEAR}).\n")

    # Make DOY available to interactive scripts (e.g., 3_factCuller.py)
    ENV["FACTBOOK_DOY"] = str(doy)

    # Run the pipeline
    for idx, (script, interactive) in enumerate(PIPELINE, start=1):
        script_path = os.path.join(folder, script)
        if not os.path.exists(script_path):
            print(f"⚠️  Skipping missing file: {script}")
            continue

        step_label = f"[{idx}/{len(PIPELINE)}]"
        print(f"{step_label} Preparing to run {script} …")
        countdown(GAP_SECONDS)

        try:
            if interactive:
                run_script_interactive(py_exe, script_path, folder, doy)
            else:
                run_script_with_input(py_exe, script_path, doy, folder)
            print(f"✔ Finished: {script}\n")
        except Exception as e:
            print(f"❌ Error in {script}: {e}")
            # Stop on error so you can see what happened
            sys.exit(1)

    print("🎉 All done!")


if __name__ == "__main__":
    main()
