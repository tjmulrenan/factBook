# make_cover_paperback.py
# pip install pymupdf pillow

import os, sys, re
import fitz  # PyMuPDF
from PIL import Image

# ===== PATHS =====
INPUT_DIR  = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\complete"
OUTPUT_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\paperback"
BACK_IMG   = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\back.png"
SPINE_IMG  = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\spine.png"
SPINE_TITLE_IMG = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\what_happened_on.png"
SPINE_FONT_FILE = r"C:\Users\timmu\Documents\repos\Factbook Project\fonts\Domine-Bold.ttf"
FINAL_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\FINAL"

SPINE_TEXT_COLOR = (0, 0, 0)  # RGB 0–1
SPINE_ROTATE_DEG = 270        # 90 or 270
SPINE_MARGIN_X_IN = 0.0625    # left/right inset inside TRUE spine
SPINE_MARGIN_Y_IN = 0.125     # top/bottom inset (bleed clearance)
SPINE_WRAP_IN = 0.25          # wrap spine a bit onto covers

# ===== BOOK / LAYOUT =====
TRIM_W_IN, TRIM_H_IN = 6.0, 9.0
BLEED_IN = 0.125
DPI = 300
MARGIN_IN = 0.50
FIT_MODE = "contain"           # "contain", "cover", or "fillcrop"
VALID_EXT = {".png", ".jpg", ".jpeg"}

DRAW_SPINE_EDGE_LINES = True
SPINE_EDGE_LINE_WIDTH_PT = 2.0
SPINE_EDGE_LINE_COLOR = (0, 0, 0)

# ===== CONSTANTS (paperback per-page thickness) =====
PT = 72.0
SPINE_PER_PAGE = {
    "white": 0.002252,          # B&W White
    "cream": 0.0025,            # B&W Cream
    "standard_color": 0.002252, # Standard Color on white paper
    "premium_color": 0.002347,  # Premium Color
}
PAPER = "standard_color"

# ---------- helpers ----------
def _read_doy():
    # CLI: b_coverBuild_paperback.py 89   OR   --doy=89
    for arg in sys.argv[1:]:
        if arg.isdigit():
            return int(arg)
        if arg.startswith("--doy="):
            v = arg.split("=", 1)[1]
            if v.isdigit():
                return int(v)
    # ENV
    v = os.environ.get("FACTBOOK_DOY")
    if v and v.isdigit():
        return int(v)
    # STDIN (from pipeline)
    try:
        line = sys.stdin.readline().strip()
        if line.isdigit():
            return int(line)
    except Exception:
        pass
    return None

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

    # Bleed-inclusive rects
    back_bleed_rect  = fitz.Rect(IN(x0_back_in - BLEED_IN), IN(y0_in - BLEED_IN),
                                 IN(x1_back_in),             IN(y1_in + BLEED_IN))
    front_bleed_rect = fitz.Rect(IN(x0_front_in),            IN(y0_in - BLEED_IN),
                                 IN(x1_front_in + BLEED_IN), IN(y1_in + BLEED_IN))
    spine_bleed_rect = fitz.Rect(
        max(0, spine_panel.x0 - IN(SPINE_WRAP_IN)),
        IN(y0_in - BLEED_IN),
        min(page.rect.x1, spine_panel.x1 + IN(SPINE_WRAP_IN)),
        IN(y1_in + BLEED_IN)
    )

    # TRUE spine (same as spine_panel for paperback)
    true_spine = spine_panel

    # Spine text bands (safe insets)
    r = fitz.Rect(true_spine.x0 + IN(SPINE_MARGIN_X_IN),
                  true_spine.y0 + IN(SPINE_MARGIN_Y_IN),
                  true_spine.x1 - IN(SPINE_MARGIN_X_IN),
                  true_spine.y1 - IN(SPINE_MARGIN_Y_IN))
    h = r.height
    title_band  = fitz.Rect(r.x0, r.y0 + h*0.04, r.x1, r.y0 + h * 0.40)
    date_band   = fitz.Rect(r.x0, r.y0 + h*0.40, r.x1, r.y0 + h * 0.80)
    author_band = fitz.Rect(r.x0, r.y0 + h*0.71, r.x1, r.y0 + h * 0.96)

    # FRONT / BACK
    insert_image_fill_rect_with_crop(page, front_bleed_rect, img_path, DPI)
    if back_img_path:
        insert_image_fill_rect_with_crop(page, back_bleed_rect, back_img_path, DPI)

    # Spine background
    if spine_img_path:
        insert_image_fill_rect_with_crop(page, spine_bleed_rect, spine_img_path, DPI)

    # Panel separators
    if DRAW_SPINE_EDGE_LINES:
        left_line_x  = max(0, spine_panel.x0 - IN(SPINE_WRAP_IN))
        right_line_x = min(page.rect.x1, spine_panel.x1 + IN(SPINE_WRAP_IN))
        y_top    = IN(y0_in - BLEED_IN)
        y_bottom = IN(y1_in + BLEED_IN)
        page.draw_line((left_line_x, y_top), (left_line_x, y_bottom),
                       color=SPINE_EDGE_LINE_COLOR, width=SPINE_EDGE_LINE_WIDTH_PT)
        page.draw_line((right_line_x, y_top), (right_line_x, y_bottom),
                       color=SPINE_EDGE_LINE_COLOR, width=SPINE_EDGE_LINE_WIDTH_PT)

    # (Spine text currently disabled; uncomment if needed)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path, garbage=4, clean=True)
    doc.close()

