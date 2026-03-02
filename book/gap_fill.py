import io
import math
import os
import re
import sys
from itertools import groupby
from operator import itemgetter
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw

# --- thresholds / detection ---
BRIGHTNESS_THRESHOLD_ROW = 200
BRIGHTNESS_THRESHOLD_COL = 200
INK_MAX_BRIGHTNESS = 70          # ≤ this = “ink” (very dark) → ignore in gap logic
ROW_BRIGHT_MIN_FRAC = 0.70       # row is bright if ≥70% of non-ink pixels are bright

# --- right margin band for detection (as fraction of width) ---
MARGIN_RIGHT_START_RATIO = 0.86
MARGIN_RIGHT_END_RATIO   = 0.88

TOP_SKIP_PX = 80  # ignore the top region when detecting gaps

# Force fixed cloud span (pixels at the rendered DPI)
FORCE_X_RANGE = (100, 799)      # ← fixed width like before
FORCE_Y_RANGE = None            # keep auto height

def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def detect_special_layout(image_rgba, page=None):
    """
    Lightweight detector for Letter Quest / Grid Gauntlet pages using PDF text only.
    """
    txt = page.get_text("text") if page is not None else ""
    norm = _norm(txt)

    is_lq_answers = bool(re.search(r"\bletter quest answers\b", norm))
    is_lq         = bool(re.search(r"\bletter quest\b", norm)) and not is_lq_answers

    is_gg_answers = bool(re.search(r"\bgrid gauntlet answers\b", norm))
    is_gg         = bool(re.search(r"\bgrid gauntlet\b", norm)) and not is_gg_answers

    return {
        "letter_quest": is_lq,
        "letter_quest_answers": is_lq_answers,
        "grid_gauntlet": is_gg,
        "grid_gauntlet_answers": is_gg_answers,
        "raw_text": txt,
    }

def generate_top_semicircle_cutouts(x0, y0, x1, y1, num_bumps=12, radius=None):
    if radius is None:
        radius = (x1 - x0) / (2 * num_bumps)
    path = []
    for i in range(num_bumps):
        cx = x0 + (2 * i + 1) * radius
        theta_vals = np.linspace(np.pi, 2 * np.pi, 30)
        for theta in theta_vals:
            x = cx + radius * np.cos(theta)
            y = y0 - radius * np.sin(theta)
            path.append((x, y))
    return path

def generate_soft_cloud_path(x, y, w, h, bumps_x=8, bumps_y=6, radius=15):
    points = []
    # Top
    for i in range(bumps_x + 1):
        t = i / bumps_x
        cx = x + t * w
        cy = y - math.sin(t * math.pi) * radius
        points.append((cx, cy))
    # Right
    for i in range(bumps_y + 1):
        t = i / bumps_y
        cx = x + w + math.sin(t * math.pi) * radius
        cy = y + t * h
        points.append((cx, cy))
    # Bottom
    for i in range(bumps_x + 1):
        t = i / bumps_x
        cx = x + w - t * w
        cy = y + h + math.sin(t * math.pi) * radius
        points.append((cx, cy))
    # Left
    for i in range(bumps_y + 1):
        t = i / bumps_y
        cx = x - math.sin(t * math.pi) * radius
        cy = y + h - t * h
        points.append((cx, cy))
    return points

