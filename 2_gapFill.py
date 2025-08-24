import fitz
from PIL import Image, ImageDraw
import numpy as np
import io
from itertools import groupby
from operator import itemgetter
import random
import math
import pytesseract
import difflib
from PIL import ImageOps, ImageFilter
import re

BRIGHTNESS_THRESHOLD_ROW = 200
BRIGHTNESS_THRESHOLD_BLOCK = 220
BRIGHTNESS_THRESHOLD_COL = 200

INK_MAX_BRIGHTNESS = 70      # ≤ this = “ink” (very dark) → ignore in gap logic
ROW_BRIGHT_MIN_FRAC = 0.70   # row counts as bright if ≥70% of non-ink pixels are bright

# --- Margin band for whiteness detection (right side) ---
# Use ratios of page width so it works on any DPI / page
MARGIN_RIGHT_START_RATIO = 0.86   # left edge of margin band (e.g., 88% of width)
MARGIN_RIGHT_END_RATIO   = 0.88   # right edge of margin band (e.g., 98% of width)
GUIDE_LINE_WIDTH = 3             # pixels

TOP_SKIP_PX = 80  # ignore the top 20 pixels when detecting gaps
# If you want this to scale with DPI (e.g., 20pt), use:
# TOP_SKIP_PX = int((20/72) * dpi)

DEBUG_OCR = False
DEBUG_OCR_MAX_CHARS = 400

# Force LSTM engine, PSM tuned for blocks, and add user words
USER_WORDS = r"C:\Users\timmu\Documents\repos\Factbook Project\fonts\user_words.txt"
OCR_CFG = fr'--oem 3 --psm 6 --user-words "{USER_WORDS}"'

def prep_for_ocr(img_rgba):
    # Upscale for sharper glyphs
    upscale = img_rgba.resize((img_rgba.width*2, img_rgba.height*2), Image.BICUBIC)

    # Convert to grayscale
    gray = upscale.convert("L")

    # Auto contrast
    gray = ImageOps.autocontrast(gray, cutoff=1)

    # Binarize (threshold ~190 works for headers)
    bw = gray.point(lambda p: 255 if p > 190 else 0, mode="1")

    # Denoise
    return bw.convert("L").filter(ImageFilter.MedianFilter(3))

def _ocr_region(image_rgba, x0, y0, x1, y1, note=""):
    """
    OCR a sub-rectangle of the RGBA image; returns trimmed text.
    Ensures bounds are clamped and handles empty regions safely.
    """
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(image_rgba.width, int(x1)); y1 = min(image_rgba.height, int(y1))
    if x1 <= x0 or y1 <= y0:
        return ""
    # Tesseract works best on L or RGB; drop alpha
    region = image_rgba.crop((x0, y0, x1, y1))
    region = prep_for_ocr(region)   # ✅ preprocess (upscale, contrast, binarize)
    try:
        txt = pytesseract.image_to_string(region, config=OCR_CFG)
    except Exception as e:
        txt = f"[OCR ERROR: {e}]"
    txt = txt.strip()
    if len(txt) > DEBUG_OCR_MAX_CHARS:
        txt = txt[:DEBUG_OCR_MAX_CHARS] + " …[truncated]"
    if DEBUG_OCR and note:
        print(f"🔎 OCR {note} [{x0},{y0} → {x1},{y1}]:\n{txt}\n")
    return txt

