# make_cover_paperback.py
# pip install pymupdf pillow

import os, sys
import fitz  # PyMuPDF
from PIL import Image

# ===== PATHS =====
INPUT_DIR  = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\complete"
OUTPUT_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\paperback"
BACK_IMG   = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\back.png"
SPINE_IMG  = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\spine.png"
SPINE_TITLE_IMG = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\what_happened_on.png"
SPINE_FONT_FILE = r"C:\Users\timmu\Documents\repos\Factbook Project\fonts\Domine-Bold.ttf"

SPINE_TEXT_COLOR = (0, 0, 0)  # RGB 0–1
SPINE_ROTATE_DEG = 270        # 90 or 270
# Match KDP paperback “Spine Safe Area”: ~0.118" total safe width on a 0.243" spine (108 pages)
SPINE_MARGIN_X_IN = 0.0625    # left/right inset inside TRUE spine
SPINE_MARGIN_Y_IN = 0.125     # top/bottom inset (bleed clearance)

# ===== BOOK / LAYOUT =====
TRIM_W_IN, TRIM_H_IN = 6.0, 9.0
BLEED_IN = 0.125
DPI = 300
MARGIN_IN = 0.50
FIT_MODE = "contain"           # "contain", "cover", or "fillcrop"
VALID_EXT = {".png", ".jpg", ".jpeg"}

# optional thin lines where panels meet the spine
DRAW_SPINE_EDGE_LINES = True
SPINE_EDGE_LINE_WIDTH_PT = 1.0
SPINE_EDGE_LINE_COLOR = (0, 0, 0)

# ===== CONSTANTS (paperback per-page thickness) =====
PT = 72.0
SPINE_PER_PAGE = {"white":0.002252, "cream":0.0025, "color":0.002347}
PAPER = "white"   # set "white" | "cream" | "color" per your interior

# ---------- helpers ----------
def even_pages(p: int) -> int:
    return p if p % 2 == 0 else p + 1

def px(inches: float, dpi: int) -> int:
    return int(round(inches * dpi))

def list_images():
    items = []
    for f in os.listdir(INPUT_DIR):
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
    page.insert_image(rect, filename=img_path)

