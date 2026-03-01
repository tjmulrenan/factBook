# build_hardcover.py

import os
import re
import sys
from io import BytesIO
from math import ceil
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import COVER_DIR, FONTS_DIR, FINAL_OUTPUT_DIR, LEAP_YEAR

# ===== PATHS =====
INPUT_DIR  = str(COVER_DIR / "complete")
OUTPUT_DIR = str(COVER_DIR / "hardcover")
BACK_IMG   = str(COVER_DIR / "back.png")
SPINE_IMG  = str(COVER_DIR / "spine.png")
SPINE_TITLE_IMG = str(COVER_DIR / "what_happened_on.png")
SPINE_FONT_FILE = str(FONTS_DIR / "Domine-Bold.ttf")
SPINE_TEXT_COLOR = (0, 0, 0)   # black (0–1 RGB). Use (1,1,1) for white on dark spine
SPINE_ROTATE_DEG = 270          # 90 or 270 depending on reading direction
SPINE_TEXT_MARGIN_IN = 0.03   # inset inside TRUE spine

# ===== BOOK / LAYOUT =====
TRIM_W_IN, TRIM_H_IN = 6.0, 9.0      # interior trim size
DPI = 300
MARGIN_IN = 0.50                      # margin for page 1 image placement
FIT_MODE = "contain"                  # "contain" (no crop) or "cover" (fill, may crop)
VALID_EXT = {".png", ".jpg", ".jpeg"}
GENERATE_INTERIOR = False

# draw guide lines at the true spine edges (between spine and panels)
DRAW_SPINE_EDGE_LINES = True
SPINE_EDGE_LINE_WIDTH_PT = 1.0   # 0.5–1.0 is subtle; increase if you want bolder
SPINE_EDGE_LINE_COLOR = (0, 0, 0)  # RGB 0–1; black

# ===== CONSTANTS (always color paper for spine calc) =====
PT = 72.0                             # PDF points per inch
SPINE_PER_PAGE = {"white":0.002252, "cream":0.0025, "color":0.002347}
PAPER = "color"                       # fixed

# --- HARDCOVER (6x9) spec helper to mirror KDP calculator ---
# spine uses slope + intercept (not per-page only)
HC_SPINE_SLOPE = 0.002347         # in/page
HC_SPINE_INTERCEPT = 0.18852      # in

HC_WRAP  = 0.5905                 # each side (gives 10.417" total height)
HC_HINGE = 0.394                  # each side of spine

HC_FRONT_W_ADD = HC_HINGE / 2.0   # 0.197"
HC_FRONT_H_ADD = 0.236            # 9.236" front height


def cover_specs_hardcover(pages, trim_w=6.0, trim_h=9.0, dpi=300, spine_override=None):
    # auto spine from slope + intercept (KDP hardcover 6×9 premium color)
    spine_auto = HC_SPINE_SLOPE * pages + HC_SPINE_INTERCEPT
    spine = spine_override if spine_override is not None else spine_auto

    front_w = trim_w + HC_FRONT_W_ADD
    front_h = trim_h + HC_FRONT_H_ADD
    full_w  = 2 * front_w + spine + 2 * HC_WRAP
    full_h  = front_h + 2 * HC_WRAP

    def to_px(inches): return int(round(inches * dpi))
    return {
        "binding": "hardcover",
        "trim_w_in": trim_w, "trim_h_in": trim_h,
        "pages": pages,
        "front_w_in": front_w, "front_h_in": front_h,
        "spine_in": spine, "spine_px": to_px(spine),
        "spine_auto_in": spine_auto, "spine_auto_px": to_px(spine_auto),
        "wrap_in": HC_WRAP, "hinge_in": HC_HINGE,
        "full_w_in": full_w, "full_h_in": full_h,
        "full_w_px": to_px(full_w), "full_h_px": to_px(full_h),
    }


def even_pages(p: int) -> int:
    return p if p % 2 == 0 else p + 1