def _norm(s: str) -> str:
    # normalize whitespace and punctuation; keep words only
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def detect_special_layout(image_rgba, page=None):
    txt = page.get_text("text") if page is not None else pytesseract.image_to_string(image_rgba.convert("RGB"))
    norm = _norm(txt)

    # check longer phrases FIRST so they win
    is_lq_answers  = bool(re.search(r"\bletter quest answers\b", norm))
    is_lq          = bool(re.search(r"\bletter quest\b", norm)) and not is_lq_answers

    is_gg_answers  = bool(re.search(r"\bgrid gauntlet answers\b", norm))
    is_gg          = bool(re.search(r"\bgrid gauntlet\b", norm)) and not is_gg_answers

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

    # Top side
    for i in range(bumps_x + 1):
        t = i / bumps_x
        cx = x + t * w
        cy = y - math.sin(t * math.pi) * radius
        points.append((cx, cy))

    # Right side
    for i in range(bumps_y + 1):
        t = i / bumps_y
        cx = x + w + math.sin(t * math.pi) * radius
        cy = y + t * h
        points.append((cx, cy))

    # Bottom side
    for i in range(bumps_x + 1):
        t = i / bumps_x
        cx = x + w - t * w
        cy = y + h + math.sin(t * math.pi) * radius
        points.append((cx, cy))

    # Left side
    for i in range(bumps_y + 1):
        t = i / bumps_y
        cx = x - math.sin(t * math.pi) * radius
        cy = y + h - t * h
        points.append((cx, cy))

    return points