def insert_image_fill_rect_with_crop(page, rect: fitz.Rect, img_path: str, dpi: int):
    from io import BytesIO
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
            new_w = int(round(h * target_aspect))
            left = max(0, (w - new_w) // 2)
            im = im.crop((left, 0, left + new_w, h))
        elif src_aspect < target_aspect:
            new_h = int(round(w / target_aspect))
            top = max(0, (h - new_h) // 2)
            im = im.crop((0, top, w, top + new_h))

        im = im.resize((target_w_px, target_h_px), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, format="PNG")
        page.insert_image(rect, stream=buf.getvalue(), keep_proportion=False)

def insert_rotated_image_fit(page, rect: fitz.Rect, img_path: str, deg: int = 90):
    from io import BytesIO
    with Image.open(img_path) as im:
        im = im.convert("RGBA").rotate(deg, expand=True)
        buf = BytesIO()
        im.save(buf, format="PNG")
        page.insert_image(rect, stream=buf.getvalue(), keep_proportion=True)

def insert_rotated_text_pil(page, rect: fitz.Rect, text: str, font_path: str,
                            rotate_deg: int = 270, color=(1,1,1),
                            dpi: int = 300, thickness_frac: float = 0.88):
    if not text:
        return
    from io import BytesIO
    from math import ceil
    from PIL import Image, ImageDraw, ImageFont

    w_px = max(1, int(round(rect.width  / PT * dpi)))
    h_px = max(1, int(round(rect.height / PT * dpi)))
    target_px = max(1, int(round((w_px if rotate_deg in (90, 270) else h_px) * thickness_frac)))
    font = ImageFont.truetype(font_path, size=target_px)

    meas = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    drw = ImageDraw.Draw(meas)
    bbox = drw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    PAD = ceil(target_px * 0.18)
    canvas_w = text_w + PAD * 2
    canvas_h = text_h + PAD * 2

    text_im = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    drw = ImageDraw.Draw(text_im)
    col = tuple(int(round(c * 255)) for c in color) + (255,)
    drw.text((PAD, PAD), text, font=font, fill=col)

    text_im = text_im.rotate(rotate_deg, expand=True)
    FIT_MARGIN = 0.98
    scale = min((w_px * FIT_MARGIN) / text_im.width,
                (h_px * FIT_MARGIN) / text_im.height, 1.0)
    if scale < 1.0:
        new_size = (max(1, int(text_im.width * scale)),
                    max(1, int(text_im.height * scale)))
        text_im = text_im.resize(new_size, Image.LANCZOS)

    base = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
    ox = (w_px - text_im.width) // 2
    oy = (h_px - text_im.height) // 2
    base.paste(text_im, (ox, oy), text_im)

    buf = BytesIO()
    base.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue(), keep_proportion=False)

# ---------- PAPERBACK GEOMETRY ----------
def cover_specs_paperback(pages: int, trim_w=6.0, trim_h=9.0, bleed=0.125, dpi=300, paper="white"):
    spine = SPINE_PER_PAGE[paper] * pages
    full_w = 2 * trim_w + spine + 2 * bleed
    full_h = trim_h + 2 * bleed
    def to_px(inches): return int(round(inches * dpi))
    return {
        "binding": "paperback",
        "trim_w_in": trim_w, "trim_h_in": trim_h,
        "bleed_in": bleed,
        "pages": pages,
        "spine_in": spine, "spine_px": to_px(spine),
        "full_w_in": full_w, "full_h_in": full_h,
        "full_w_px": to_px(full_w), "full_h_px": to_px(full_h),
    }

def make_cover_spread_paperback(img_path: str, out_path: str, pages: int,
                                paper: str = PAPER,
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

    pb = cover_specs_paperback(pages, TRIM_W_IN, TRIM_H_IN, BLEED_IN, DPI, paper)
    if spine_override is not None:
        pb["spine_in"] = spine_override
        pb["spine_px"] = px(spine_override, DPI)
        pb["full_w_in"] = 2 * TRIM_W_IN + pb["spine_in"] + 2 * BLEED_IN
        pb["full_w_px"] = px(pb["full_w_in"], DPI)

    doc = fitz.open()
    W = pb["full_w_in"] * PT
    H = pb["full_h_in"] * PT
    page = doc.new_page(width=W, height=H)

    # Fill to bleed edge
    page.draw_rect(page.rect, fill=bg, color=None)

    def IN(x): return x * PT

    # Panels (paperback): [bleed][BACK][SPINE][FRONT][bleed]
    x0_back_in = BLEED_IN
    x1_back_in = x0_back_in + TRIM_W_IN
    y0_in = BLEED_IN
    y1_in = y0_in + TRIM_H_IN
    back_panel = fitz.Rect(IN(x0_back_in), IN(y0_in), IN(x1_back_in), IN(y1_in))

    x0_spine_in = x1_back_in
    x1_spine_in = x0_spine_in + pb["spine_in"]
    spine_panel = fitz.Rect(IN(x0_spine_in), IN(y0_in), IN(x1_spine_in), IN(y1_in))

    x0_front_in = x1_spine_in
    x1_front_in = x0_front_in + TRIM_W_IN
    front_panel = fitz.Rect(IN(x0_front_in), IN(y0_in), IN(x1_front_in), IN(y1_in))

    # TRUE spine (same as spine_panel for paperback)
    true_spine = spine_panel

    # Spine text bands (use KDP safe insets)
    r = fitz.Rect(true_spine.x0 + IN(SPINE_MARGIN_X_IN),
                  true_spine.y0 + IN(SPINE_MARGIN_Y_IN),
                  true_spine.x1 - IN(SPINE_MARGIN_X_IN),
                  true_spine.y1 - IN(SPINE_MARGIN_Y_IN))

    h = r.height
    title_band  = fitz.Rect(r.x0, r.y0 + h*0.04, r.x1, r.y0 + h * 0.40)
    date_band   = fitz.Rect(r.x0, r.y0 + h*0.40, r.x1, r.y0 + h * 0.80)
    author_band = fitz.Rect(r.x0, r.y0 + h*0.71, r.x1, r.y0 + h * 0.96)

    # utility to place front/back
    def dest_for_panel(panel_rect, which: str, mode: str, safe: float):
        if mode == "panel":
            return fitz.Rect(panel_rect.x0 + IN(safe),
                             panel_rect.y0 + IN(safe),
                             panel_rect.x1 - IN(safe),
                             panel_rect.y1 - IN(safe))
        # "trim": place exactly 6x9 aligned to outer fore-edge
        iw, ih = TRIM_W_IN - 2*safe, TRIM_H_IN - 2*safe
        if which == "front":
            x1 = panel_rect.x1 - IN(safe)
            x0 = x1 - IN(iw)
        else:
            x0 = panel_rect.x0 + IN(safe)
            x1 = x0 + IN(iw)
        y0 = panel_rect.y0 + (panel_rect.height - IN(ih)) / 2
        y1 = y0 + IN(ih)
        return fitz.Rect(x0, y0, x1, y1)

    # FRONT image
    dest_front = dest_for_panel(front_panel, "front", place_mode, safe_margin_in)
    page.insert_image(dest_front, filename=img_path, keep_proportion=True)

    # BACK image (optional)
    if back_img_path:
        b_mode = back_place_mode or place_mode
        b_safe = back_safe_margin_in if back_safe_margin_in is not None else safe_margin_in
        dest_back = dest_for_panel(back_panel, "back", b_mode, b_safe)
        page.insert_image(dest_back, filename=back_img_path, keep_proportion=True)

    # Optional spine background image (exact fit, will crop if needed)
    if spine_img_path:
        insert_image_fill_rect_with_crop(page, spine_panel, spine_img_path, DPI)

    # Panel separators
    if DRAW_SPINE_EDGE_LINES:
        y_top, y_bottom = spine_panel.y0, spine_panel.y1
        # left join (back → spine)
        page.draw_line((spine_panel.x0, y_top), (spine_panel.x0, y_bottom),
                       color=SPINE_EDGE_LINE_COLOR, width=SPINE_EDGE_LINE_WIDTH_PT)
        # right join (spine → front)
        page.draw_line((spine_panel.x1, y_top), (spine_panel.x1, y_bottom),
                       color=SPINE_EDGE_LINE_COLOR, width=SPINE_EDGE_LINE_WIDTH_PT)

    # Spine title image
    if spine_title_img_path and os.path.exists(spine_title_img_path):
        insert_rotated_image_fit(page, title_band, spine_title_img_path, deg=SPINE_ROTATE_DEG)

    # Date / Author (rotated Domine-Bold)
    insert_rotated_text_pil(page, date_band,   spine_date_text,   SPINE_FONT_FILE,
                            rotate_deg=SPINE_ROTATE_DEG, color=SPINE_TEXT_COLOR,
                            dpi=DPI, thickness_frac=0.90)
    insert_rotated_text_pil(page, author_band, spine_author_text, SPINE_FONT_FILE,
                            rotate_deg=SPINE_ROTATE_DEG, color=SPINE_TEXT_COLOR,
                            dpi=DPI, thickness_frac=0.55)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path, garbage=4, clean=True)
    doc.close()

# ---------- CLI ----------
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
    cover_pdf = os.path.join(OUTPUT_DIR, f"{stem}_PB_COVER.pdf")

    spine_override_in = None

    while True:
        try:
            pages_in = int(input("Enter total interior pages (e.g., 108): ").strip())
        except Exception:
            print("Enter a valid integer page count.")
            continue

        pages = even_pages(pages_in)
        if pages != pages_in:
            print(f"⚠ Page count must be even. Using {pages} instead of {pages_in}.")

        while True:
            pb = cover_specs_paperback(pages, TRIM_W_IN, TRIM_H_IN, BLEED_IN, DPI, PAPER)
            auto_spine = pb["spine_in"]
            if spine_override_in is not None:
                pb["spine_in"] = spine_override_in

            print("\n=== SPEC PREVIEW — PAPERBACK ===")
            print(f"Chosen file      : {chosen}")
            print(f"Interior trim    : {TRIM_W_IN:.3f} in × {TRIM_H_IN:.3f} in  "
                  f"({px(TRIM_W_IN,DPI)} × {px(TRIM_H_IN,DPI)} px @ {DPI} DPI)")
            if spine_override_in is None:
                print(f"Spine (auto)     : {auto_spine:.3f} in  ({px(auto_spine, DPI)} px)")
            else:
                print(f"Spine (override) : {spine_override_in:.3f} in  ({px(spine_override_in, DPI)} px)  [auto={auto_spine:.3f}\"]")
            full_w_in = 2*TRIM_W_IN + (spine_override_in or auto_spine) + 2*BLEED_IN
            full_h_in = TRIM_H_IN + 2*BLEED_IN
            print(f"Full cover       : {full_w_in:.3f} in × {full_h_in:.3f} in")
            print(f"Bleed            : {BLEED_IN:.3f} in on all sides")
            print(f"Cover spread out : {cover_pdf}")
            print("Commands: [y] proceed  [p] change pages  [s] set spine  [r] reset spine  [n] abort")
            cmd = input("> ").strip().lower()

            if cmd == "y":
                break
            if cmd == "n":
                print("Aborted.")
                return
            if cmd == "p":
                break
            if cmd == "r":
                spine_override_in = None
                continue
            if cmd == "s":
                raw = input("Enter spine width (e.g., 0.243 or 73px): ").strip().lower()
                try:
                    if raw.endswith("px"):
                        px_val = float(raw[:-2])
                        spine_override_in = px_val / DPI
                    else:
                        spine_override_in = float(raw)
                    if not (0.05 <= spine_override_in <= 2.0):
                        print("Unusual spine width; keeping it but double-check.")
                except Exception:
                    print("Could not parse that spine value.")
                continue

            print("Unknown command.")

        if cmd == "y":
            break

    # derive "Month Day" from filename
    import re
    m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)[ _-]?(\d{1,2})',
                  stem, re.IGNORECASE)
    spine_date_text = (f"{m.group(1).title()} {int(m.group(2))}" if m else "").upper()
    spine_author_text = "By TJ Mulrenan"

    back_path  = BACK_IMG  if os.path.exists(BACK_IMG)  else None
    spine_path = SPINE_IMG if os.path.exists(SPINE_IMG) else None
    title_img_path = SPINE_TITLE_IMG if os.path.exists(SPINE_TITLE_IMG) else None

    print(f"→ Writing COVER SPREAD PDF: {cover_pdf}")
    make_cover_spread_paperback(
        img_path,
        cover_pdf,
        pages,
        paper=PAPER,
        safe_margin_in=0.0,
        place_mode="trim",
        bg=(1, 1, 1),
        spine_override=spine_override_in,
        back_img_path=back_path,
        back_place_mode="trim",
        back_safe_margin_in=0.0,
        spine_img_path=spine_path,
        spine_title_img_path=title_img_path,
        spine_date_text=spine_date_text,
        spine_author_text=spine_author_text
    )
    print("\n✅ Done.")
    print(f"Cover: {cover_pdf}")

if __name__ == "__main__":
    main()