def px(inches: float, dpi: int) -> int:
    return int(round(inches * dpi))


def cover_specs(pages: int):
    bleed = 0.125
    spine_in = SPINE_PER_PAGE[PAPER] * pages
    cov_w_in = (2 * TRIM_W_IN) + spine_in + (2 * bleed)
    cov_h_in = TRIM_H_IN + (2 * bleed)
    return spine_in, cov_w_in, cov_h_in


def list_images():
    items = []
    for f in os.listdir(INPUT_DIR):  # keep directory order "as appears"
        full = os.path.join(INPUT_DIR, f)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in VALID_EXT:
            items.append(f)
    return items


def place_image(page, img_path, margin_in: float, fit_mode: str):
    box = page.rect
    m = margin_in * PT
    inner = fitz.Rect(box.x0 + m, box.y0 + m, box.x1 - m, box.y1 - m)

    # new exact-fill path: crops to inner aspect, then fills exactly
    if fit_mode == "fillcrop":
        insert_image_fill_rect_with_crop(page, inner, img_path, DPI)
        return

    with Image.open(img_path) as im:
        wpx, hpx = im.size

    scale = max(inner.width / wpx, inner.height / hpx) if fit_mode == "cover" else \
            min(inner.width / wpx, inner.height / hpx)

    new_w, new_h = wpx * scale, hpx * scale
    x0 = inner.x0 + (inner.width - new_w) / 2
    y0 = inner.y0 + (inner.height - new_h) / 2
    rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)
    page.insert_image(rect, filename=img_path)  # embeds at source quality