# ---------- CLI ----------
def main():
    print("=== MAKE COVER PAPERBACK (non-interactive) ===")

    target_num = _read_doy()
    if not isinstance(target_num, int):
        print("❌ Missing DOY. Pass as CLI (e.g., 89), --doy=89, ENV FACTBOOK_DOY, or via stdin.")
        sys.exit(1)

    # Find FINAL/<DOY>_<Month>_<Day> folder
    pattern = re.compile(r'^(?P<num>\d+)_([A-Za-z]+)_(\d{1,2})$')
    candidates = []
    for name in os.listdir(FINAL_DIR):
        full = os.path.join(FINAL_DIR, name)
        if not os.path.isdir(full):
            continue
        m = pattern.match(name)
        if m and int(m.group('num')) == target_num:
            candidates.append(name)

    if not candidates:
        print(f"❌ No FINAL subfolder for DOY {target_num} (expected '<DOY>_<Month>_<Day>').")
        sys.exit(1)

    folder_name = sorted(candidates)[0]  # deterministic if multiple
    target_dir = os.path.join(FINAL_DIR, folder_name)
    parts = folder_name.split("_")
    month_name = parts[1].title()
    day_num = int(parts[2])

    # Required files/paths
    img_path = os.path.join(target_dir, "front_cover.png")
    manuscript_path = os.path.join(target_dir, "full_manuscript.pdf")
    cover_pdf = os.path.join(target_dir, "book_cover.pdf")
    spine_path_candidate = os.path.join(target_dir, "spine.png")

    if not os.path.exists(img_path):
        print(f"❌ front_cover.png missing: {img_path}")
        sys.exit(1)
    if not os.path.exists(manuscript_path):
        print(f"❌ full_manuscript.pdf missing: {manuscript_path}")
        sys.exit(1)

    # Page count (auto)
    try:
        with fitz.open(manuscript_path) as mdoc:
            pages_in = mdoc.page_count
    except Exception as e:
        print(f"❌ Failed to read manuscript: {e}")
        sys.exit(1)

    # Force even pages for print
    pages = even_pages(pages_in)
    if pages != pages_in:
        print(f"ℹ Even-page adjust: {pages_in} → {pages}")

    # Optional assets (auto if present)
    back_path  = BACK_IMG if os.path.exists(BACK_IMG) else None
    title_img_path = SPINE_TITLE_IMG if os.path.exists(SPINE_TITLE_IMG) else None
    spine_path = spine_path_candidate if os.path.exists(spine_path_candidate) \
                 else (SPINE_IMG if os.path.exists(SPINE_IMG) else None)

    # Spine text (if you later re-enable your spine text routine)
    spine_date_text = f"{month_name} {day_num}".upper()
    spine_author_text = "By TJ Mulrenan"

    print(f"> DOY: {target_num}  |  Folder: {folder_name}")
    print(f"> Pages (even): {pages}")
    print(f"> Front: {img_path}")
    print(f"> Back : {back_path or 'None'}")
    print(f"> Spine img: {spine_path or 'None'}")
    print(f"> Out  : {cover_pdf}")

    # Auto build with computed spine (no override, no prompts)
    make_cover_spread_paperback(
        img_path,
        cover_pdf,
        pages,
        paper=PAPER,
        safe_margin_in=0.0,
        place_mode="trim",
        bg=(1, 1, 1),
        spine_override=None,                 # <-- TRUST auto spine calc
        back_img_path=back_path,
        back_place_mode="trim",
        back_safe_margin_in=0.0,
        spine_img_path=spine_path,
        spine_title_img_path=title_img_path,
        spine_date_text=spine_date_text,
        spine_author_text=spine_author_text
    )

    print("✅ Paperback cover built.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n🔥 Unhandled error: {e}")
        try:
            import traceback; traceback.print_exc()
        except Exception:
            pass
        sys.exit(1)