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

BRIGHTNESS_THRESHOLD_ROW = 200
BRIGHTNESS_THRESHOLD_BLOCK = 220
BRIGHTNESS_THRESHOLD_COL = 200


def detect_special_layout(image: Image.Image):
    text = pytesseract.image_to_string(image)
    text_lower = text.lower()

    # Split text into lines to handle line breaks and OCR misalignments
    lines = [line.strip() for line in text_lower.splitlines() if line.strip()]

    is_grid_gauntlet = any("grid gauntlet" in line for line in lines)

    # Fuzzy match for letter quest
    is_letter_quest = any(
        difflib.get_close_matches(line, ["letter quest"], n=1, cutoff=0.75)
        for line in lines
    )

    return {
        "grid_gauntlet": is_grid_gauntlet,
        "letter_quest": is_letter_quest,
        "raw_text": text
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

    # for page_index in range(page_count - 15, page_count): # Debugging last 15 pages
    for page_index in range(page_count):
        page = doc[page_index]
        print(f"\n📄 Processing page {page_index + 1}/{page_count}")

        # Render at higher resolution
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(alpha=True, matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
        arr = np.array(img)
        height, width = arr.shape[:2]

        stripe_width = int(width * 0.02)
        best_x = None
        max_bright_rows = -1
        # candidates = [round(x / 100, 2) for x in range(95, 59, -1)]
        candidates = [0.85]

        for ratio in candidates:
            x_start = int(width * ratio)
            stripe = arr[:, x_start:x_start + stripe_width, :3]
            row_brightness = np.mean(stripe, axis=(1, 2))
            bright_rows = np.sum(row_brightness > BRIGHTNESS_THRESHOLD_BLOCK)
            if bright_rows > max_bright_rows:
                max_bright_rows = bright_rows
                best_x = x_start

        probe_x_start = best_x
        bright_rows = []
        for y in range(height):
            brightness = np.mean(arr[y, probe_x_start:probe_x_start + stripe_width, :3])
            if brightness > BRIGHTNESS_THRESHOLD_ROW:
                bright_rows.append(y)

        blocks = []
        for _, g in groupby(enumerate(bright_rows), lambda ix: ix[0] - ix[1]):
            group = list(map(itemgetter(1), g))
            if len(group) > 3:
                start_y = min(group)
                end_y = max(group)

                block_slice = arr[start_y:end_y + 1, :, :3]
                avg_cols = np.mean(block_slice, axis=(0, 2))
                bright_cols = np.where(avg_cols > BRIGHTNESS_THRESHOLD_COL)[0]

                if len(bright_cols) > 0:
                    x_start = int(np.min(bright_cols))
                    x_end = int(np.max(bright_cols))
                else:
                    x_start, x_end = 0, width

                blocks.append((start_y, end_y, x_start, x_end))
                print(f"📦 Page {page_index + 1}: bright block y={start_y}-{end_y}, x={x_start}-{x_end}")

        draw = ImageDraw.Draw(img, "RGBA")
        gap_count = 0

        layout_flags = detect_special_layout(img)
        is_gauntlet = layout_flags["grid_gauntlet"]
        is_letter_quest = layout_flags["letter_quest"]
        ocr_text = layout_flags["raw_text"]
        text_lower = ocr_text.lower()

        # Page-specific detection
        is_lqa_page = "letter quest answers" in text_lower
        is_gga_page = "grid gauntlet answers" in text_lower

        # Delay updating flags until after rendering
        mark_lqa_seen = False
        mark_gga_seen = False

        # Control flow for cloud/gap logic
        cloud_mode = False
        allow_gap_patch = True
        special_single_cloud = False

        if is_lqa_page:
            cloud_mode = True
            allow_gap_patch = False
            special_single_cloud = True
            mark_lqa_seen = True
        elif is_gga_page:
            cloud_mode = True
            allow_gap_patch = False
            special_single_cloud = True
            mark_gga_seen = True
        elif has_seen_letter_quest_answers and not has_seen_grid_gauntlet_answers:
            cloud_mode = False
            allow_gap_patch = False
        elif has_seen_letter_quest_answers and has_seen_grid_gauntlet_answers:
            cloud_mode = False
            allow_gap_patch = False
        else:
            cloud_mode = True  # ✅ Enable clouds by default before LQA
            allow_gap_patch = True

        print(f"🧠 Grid Gauntlet Detected: {is_gauntlet}")
        print(f"📜 Letter Quest Detected: {is_letter_quest}")
        print(f"🔤 OCR Text (page {page_index + 1}):\n{text_lower}")

        # 🔁 Custom block grouping
        if special_single_cloud and len(blocks) >= 1:
            grouped_blocks = [[blocks[0]]]  # Only first block gets a cloud
        elif (is_gauntlet or is_letter_quest) and len(blocks) >= 3:
            grouped_blocks = [blocks[:2], [blocks[-1]]]
        else:
            grouped_blocks = [blocks]

        print(f"🧠 Grid Gauntlet Detected: {is_gauntlet}")
        print(f"📜 Letter Quest Detected: {is_letter_quest}")
        print(f"🔤 OCR Text (page {page_index + 1}):\n{ocr_text}")
        print(f"🔍 Grouped block sets for page {page_index + 1}: {[[(b[0], b[1]) for b in g] for g in grouped_blocks]}")

        # 🔁 Loop through block groups
        for group in grouped_blocks:
            if len(group) < 2 and not special_single_cloud:
                continue

            # ✅ PATCH gaps *within* this group
            if allow_gap_patch:
                for i in range(len(group) - 1):
                    top = group[i][1]
                    bottom = group[i + 1][0]
                    x_start_common = max(b[2] for b in group)
                    x_end_common = min(b[3] for b in group)

                    if bottom > top and (x_end_common - x_start_common) > 10:
                        draw.rectangle(
                            [(x_start_common, top + 1), (x_end_common, bottom - 1)],
                            fill=(255, 255, 255, int(alpha * 255))
                        )
                        print(f"🩹 Page {page_index + 1}: hard-patched y={top + 1}-{bottom - 1}")
                        gap_count += 1


            # ✅ CLOUD for this group
            if cloud_mode:
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