def insert_image_fill_rect_with_crop(page, rect: fitz.Rect, img_path: str, dpi: int):
    """Crop the image to match the rect aspect ratio, then resize to exact pixel size and place without distortion."""
    with Image.open(img_path) as im:
        im = im.convert("RGBA")
        target_w_in = (rect.width  / PT)
        target_h_in = (rect.height / PT)
        target_w_px = max(1, int(round(target_w_in * dpi)))
        target_h_px = max(1, int(round(target_h_in * dpi)))
        target_aspect = target_w_px / target_h_px

        w, h = im.size
        src_aspect = w / h
        if src_aspect > target_aspect:
            # too wide → crop left/right
            new_w = int(round(h * target_aspect))
            left = max(0, (w - new_w) // 2)
            im = im.crop((left, 0, left + new_w, h))
        elif src_aspect < target_aspect:
            # too tall → crop top/bottom
            new_h = int(round(w / target_aspect))
            top = max(0, (h - new_h) // 2)
            im = im.crop((0, top, w, top + new_h))

        im = im.resize((target_w_px, target_h_px), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, format="PNG")
        page.insert_image(rect, stream=buf.getvalue(), keep_proportion=False)


def insert_rotated_image_fit(page, rect: fitz.Rect, img_path: str, deg: int = 90):
    with Image.open(img_path) as im:
        im = im.convert("RGBA").rotate(deg, expand=True)  # rotate CCW by 'deg'
        buf = BytesIO()
        im.save(buf, format="PNG")
        page.insert_image(rect, stream=buf.getvalue(), keep_proportion=True)


def insert_rotated_text_pil(page, rect: fitz.Rect, text: str, font_path: str,
                            rotate_deg: int = 270, color=(1,1,1),
                            dpi: int = 300, thickness_frac: float = 0.88):
    """Render text with PIL, add padding to avoid clip, rotate, scale-to-fit band, insert as image."""
    if not text:
        return

    # band (points) -> pixels
    w_px = max(1, int(round(rect.width  / PT * dpi)))
    h_px = max(1, int(round(rect.height / PT * dpi)))

    # how thick the letters should be relative to the band’s short side (post-rotation)
    target_px = max(1, int(round((w_px if rotate_deg in (90, 270) else h_px) * thickness_frac)))

    # build font roughly at that thickness
    font = ImageFont.truetype(font_path, size=target_px)

    # measure unrotated text
    meas = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    drw = ImageDraw.Draw(meas)
    bbox = drw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # --- safety padding so edges don't get cropped after rotation ---
    PAD = ceil(target_px * 0.18)   # ~18% of thickness; tweak 0.12–0.22 if needed
    canvas_w = text_w + PAD * 2
    canvas_h = text_h + PAD * 2

    # render unrotated text onto padded canvas
    text_im = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    drw = ImageDraw.Draw(text_im)
    col = tuple(int(round(c * 255)) for c in color) + (255,)
    drw.text((PAD, PAD), text, font=font, fill=col)

    # rotate (expand) and scale to fit with a tiny margin
    text_im = text_im.rotate(rotate_deg, expand=True)
    FIT_MARGIN = 0.98  # keep 2% breathing room inside the band
    scale = min((w_px * FIT_MARGIN) / text_im.width,
                (h_px * FIT_MARGIN) / text_im.height, 1.0)
    if scale < 1.0:
        new_size = (max(1, int(text_im.width * scale)),
                    max(1, int(text_im.height * scale)))
        text_im = text_im.resize(new_size, Image.LANCZOS)

    # center in band and insert
    base = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
    ox = (w_px - text_im.width) // 2
    oy = (h_px - text_im.height) // 2
    base.paste(text_im, (ox, oy), text_im)

    buf = BytesIO()
    base.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue(), keep_proportion=False)


def _fit_font_to_width(text: str, max_w_pt: float, fontfile: str,
                       min_pt=6, max_pt=36, pad=0.92) -> float:
    """Return a font size that fits 'text' into max_w_pt (single line), using a Font object for width."""
    if not text:
        return min_pt
    # Build a font and measure width at 1pt – works across PyMuPDF versions
    try:
        fnt = fitz.Font(fontfile=fontfile)   # newer keyword
    except TypeError:
        fnt = fitz.Font(filename=fontfile)   # older keyword
    w_at_1 = fnt.text_length(text, 1.0)
    if w_at_1 <= 0:
        return min_pt
    size = (max_w_pt * pad) / w_at_1
    return max(min_pt, min(max_pt, size))


def make_pdf(img_path: str, out_path: str, total_pages: int):
    doc = fitz.open()
    page_w, page_h = TRIM_W_IN * PT, TRIM_H_IN * PT

    # page 1 with image
    first = doc.new_page(width=page_w, height=page_h)
    place_image(first, img_path, MARGIN_IN, FIT_MODE)

    # remaining blank
    for _ in range(total_pages - 1):
        doc.new_page(width=page_w, height=page_h)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path, garbage=4, clean=True)
    doc.close()


