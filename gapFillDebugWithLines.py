import fitz
from PIL import Image, ImageDraw
import numpy as np
import io
from itertools import groupby
from operator import itemgetter

def visually_fill_transparent_gaps(pdf_path, alpha=0.65, dpi=144):
    doc = fitz.open(pdf_path)
    page_count = min(len(doc), 10)

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
        candidates = [round(x / 100, 2) for x in range(85, 84, -1)]



        for ratio in candidates:
            x_start = int(width * ratio)
            stripe = arr[:, x_start:x_start + stripe_width, :3]
            row_brightness = np.mean(stripe, axis=(1, 2))
            bright_rows = np.sum(row_brightness > 180)
            if bright_rows > max_bright_rows:
                max_bright_rows = bright_rows
                best_x = x_start

        probe_x_start = best_x
        bright_rows = []
        for y in range(height):
            brightness = np.mean(arr[y, probe_x_start:probe_x_start + stripe_width, :3])
            if brightness > 160:
                bright_rows.append(y)

        blocks = []
        for _, g in groupby(enumerate(bright_rows), lambda ix: ix[0] - ix[1]):
            group = list(map(itemgetter(1), g))
            if len(group) > 100:
                start_y = min(group)
                end_y = max(group)

                block_slice = arr[start_y:end_y + 1, :, :3]
                avg_cols = np.mean(block_slice, axis=(0, 2))
                bright_cols = np.where(avg_cols > 160)[0]

                if len(bright_cols) > 0:
                    x_start = int(np.min(bright_cols))
                    x_end = int(np.max(bright_cols))
                else:
                    x_start, x_end = 0, width

                blocks.append((start_y, end_y, x_start, x_end))
                print(f"📦 Page {page_index + 1}: bright block y={start_y}-{end_y}, x={x_start}-{x_end}")

        draw = ImageDraw.Draw(img, "RGBA")
        gap_count = 0

        for i in range(len(blocks) - 1):
            top = blocks[i][1] + 1
            bottom = blocks[i + 1][0] - 1
            x_start = min(blocks[i][2], blocks[i + 1][2])
            x_end = max(blocks[i][3], blocks[i + 1][3])

            if bottom > top and (x_end - x_start) > 10:
                # Deterministically fill the full vertical gap between bright blocks
                draw.rectangle(
                    [(x_start, top), (x_end, bottom)],
                    fill=(255, 255, 255, int(alpha * 255))
                )
                draw.line([(0, top), (width, top)], fill=(0, 255, 0, 255), width=2)
                draw.line([(0, bottom), (width, bottom)], fill=(0, 255, 0, 255), width=2)
                print(f"🩹 Page {page_index + 1}: hard-patched y={top}-{bottom}")
                gap_count += 1




        if gap_count == 0:
            print(f"✅ Page {page_index + 1}: no gaps patched.")
        else:
            print(f"✅ Page {page_index + 1}: {gap_count} gaps patched.")

        # Draw probe and block debug lines
        draw.line([(probe_x_start, 0), (probe_x_start, height)], fill=(255, 0, 255, 255), width=2)  # Magenta stripe
        for start_y, end_y, _, _ in blocks:
            draw.line([(0, start_y), (width, start_y)], fill=(0, 0, 255, 255), width=2)  # Blue = block start
            draw.line([(0, end_y), (width, end_y)], fill=(255, 0, 0, 255), width=2)      # Red = block end

        # Insert image overlay onto page
        out_bytes = io.BytesIO()
        img.save(out_bytes, format="PNG")
        page.insert_image(page.rect, stream=out_bytes.getvalue(), overlay=True)

    # Save to new file
    output_path = pdf_path.replace(".pdf", "_gapfilled.pdf")
    doc.save(output_path)
    doc.close()
    print(f"\n🎉 Saved patched PDF to: {output_path}")


# 🔧 Replace this with your test file path
visually_fill_transparent_gaps(
    r"C:\Personal\factBook\books\fresh_test.pdf",
    alpha=0.65
)