def visually_fill_transparent_gaps(pdf_path, out_path, alpha=0.85, dpi=144):
    """
    Process pdf_path and write the cloud-filled result directly to out_path.
    No intermediate *_clouds.pdf files are produced.
    """
    doc = fitz.open(pdf_path)
    page_count = len(doc)

    # Once we see "Letter Quest Answers", we enter answers phase;
    # in this phase, we only cloud LQ/GG answers pages (top block only)
    answers_phase_started = False

    for page_index in range(page_count):
        if page_index == 0:
            print("🚫 Skipping page 1.")
            continue

        page = doc[page_index]
        print(f"\n📄 Processing page {page_index + 1}/{page_count}")

        # Render page → RGBA image
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(alpha=True, matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
        arr = np.array(img)
        height, width = arr.shape[:2]

        # Fixed right-margin band
        mx0 = int(width * MARGIN_RIGHT_START_RATIO)
        mx1 = int(width * MARGIN_RIGHT_END_RATIO)
        mx0 = max(0, min(mx0, width - 1))
        mx1 = max(mx0 + 1, min(mx1, width))

        # Detect bright rows in margin band
        bright_rows = []
        stripe = arr[:, mx0:mx1, :3]
        lum = stripe.mean(axis=2)
        ink_mask = lum <= INK_MAX_BRIGHTNESS
        bright_mask = lum > BRIGHTNESS_THRESHOLD_ROW

        for y in range(TOP_SKIP_PX, height):
            valid = ~ink_mask[y]
            vc = valid.sum()
            if vc == 0:
                continue
            if ((bright_mask[y] & valid).sum() / vc) >= ROW_BRIGHT_MIN_FRAC:
                bright_rows.append(y)

        # Group rows → blocks
        blocks = []
        for _, g in groupby(enumerate(bright_rows), lambda ix: ix[0] - ix[1]):
            group = list(map(itemgetter(1), g))
            if len(group) <= 3:
                continue
            start_y = min(group)
            end_y = max(group)

            # Confirm brightness in the margin, then expand to full width
            block_slice_margin = arr[start_y:end_y + 1, mx0:mx1, :3]
            lum_cols_m = block_slice_margin.mean(axis=2)
            ink_cols_m = lum_cols_m <= INK_MAX_BRIGHTNESS
            bright_cols_mask_m = lum_cols_m > BRIGHTNESS_THRESHOLD_COL
            vpm = (~ink_cols_m).sum(axis=0)
            vpm = np.where(vpm == 0, 1, vpm)
            bright_frac_cols_m = (bright_cols_mask_m & ~ink_cols_m).sum(axis=0) / vpm
            has_bright_in_margin = np.any(bright_frac_cols_m >= ROW_BRIGHT_MIN_FRAC)
            if not has_bright_in_margin:
                continue

            block_slice_full = arr[start_y:end_y + 1, :, :3]
            lum_cols_f = block_slice_full.mean(axis=2)
            ink_cols_f = lum_cols_f <= BRIGHTNESS_THRESHOLD_COL
            bright_cols_mask_f = lum_cols_f > BRIGHTNESS_THRESHOLD_COL
            vpf = (~ink_cols_f).sum(axis=0)
            vpf = np.where(vpf == 0, 1, vpf)
            bright_frac_cols_f = (bright_cols_mask_f & ~ink_cols_f).sum(axis=0) / vpf
            bright_cols_f = np.where(bright_frac_cols_f >= ROW_BRIGHT_MIN_FRAC)[0]
            if len(bright_cols_f) == 0:
                continue

            x_start = int(np.min(bright_cols_f))
            x_end = int(np.max(bright_cols_f))
            blocks.append((start_y, end_y, x_start, x_end))

        flags = detect_special_layout(img, page=page)
        is_lq  = flags["letter_quest"]
        is_gg  = flags["grid_gauntlet"]
        is_lqa = flags["letter_quest_answers"]
        is_gga = flags["grid_gauntlet_answers"]

        if not blocks:
            print(f"ℹ️ Page {page_index + 1}: no bright blocks found.")
            continue

        top_block = min(blocks, key=lambda b: b[0])

        if not answers_phase_started:
            if is_lqa:
                grouped_blocks = [[top_block]]
                answers_phase_started = True
                print("🔔 Entered answers phase (after Letter Quest Answers).")
            elif is_lq or is_gg:
                grouped_blocks = [[top_block]]
            else:
                grouped_blocks = [blocks]
        else:
            if is_lqa or is_gga:
                grouped_blocks = [[top_block]]
                print("📌 Answers page (LQ/GG) during answers phase.")
            else:
                print(f"⏭️ Skipping clouds on page {page_index + 1} (post-LQ Answers, non-answers page).")
                continue

        # Draw clouds
        for group in grouped_blocks:
            cloud_top = group[0][0]
            cloud_bottom = group[-1][1]
            cloud_x_start = max(b[2] for b in group)
            cloud_x_end   = min(b[3] for b in group)

            if FORCE_X_RANGE is not None:
                left_fixed, right_fixed = FORCE_X_RANGE
                cloud_x_start = max(0, min(left_fixed, width - 1))
                cloud_x_end   = max(cloud_x_start + 1, min(right_fixed, width))

            if FORCE_Y_RANGE is not None:
                top_fixed, bottom_fixed = FORCE_Y_RANGE
                cloud_top    = max(0, min(top_fixed, height - 1))
                cloud_bottom = max(cloud_top + 1, min(bottom_fixed, height))

            x0, y0 = cloud_x_start - 25, cloud_top - 25
            w = (cloud_x_end - cloud_x_start) + 50
            h = (cloud_bottom - cloud_top) + 50

            SCALE = 4
            cloud_hr = Image.new("RGBA", (width * SCALE, height * SCALE), (0, 0, 0, 0))
            draw_hr = ImageDraw.Draw(cloud_hr)

            x0_hr = x0 * SCALE; y0_hr = y0 * SCALE
            w_hr = w * SCALE;   h_hr = h * SCALE
            xs_hr = cloud_x_start * SCALE; xe_hr = cloud_x_end * SCALE
            yt_hr = cloud_top * SCALE;     yb_hr = cloud_bottom * SCALE

            path = generate_soft_cloud_path(x0_hr, y0_hr, w_hr, h_hr, bumps_x=10, bumps_y=8, radius=18 * SCALE)
            draw_hr.polygon(path, fill=(255, 255, 255, int(alpha * 255)))
            draw_hr.rectangle([(xs_hr, yt_hr), (xe_hr, yb_hr)], fill=(0, 0, 0, 0))

            scallops = generate_top_semicircle_cutouts(xs_hr, yt_hr, xe_hr, yt_hr, num_bumps=20, radius=12 * SCALE)
            draw_hr.polygon(scallops, fill=(0, 0, 0, 0))
            draw_hr.line(path + [path[0]], fill=(0, 0, 0, 255), width=5 * SCALE, joint="curve")

            cloud_final = cloud_hr.resize((width, height), resample=Image.LANCZOS)
            img = Image.alpha_composite(img, cloud_final)

        # Write the modified page back
        out_bytes = io.BytesIO()
        img.save(out_bytes, format="PNG")
        page.insert_image(page.rect, stream=out_bytes.getvalue(), overlay=True)

    # Direct save to out_path (no temp files)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path, deflate=True, garbage=4, clean=True)
    doc.close()
    print(f"💾 Saved clouds → {out_path}")

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import FINAL_OUTPUT_DIR
    FINAL_ROOT = str(FINAL_OUTPUT_DIR)

    # Folders like: 89_March_29
    dir_re = re.compile(r'^(?P<num>\d+)_([A-Za-z]+)_(\d{1,2})$')

    # index: num -> month_day (e.g., "March_29"), only if build_docs/1.pdf exists
    index = {}
    try:
        for entry in os.listdir(FINAL_ROOT):
            m = dir_re.match(entry)
            if not m:
                continue
            num = int(m.group("num"))
            parts = entry.split("_")
            if len(parts) >= 3:
                month_day = f"{parts[1]}_{parts[2]}"
                build_dir = os.path.join(FINAL_ROOT, entry, "build_docs")
                if os.path.exists(os.path.join(build_dir, "1.pdf")):
                    index[num] = month_day
    except FileNotFoundError:
        print(f"❌ FINAL folder not found: {FINAL_ROOT}")
        sys.exit(1)

    if not index:
        print("❌ No valid <num>_<Month>_<Day> folders with build_docs\\1.pdf found.")
        sys.exit(1)

    _doy_arg = None
    for _a in sys.argv[1:]:
        _v = _a.lstrip("-").split("=", 1)
        if _v[0] == "doy" and len(_v) == 2:
            _doy_arg = _v[1]
            break
        if _v[0].isdigit():
            _doy_arg = _v[0]
            break
    user_in = _doy_arg or os.environ.get("FACTBOOK_DOY", "")
    if not user_in:
        user_in = input("Type the book number (e.g., 89): ").strip()
    if not str(user_in).isdigit():
        print("❌ Please enter a number, e.g., 89")
        sys.exit(1)

    pick = int(user_in)
    if pick not in index:
        hint = ", ".join(str(n) for n in sorted(index.keys())[:12])
        print(f"❌ {pick} not found. Known numbers start like: {hint} …")
        sys.exit(1)

    month_day = index[pick]
    folder = f"{pick}_{month_day}"
    build_dir = os.path.join(FINAL_ROOT, folder, "build_docs")
    in_pdf = os.path.join(build_dir, "1.pdf")
    out_pdf = os.path.join(build_dir, "2.pdf")

    if not os.path.exists(in_pdf):
        print(f"❌ Input not found: {in_pdf}")
        sys.exit(1)

    print(f"📄 Input:  {in_pdf}")
    print(f"📦 Output: {out_pdf}")

    visually_fill_transparent_gaps(in_pdf, out_pdf, alpha=0.85, dpi=144)

    print("✅ Done.")