def make_cover_spread(img_path: str, out_path: str, pages: int,
                      safe_margin_in: float = 0.0,
                      place_mode: str = "trim",
                      bg=(1, 1, 1),
                      spine_override=None,
                      back_img_path: str = None,
                      back_safe_margin_in: float = None,
                      back_place_mode: str = None,
                      spine_img_path: str = None,
                      spine_title_img_path: str = None,
                      spine_date_text: str = "",
                      spine_author_text: str = ""):
    """
    Build a KDP hardcover spread (case laminate) PDF at the exact size.
    - Background fills the whole bleed/wrap.
    - Front panel gets the selected image (right side).
    - Back panel optionally gets a back image (left side).

    place_mode/back_place_mode:
      "trim"  -> place a 6x9 image aligned to the OUTER fore-edge of that panel.
      "panel" -> fit the entire panel area (front/back panel size).
    """
    hc = cover_specs_hardcover(pages, TRIM_W_IN, TRIM_H_IN, DPI,
                               spine_override=spine_override)

    # Create the spread page
    doc = fitz.open()
    W = hc["full_w_in"] * PT
    H = hc["full_h_in"] * PT
    page = doc.new_page(width=W, height=H)

    # Fill background to edge (bleed/wrap)
    page.draw_rect(page.rect, fill=bg, color=None)

    # Panel rectangles in inches → points
    def IN(x): return x * PT

    # Back panel (left side)
    x0_back_in = HC_WRAP
    x1_back_in = x0_back_in + hc["front_w_in"]
    y0_back_in = HC_WRAP
    y1_back_in = y0_back_in + hc["front_h_in"]
    back_panel = fitz.Rect(IN(x0_back_in), IN(y0_back_in),
                           IN(x1_back_in), IN(y1_back_in))

    # Front panel (right side)
    x0_front_in = HC_WRAP + hc["front_w_in"] + hc["spine_in"]
    x1_front_in = x0_front_in + hc["front_w_in"]
    y0_front_in = HC_WRAP
    y1_front_in = y0_front_in + hc["front_h_in"]
    front_panel = fitz.Rect(IN(x0_front_in), IN(y0_front_in),
                            IN(x1_front_in), IN(y1_front_in))

    # Spine panel widened to fill the whole visual gap (spine + 0.197" on each side)
    x0_spine_in = HC_WRAP + hc["front_w_in"] - HC_FRONT_W_ADD
    x1_spine_in = x0_spine_in + hc["spine_in"] + 2 * HC_FRONT_W_ADD
    y0_spine_in = HC_WRAP
    y1_spine_in = y0_spine_in + hc["front_h_in"]
    spine_panel = fitz.Rect(IN(x0_spine_in), IN(y0_spine_in),
                            IN(x1_spine_in), IN(y1_spine_in))

    # TRUE spine (no hinge) – keep text inside this
    x0_true_in = HC_WRAP + hc["front_w_in"]
    x1_true_in = x0_true_in + hc["spine_in"]
    true_spine = fitz.Rect(IN(x0_true_in), IN(HC_WRAP),
                        IN(x1_true_in), IN(HC_WRAP + hc["front_h_in"]))

    # precompute inset rect + bands (title / date / author)
    margin_pt = SPINE_TEXT_MARGIN_IN * PT
    r = fitz.Rect(true_spine.x0 + margin_pt, true_spine.y0 + margin_pt,
                true_spine.x1 - margin_pt, true_spine.y1 - margin_pt)
    h = r.height
    title_band  = fitz.Rect(r.x0, r.y0 + h*0.04, r.x1, r.y0 + h * 0.40)
    date_band   = fitz.Rect(r.x0, r.y0 + h*0.40, r.x1, r.y0 + h * 0.80)
    author_band = fitz.Rect(r.x0, r.y0 + h*0.71, r.x1, r.y0 + h*0.96)
    # ----- helper to compute dest rects -----
    def dest_for_panel(panel_rect, which: str,
                       mode: str, safe: float):
        # which: "front" or "back" (affects which edge is the "outer" fore-edge)
        if mode == "panel":
            return fitz.Rect(panel_rect.x0 + IN(safe),
                             panel_rect.y0 + IN(safe),
                             panel_rect.x1 - IN(safe),
                             panel_rect.y1 - IN(safe))
        # "trim": place exactly 6x9 aligned to the panel's outer fore-edge
        iw, ih = TRIM_W_IN - 2*safe, TRIM_H_IN - 2*safe
        if which == "front":
            # outer edge is right side
            x1 = panel_rect.x1 - IN(safe)
            x0 = x1 - IN(iw)
        else:
            # outer edge is left side
            x0 = panel_rect.x0 + IN(safe)
            x1 = x0 + IN(iw)
        y0 = panel_rect.y0 + (panel_rect.height - IN(ih)) / 2
        y1 = y0 + IN(ih)
        return fitz.Rect(x0, y0, x1, y1)

    # ----- FRONT image -----
    dest_front = dest_for_panel(
        front_panel,
        "front",
        place_mode,
        safe_margin_in
    )
    page.insert_image(dest_front, filename=img_path, keep_proportion=True)

    # ----- BACK image (optional) -----
    if back_img_path:
        b_mode = back_place_mode or place_mode
        b_safe = back_safe_margin_in if back_safe_margin_in is not None else safe_margin_in
        dest_back = dest_for_panel(
            back_panel,
            "back",
            b_mode,
            b_safe
        )
        page.insert_image(dest_back, filename=back_img_path, keep_proportion=True)

    # ----- SPINE image (optional, exact fit with crop) -----
    if spine_img_path:
        insert_image_fill_rect_with_crop(page, spine_panel, spine_img_path, DPI)

    # separators exactly where panel images meet the spine image
    line_w_pt = 3.0        # thickness in points
    line_col  = (0, 0, 0)  # black

    y_top    = IN(HC_WRAP)
    y_bottom = IN(HC_WRAP + hc["front_h_in"])

    # left separator: back image right edge (only if back image exists)
    if back_img_path:
        x_left_join = dest_back.x1
        page.draw_line((x_left_join, y_top), (x_left_join, y_bottom),
                       color=line_col, width=line_w_pt)

    # right separator: front image left edge
    x_right_join = dest_front.x0
    page.draw_line((x_right_join, y_top), (x_right_join, y_bottom),
                color=line_col, width=line_w_pt)

    # ----- SPINE TITLE IMAGE -----
    if spine_title_img_path and os.path.exists(spine_title_img_path):
        insert_rotated_image_fit(page, title_band, spine_title_img_path, deg=SPINE_ROTATE_DEG)

    # ----- SPINE DATE / AUTHOR (Domine-Bold via PIL, rotated) -----
    insert_rotated_text_pil(page, date_band,   spine_date_text,   SPINE_FONT_FILE,
                            rotate_deg=SPINE_ROTATE_DEG, color=SPINE_TEXT_COLOR,
                            dpi=DPI, thickness_frac=0.90)

    # make author smaller by reducing thickness_frac
    insert_rotated_text_pil(page, author_band, spine_author_text, SPINE_FONT_FILE,
                            rotate_deg=SPINE_ROTATE_DEG, color=SPINE_TEXT_COLOR,
                            dpi=DPI, thickness_frac=0.55)

    # Save
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc.save(out_path, garbage=4, clean=True)
    doc.close()