def visually_fill_transparent_gaps(pdf_path, alpha=0.85, dpi=144):
    doc = fitz.open(pdf_path)
    # page_count = min(len(doc), 63)
    page_count = len(doc)
    has_seen_letter_quest_answers = False
    has_seen_grid_gauntlet_answers = False

    # for page_index in range(page_count - 20, page_count): # Debugging last 20 pages
    # for page_index in range(min(15, page_count)):
    for page_index in range(page_count):
        if page_index == 0:
            print("🚫 Skipping page 1: no gap filling or clouding.")
            continue
        page = doc[page_index]
        print(f"\n📄 Processing page {page_index + 1}/{page_count}")

        # Render at higher resolution
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(alpha=True, matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
        arr = np.array(img)
        height, width = arr.shape[:2]

        # 🔎 DEBUG: OCR preview of whole page
        if DEBUG_OCR:
            page_ocr_preview = pytesseract.image_to_string(img.convert("RGB"), config=OCR_CFG)
            page_ocr_preview = page_ocr_preview.strip()
            if len(page_ocr_preview) > DEBUG_OCR_MAX_CHARS:
                page_ocr_preview = page_ocr_preview[:DEBUG_OCR_MAX_CHARS] + " …[truncated]"
            print(f"📄 OCR preview (page {page_index+1}):\n{page_ocr_preview}\n")

        # --- Compute fixed right-margin band for this page ---
        mx0 = int(width * MARGIN_RIGHT_START_RATIO)
        mx1 = int(width * MARGIN_RIGHT_END_RATIO)

        mx0 = max(0, min(mx0, width - 1))
        mx1 = max(mx0 + 1, min(mx1, width))  # ensure at least 1px wide
        
        # --- Draw guide lines so you can verify the band ---
        if DEBUG_OCR:
            draw = ImageDraw.Draw(img, "RGBA")
            draw.line([(mx0, 0), (mx0, height - 1)], fill=(255, 0, 0, 200), width=GUIDE_LINE_WIDTH)
            draw.line([(mx1, 0), (mx1, height - 1)], fill=(0, 0, 255, 200), width=GUIDE_LINE_WIDTH)

            # --- Horizontal cutoff guide line (green) ---
            draw.line([(0, TOP_SKIP_PX), (width - 1, TOP_SKIP_PX)], fill=(0, 255, 0, 200), width=2)

        # --- DEBUG: OCR the exact margin band used for detection (from TOP_SKIP_PX downward)
        if DEBUG_OCR:
            _ = _ocr_region(img, mx0, TOP_SKIP_PX, mx1, height,
                            note=f"(page {page_index+1}) margin band from TOP_SKIP_PX")

        # Use the fixed right-margin band (mx0:mx1) for row whiteness checks
        bright_rows = []
        stripe = arr[:, mx0:mx1, :3]

        lum = stripe.mean(axis=2)  # H x W
        ink_mask = lum <= INK_MAX_BRIGHTNESS
        bright_mask = lum > BRIGHTNESS_THRESHOLD_ROW

        for y in range(TOP_SKIP_PX, height):   # ✅ scanning starts at y=20, not at the very top
            valid = ~ink_mask[y]
            valid_count = valid.sum()
            if valid_count == 0:
                continue
            bright_frac = (bright_mask[y] & valid).sum() / valid_count
            if bright_frac >= ROW_BRIGHT_MIN_FRAC:
                bright_rows.append(y)

        blocks = []
        for _, g in groupby(enumerate(bright_rows), lambda ix: ix[0] - ix[1]):
            group = list(map(itemgetter(1), g))
            if len(group) > 3:
                start_y = min(group)
                end_y = max(group)

                # 1) Keep using the margin band to CONFIRM a bright block vertically
                block_slice_margin = arr[start_y:end_y + 1, mx0:mx1, :3]   # H x (margin width) x 3
                lum_cols_m = block_slice_margin.mean(axis=2)
                ink_cols_m = lum_cols_m <= INK_MAX_BRIGHTNESS
                bright_cols_mask_m = lum_cols_m > BRIGHTNESS_THRESHOLD_COL

                valid_per_col_m = (~ink_cols_m).sum(axis=0)
                valid_per_col_m = np.where(valid_per_col_m == 0, 1, valid_per_col_m)
                bright_frac_cols_m = (bright_cols_mask_m & ~ink_cols_m).sum(axis=0) / valid_per_col_m

                bright_cols_m = np.where(bright_frac_cols_m >= ROW_BRIGHT_MIN_FRAC)[0]
                has_bright_in_margin = len(bright_cols_m) > 0

                # 2) For the FINAL BOX WIDTH, scan the SAME Y slice across the FULL PAGE width
                block_slice_full = arr[start_y:end_y + 1, :, :3]          # H x W x 3
                lum_cols_f = block_slice_full.mean(axis=2)                # H x W
                ink_cols_f = lum_cols_f <= INK_MAX_BRIGHTNESS
                bright_cols_mask_f = lum_cols_f > BRIGHTNESS_THRESHOLD_COL

                valid_per_col_f = (~ink_cols_f).sum(axis=0)
                valid_per_col_f = np.where(valid_per_col_f == 0, 1, valid_per_col_f)
                bright_frac_cols_f = (bright_cols_mask_f & ~ink_cols_f).sum(axis=0) / valid_per_col_f

                bright_cols_f = np.where(bright_frac_cols_f >= ROW_BRIGHT_MIN_FRAC)[0]

                if has_bright_in_margin and len(bright_cols_f) > 0:
                    # Use the full-page bright band (true width of the white box)
                    x_start = int(np.min(bright_cols_f))
                    x_end   = int(np.max(bright_cols_f))
                elif has_bright_in_margin:
                    # Fallback: at least keep the margin band if full-page scan fails
                    x_start, x_end = mx0, mx1
                else:
                    # No bright evidence in margin → skip this block
                    continue

                # 🔎 DEBUG OCR of detected block regions
                if DEBUG_OCR:
                    # OCR of the margin slice (detector evidence)
                    _ = _ocr_region(
                        img, mx0, start_y, mx1, end_y + 1,
                        note=f"(page {page_index+1}) block margin slice y={start_y}-{end_y}"
                    )
                    # OCR of the full-width box (final box used for patching/cloud)
                    _ = _ocr_region(
                        img, x_start, start_y, x_end + 1, end_y + 1,
                        note=f"(page {page_index+1}) block FULL-WIDTH box y={start_y}-{end_y}"
                    )

                blocks.append((start_y, end_y, x_start, x_end))
                print(f"📦 Page {page_index + 1}: bright block y={start_y}-{end_y}, x={x_start}-{x_end}")

        draw = ImageDraw.Draw(img, "RGBA")
        gap_count = 0

        layout_flags = detect_special_layout(img, page=page)
        is_gauntlet      = layout_flags["grid_gauntlet"]
        is_letter_quest  = layout_flags["letter_quest"]
        is_lqa_page      = layout_flags["letter_quest_answers"]
        is_gga_page      = layout_flags["grid_gauntlet_answers"]
        ocr_text         = layout_flags["raw_text"]

        # Delay updating flags until after rendering
        mark_lqa_seen = False
        mark_gga_seen = False

        # Control flow for cloud/gap logic
        cloud_mode = False
        allow_gap_patch = True
        special_single_cloud = False
        grouped_blocks = []  # ensure defined before grouping tweaks

        if is_lqa_page:
            # LETTER QUEST ANSWERS → cloud only the first box, no gap patch
            cloud_mode = True
            allow_gap_patch = False
            grouped_blocks = [[blocks[0]]] if blocks else []
            mark_lqa_seen = True

        elif is_gga_page:
            # GRID GAUNTLET ANSWERS → cloud only the first box, no gap patch
            cloud_mode = True
            allow_gap_patch = False
            grouped_blocks = [[blocks[0]]] if blocks else []
            mark_gga_seen = True

        elif is_letter_quest or is_gauntlet:
            print("🎯 LQ/GG page (non-answers): clouding ONLY the top block; gap patch OFF")
            # NON-answers LQ/GG pages → cloud only the first box, no gap patch
            cloud_mode = True
            allow_gap_patch = False
            grouped_blocks = [[blocks[0]]] if blocks else []
            special_single_cloud = True

        elif has_seen_letter_quest_answers or has_seen_grid_gauntlet_answers:
            # After answers have appeared, do nothing on later pages
            cloud_mode = False
            allow_gap_patch = False
            grouped_blocks = []

        else:
            # Normal pages
            cloud_mode = True
            allow_gap_patch = True



        # 🔁 Custom block grouping (only if not already set above)
        if not grouped_blocks:
            if special_single_cloud and len(blocks) >= 1:
                grouped_blocks = [[blocks[0]]]
            elif len(blocks) == 1:
                grouped_blocks = [[blocks[0]]]
            elif (is_gauntlet or is_letter_quest) and len(blocks) >= 3:
                grouped_blocks = [blocks[:2], [blocks[-1]]]
            else:
                grouped_blocks = [blocks]



        print(f"🧠 Grid Gauntlet Detected: {is_gauntlet}")
        print(f"📜 Letter Quest Detected: {is_letter_quest}")
        print(f"🔤 OCR Text (page {page_index + 1}):\n{ocr_text}")
        print(f"🔍 Grouped block sets for page {page_index + 1}: {[[(b[0], b[1]) for b in g] for g in grouped_blocks]}")

        has_drawn_first_cloud = False
        # 🔁 Loop through block groups
        for group in grouped_blocks:
            if not group:
                print(f"⚠️ Skipping empty block group on page {page_index + 1}")
                continue  # Skip empty groups entirely

            if len(group) < 2:
                if not cloud_mode:
                    continue
                else:
                    print(f"☁️ Forcing cloud for single block on page {page_index + 1}")

            # ✅ PATCH gaps *within* this group
            if allow_gap_patch:
                max_patches = 2 if page_index == 2 else len(group) - 1
                for i in range(min(len(group) - 1, max_patches)):
                    top = group[i][1]
                    bottom = group[i + 1][0]
                    x_start_common = max(b[2] for b in group)
                    x_end_common = min(b[3] for b in group)

                    gap_height = (bottom - top) - 1
                    gap_width  = (x_end_common - x_start_common)

                    # Always patch, regardless of size
                    draw.rectangle(
                        [(x_start_common, top + 1), (x_end_common, bottom - 1)],
                        fill=(255, 255, 255, int(alpha * 255))
                    )
                    print(f"🩹 Page {page_index + 1}: hard-patched y={top + 1}-{bottom - 1} (h={gap_height}, w={gap_width})")
                    gap_count += 1



            # ✅ CLOUD for this group
            if cloud_mode:
                # (unchanged — keep this guard to only draw the first cloud on LQ/GG pages)
                if has_drawn_first_cloud and (is_letter_quest or is_gauntlet):
                    print(f"⛔ Skipping extra cloud for LQ/GG page {page_index + 1}")
                    continue

                print(f"🌩 Drawing cloud for group on page {page_index + 1}: "
                    f"y={group[0][0]}–{group[-1][1]}, x={max(b[2] for b in group)}–{min(b[3] for b in group)}")


                # ✅ CLOUD for this group
                cloud_top = group[0][0]
                cloud_bottom = group[-1][1]
                cloud_x_start = max(b[2] for b in group)
                cloud_x_end = min(b[3] for b in group)

                x0, y0 = cloud_x_start - 25, cloud_top - 25
                w = (cloud_x_end - cloud_x_start) + 50
                h = (cloud_bottom - cloud_top) + 50

                # Upscaling factor
                SCALE = 4
                highres_w = width * SCALE
                highres_h = height * SCALE

                # High-res overlay
                cloud_hr = Image.new("RGBA", (highres_w, highres_h), (0, 0, 0, 0))
                cloud_draw = ImageDraw.Draw(cloud_hr)

                # Scale all coordinates
                x0_hr = x0 * SCALE
                y0_hr = y0 * SCALE
                w_hr = w * SCALE
                h_hr = h * SCALE
                cloud_x_start_hr = cloud_x_start * SCALE
                cloud_x_end_hr = cloud_x_end * SCALE
                cloud_top_hr = cloud_top * SCALE
                cloud_bottom_hr = cloud_bottom * SCALE

                # Generate path
                path_points = generate_soft_cloud_path(
                    x0_hr, y0_hr, w_hr, h_hr, bumps_x=10, bumps_y=8, radius=18 * SCALE
                )

                # Fill outside, punch hole in center
                cloud_draw.polygon(path_points, fill=(255, 255, 255, int(alpha * 255)))
                cloud_draw.rectangle(
                    [(cloud_x_start_hr, cloud_top_hr), (cloud_x_end_hr, cloud_bottom_hr)],
                    fill=(0, 0, 0, 0)
                )

                # Transparent semicircles
                semicircle_path = generate_top_semicircle_cutouts(
                    cloud_x_start_hr, cloud_top_hr, cloud_x_end_hr, cloud_top_hr,
                    num_bumps=20, radius=12 * SCALE
                )
                cloud_draw.polygon(semicircle_path, fill=(0, 0, 0, 0))

                # Outline
                cloud_draw.line(path_points + [path_points[0]], fill=(0, 0, 0, 255), width=5 * SCALE, joint="curve")

                # Downscale and merge
                cloud_final = cloud_hr.resize((width, height), resample=Image.LANCZOS)
                img = Image.alpha_composite(img, cloud_final)

                has_drawn_first_cloud = True 






        if gap_count == 0:
            print(f"✅ Page {page_index + 1}: no gaps patched.")
        else:
            print(f"✅ Page {page_index + 1}: {gap_count} gaps patched.")

        # Insert image overlay onto page
        out_bytes = io.BytesIO()
        img.save(out_bytes, format="PNG")
        page.insert_image(page.rect, stream=out_bytes.getvalue(), overlay=True)

        # ✅ Now mark the current page as seen (but only after rendering)
        if mark_lqa_seen:
            has_seen_letter_quest_answers = True
        if mark_gga_seen:
            has_seen_grid_gauntlet_answers = True

    # Save uncompressed version (optional)
    output_path = pdf_path.replace(".pdf", "_gapfilled.pdf")
    doc.save(output_path)

    # Save optimized compressed version
    compressed_path = pdf_path.replace(".pdf", "_gapfilled_compressed.pdf")
    doc.save(compressed_path, deflate=True, garbage=4, clean=True)

    print(f"💾 Uncompressed saved to: {output_path}")
    print(f"📦 Compressed saved to:   {compressed_path}")

    doc.close()



# 🔧 Replace this with your test file path
visually_fill_transparent_gaps(
    r"C:\Users\timmu\Documents\repos\Factbook Project\books\fresh_test.pdf",
    alpha=0.85
)