def main():
    files = list_images()
    if not files:
        print("No PNG/JPG covers found in:", INPUT_DIR)
        sys.exit(1)

    print("\nSelect a cover by number:\n")
    for i, f in enumerate(files, 1):
        print(f"{i:3d}. {f}")

    try:
        idx = int(input("\nEnter number: ").strip())
        assert 1 <= idx <= len(files)
    except Exception:
        print("Invalid selection.")
        sys.exit(1)

    chosen = files[idx - 1]
    img_path = os.path.join(INPUT_DIR, chosen)
    stem, _ = os.path.splitext(chosen)
    out_path = os.path.join(OUTPUT_DIR, f"{stem}.pdf")
    cover_pdf = os.path.join(OUTPUT_DIR, f"{stem}_COVER_SPREAD.pdf")

    # --- loop until page count + specs look good ---
    spine_override_in = None  # inches (float) or None

    while True:
        try:
            pages_in = int(input("Enter total interior pages (e.g., 108): ").strip())
        except Exception:
            print("Enter a valid integer page count.")
            continue

        pages = even_pages(pages_in)
        if pages != pages_in:
            print(f"⚠ Page count must be even. Using {pages} instead of {pages_in}.")

        # inner command loop so you can tweak spine/pages and re-preview
        while True:
            hc = cover_specs_hardcover(pages, TRIM_W_IN, TRIM_H_IN, DPI,
                                       spine_override=spine_override_in)

            # Preview + confirm
            print("\n=== SPEC PREVIEW — HARDCOVER (case laminate) ===")
            print(f"Chosen file      : {chosen}")
            print(f"Interior trim    : {TRIM_W_IN:.3f} in × {TRIM_H_IN:.3f} in  "
                  f"({px(TRIM_W_IN,DPI)} × {px(TRIM_H_IN,DPI)} px @ {DPI} DPI)")
            if spine_override_in is None:
                print(f"Spine (cover)    : {hc['spine_in']:.3f} in  ({hc['spine_px']} px)")
            else:
                print(f"Spine (cover)    : {hc['spine_in']:.3f} in  ({hc['spine_px']} px)  [OVERRIDE; auto={hc['spine_auto_in']:.3f}\"]")
            print(f"Full cover       : {hc['full_w_in']:.3f} in × {hc['full_h_in']:.3f} in  "
                  f"({hc['full_w_px']} × {hc['full_h_px']} px)")
            print(f"Front panel      : {hc['front_w_in']:.3f} in × {hc['front_h_in']:.3f} in")
            print(f"Image placement  : margin {MARGIN_IN:.2f}\" | fit={FIT_MODE}")
            print(f"Cover spread out : {cover_pdf}")
            if GENERATE_INTERIOR:
                print(f"Interior out     : {out_path}")
            print("Commands: [y] proceed  [p] change pages  [s] set spine  [r] reset spine  [n] abort")
            cmd = input("> ").strip().lower()

            if cmd == "y":
                break
            if cmd == "n":
                print("Aborted.")
                return
            if cmd == "p":
                # break inner loop to re-ask page count
                break
            if cmd == "r":
                spine_override_in = None
                continue
            if cmd == "s":
                raw = input("Enter spine width (e.g., 0.541 or 162px): ").strip().lower()
                try:
                    if raw.endswith("px"):
                        px_val = float(raw[:-2])
                        spine_override_in = px_val / DPI
                    else:
                        spine_override_in = float(raw)
                    # sanity bounds (optional)
                    if not (0.05 <= spine_override_in <= 3.0):
                        print("Unusual spine width; keeping it but double-check.")
                except Exception:
                    print("Could not parse that spine value.")
                continue

            print("Unknown command.")

        if cmd == "y":
            break
        # if cmd == "p": loop back to re-enter page count

    # === After confirming, build PDFs ===
    if GENERATE_INTERIOR:
        interior_pdf = out_path
        print(f"\n→ Writing INTERIOR PDF: {interior_pdf}")
        make_pdf(img_path, interior_pdf, pages)

    # cover spread (full jacket)
    print(f"→ Writing COVER SPREAD PDF: {cover_pdf}")
    # place 6×9 art on the front panel; white background to edge
    back_path  = BACK_IMG  if os.path.exists(BACK_IMG)  else None
    spine_path = SPINE_IMG if os.path.exists(SPINE_IMG) else None
    title_img_path = SPINE_TITLE_IMG if os.path.exists(SPINE_TITLE_IMG) else None

    # derive "Month Day" from filename (e.g., March_29_*.png → "March 29")
    import re
    m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)[ _-]?(\d{1,2})',
                stem, re.IGNORECASE)
    spine_date_text = (f"{m.group(1).title()} {int(m.group(2))}" if m else "").upper()
    spine_author_text = "By TJ Mulrenan"

    make_cover_spread(
        img_path,
        cover_pdf,
        pages,

        safe_margin_in=0.0,
        place_mode="trim",          # or "panel" if your art is full-bleed per panel
        bg=(1, 1, 1),
        spine_override=spine_override_in,
        back_img_path=back_path,
        back_place_mode="trim",     # or "panel"
        back_safe_margin_in=0.0,
        spine_img_path=spine_path,
        spine_title_img_path=title_img_path,
        spine_date_text=spine_date_text,
        spine_author_text=spine_author_text
    )

    print("\n✅ Done.")
    if GENERATE_INTERIOR:
        print(f"Interior: {interior_pdf}")
    print(f"Cover:    {cover_pdf}")

if __name__ == "__main__":
    main()
