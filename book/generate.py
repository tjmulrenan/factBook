import hashlib
import io
import json
import logging
import os
import random
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import FINAL_FACTS_DIR, FINAL_OUTPUT_DIR, FONTS_DIR, BACKGROUNDS_DIR

import fitz
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont

from book.flowables import CUSTOM_PAGE_SIZE, MyDocTemplate
from book.content_builder import (
    build_elements, CATEGORY_BACKGROUNDS, final_categories_dict,
)

def compute_background_ranges(page_tracker, category_backgrounds):

    def normalize_text(text):
        # Remove emojis
        text = ''.join(c for c in text if not unicodedata.category(c).startswith('So'))

        # Normalize curly quotes/apostrophes to straight ones
        text = text.replace("'", "'").replace("'", "'")  # single quotes/apostrophes
        text = text.replace(""", '"').replace(""", '"')  # double quotes

        return text.strip()

    sorted_pages = sorted(page_tracker.items(), key=lambda x: x[1])
    temp_ranges = []
    skip_until = None

    for i, (label, start_page) in enumerate(sorted_pages):
        # ✅ Skip anything that falls inside the TOC range — except Vibe Check
        if skip_until is not None and start_page <= skip_until and label != "__TODAYS_VIBE_CHECK__":
            logging.debug(f"⏭️ Skipping label '{label}' at page {start_page} (within TOC range ending {skip_until})")
            continue

        # Default end page: just before the next marker or end of doc
        end_page = sorted_pages[i + 1][1] - 1 if i + 1 < len(sorted_pages) else 999
        logging.debug(f"🔍 Considering label '{label}' → page {start_page} to {end_page}")

        if label == "__COVER_PAGE__":
            bg_path = str(BACKGROUNDS_DIR / "to_from.png")
            kind = "cover"
            logging.info(f"📕 Cover page detected → pages {start_page}–{end_page}")
            if os.path.exists(bg_path):
                temp_ranges.append((start_page, end_page, bg_path, kind))
            else:
                logging.warning(f"❌ Cover background image not found: {bg_path}")
            continue

        elif label == "__INTRO_PAGE__":
            bg_path = str(BACKGROUNDS_DIR / "before_we_begin.png")
            kind = "intro"
            logging.info(f"📘 Intro range detected → pages {start_page}–{end_page}")
            if os.path.exists(bg_path):
                temp_ranges.append((start_page, end_page, bg_path, kind))
            else:
                logging.warning(f"❌ Intro background image not found: {bg_path}")
            continue

        elif label == "__TOC_PAGE__":
            start = start_page
            end = start  # TOC is one page
            toc_path = str(BACKGROUNDS_DIR / "table_of_contents.png")
            if os.path.exists(toc_path):
                temp_ranges.append((start, end, toc_path, "toc"))
                logging.info(f"🧭 TOC background applied to page {start}")
            else:
                logging.warning(f"🚫 TOC image missing at: {toc_path}")

            # Pre-apply Vibe *title* background to the next page (e.g., page 4)
            vibe_check_page = start + 1
            vibe_path = str(BACKGROUNDS_DIR / "todays_vibe_check_t.png")
            if os.path.exists(vibe_path):
                temp_ranges.append((vibe_check_page, vibe_check_page, vibe_path, "vibe_title"))
                logging.info(f"🌤️ Vibe title background applied to page {vibe_check_page}")
            else:
                logging.warning(f"❌ Vibe Check *_t.png background not found: {vibe_path}")

            # ✅ Only skip the TOC page so the "Today's Vibe Check" category label
            # can run next and add the *normal* background for subsequent pages.
            skip_until = start
            continue

        elif label == "__TODAYS_VIBE_CHECK__":
            bg_path = str(BACKGROUNDS_DIR / "todays_vibe_check.png")
            kind = "vibe"

            # 🔒 Force Vibe Check to start immediately after TOC (if TOC exists)
            toc_end = page_tracker.get("__TOC_END__")
            if toc_end:
                start_page = toc_end + 1
                end_page = start_page  # Make it a single page background
                logging.info(f"🌤️ Forcing Vibe Check background → page {start_page} (immediately after TOC)")
            else:
                logging.info(f"🌤️ Vibe Check page detected → pages {start_page}–{end_page}")

            if os.path.exists(bg_path):
                temp_ranges.append((start_page, end_page, bg_path, kind))
            else:
                logging.warning(f"❌ Vibe Check background image not found: {bg_path}")
            continue

        elif label.startswith("__TRIVIA_START__"):
            base_path = str(BACKGROUNDS_DIR / "trivia_time.png")
            title_path = str(BACKGROUNDS_DIR / "trivia_time_t.png")
            kind = "trivia"

            logging.info(f"🎲 Trivia range detected: '{label}' → pages {start_page}–{end_page}")

            if os.path.exists(title_path):
                temp_ranges.append((start_page, start_page, title_path, "trivia_title"))
                logging.info(f"🎨 Trivia title background → page {start_page}: {os.path.basename(title_path)}")
            else:
                logging.warning(f"❌ Trivia *_t.png title background missing: {title_path}")

            if end_page > start_page and os.path.exists(base_path):
                temp_ranges.append((start_page + 1, end_page, base_path, kind))
                logging.info(f"🖼️ Trivia background → pages {start_page + 1}–{end_page}: {os.path.basename(base_path)}")
            elif end_page > start_page:
                logging.warning(f"❌ Trivia background image not found: {base_path}")

            continue  # 🔥 CRITICAL: ensures it doesn't fall through to category block



        elif label == "__ANSWERS_START__":
            bg_title_path = str(BACKGROUNDS_DIR / "answers_t.png")
            bg_path = str(BACKGROUNDS_DIR / "answers.png")
            kind = "answers"

            logging.info(f"📜 Answers section detected → pages {start_page}–{end_page}")

            if os.path.exists(bg_title_path):
                temp_ranges.append((start_page, start_page, bg_title_path, f"{kind}_title"))
                logging.info(f"🎨 Answers title background → page {start_page}")
            else:
                logging.warning(f"❌ Missing answers *_t.png background: {bg_title_path}")

            if end_page > start_page and os.path.exists(bg_path):
                temp_ranges.append((start_page + 1, end_page, bg_path, kind))
                logging.info(f"🖼️ Answers background → pages {start_page + 1}–{end_page}")
            elif end_page > start_page:
                logging.warning(f"❌ Missing answers background: {bg_path}")
            continue

        # Handle category or trivia background ranges
        else:
            is_trivia = label.startswith("__TRIVIA_START__")
            if is_trivia:
                # Extract just the category name from "__TRIVIA_START__Category Name"
                stripped = normalize_text(label.replace("__TRIVIA_START__", ""))
            else:
                stripped = normalize_text(label)

            match_key = next(
                (k for k in category_backgrounds if normalize_text(k) == stripped),
                None
            )

            if not match_key:
                logging.warning(f"❓ No match for {'trivia' if is_trivia else 'category'} label '{label}' (stripped: '{stripped}')")
                continue

            bg_base = category_backgrounds[match_key]
            base_start = start_page
            base_end = sorted_pages[i + 1][1] - 1 if i + 1 < len(sorted_pages) else 999

            # Trivia or category-specific background files
            t_path = str(BACKGROUNDS_DIR / f"{bg_base}_t.png")
            normal_path = str(BACKGROUNDS_DIR / f"{bg_base}.png")

            kind = "trivia" if is_trivia else "category"

            # First page (title/intro)
            if os.path.exists(t_path):
                temp_ranges.append((base_start, base_start, t_path, f"{kind}_title"))
                logging.info(f"🎨 {kind.capitalize()} title background for '{label}': {os.path.basename(t_path)} → page {base_start}")
            else:
                logging.warning(f"❌ Missing {kind} *_t.png background: {t_path}")

            # Remaining pages
            if base_end > base_start and os.path.exists(normal_path):
                temp_ranges.append((base_start + 1, base_end, normal_path, kind))
                logging.info(f"🖼️ {kind.capitalize()} content background for '{label}': {os.path.basename(normal_path)} → pages {base_start + 1}–{base_end}")
            elif base_end > base_start:
                logging.warning(f"❌ Missing {kind} *.png background: {normal_path}")



    # ✅ Deduplicate by page – trivia wins if overlap
    page_map = {}
    for start, end, path, label_type in temp_ranges:
        for page in range(start, end + 1):
            if page not in page_map or label_type == "trivia":
                page_map[page] = (path, label_type)

    # ✅ Merge into clean ranges
    background_ranges = []
    current_path = None
    current_label_type = None
    range_start = None

    for page in sorted(page_map):
        path, label_type = page_map[page]
        if path != current_path or label_type != current_label_type:
            if current_path:
                background_ranges.append({
                    "start": range_start,
                    "end": page - 1,
                    "image_path": current_path,
                    "label": current_label_type
                })
            current_path = path
            current_label_type = label_type
            range_start = page

    if current_path:
        background_ranges.append({
            "start": range_start,
            "end": max(page_map),
            "image_path": current_path,
            "label": current_label_type
        })

    # 📋 Log full background map
    logging.info("🗺 Final computed background ranges:")
    for r in background_ranges:
        logging.info(f" → Pages {r['start']}–{r['end']}: {os.path.basename(r['image_path'])} ({r['label']})")

    # 📋 Log raw tracker
    logging.info("📖 Page tracker keys + values:")
    for k, v in sorted(page_tracker.items(), key=lambda x: x[1]):
        logging.info(f"  {k} → page {v}")

    return background_ranges


def generate_pdf_with_manual_toc(json_file, output_pdf):
    with open(json_file, "r", encoding="utf-8") as f:
        facts = json.load(f)

        # Quick sanity check for categories
        for rec in facts:
            raw = rec.get("categories")
            # log the first weird shape we see
            if raw is not None and not (
                isinstance(raw, list) and all(isinstance(x, (str, dict)) for x in raw)
                or isinstance(raw, (str, dict))
            ):
                logging.warning(f"⚠️ Odd categories shape in id={rec.get('id')}: {raw}")
                break

    book_seed = int(hashlib.md5(json_file.encode("utf-8")).hexdigest(), 16) % (2**32)

    # Font registration
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONTS_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONTS_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(FONTS_DIR / "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", str(FONTS_DIR / "DejaVuSans-BoldOblique.ttf")))
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")

    pdfmetrics.registerFont(TTFont("LuckiestGuy", str(FONTS_DIR / "LuckiestGuy-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Baloo2", str(FONTS_DIR / "Baloo2-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Baloo2-Bold", str(FONTS_DIR / "Baloo2-Bold.ttf")))

    registerFontFamily("Baloo2", normal="Baloo2", bold="Baloo2-Bold")

    date_str = extract_date_with_suffix(json_file)

    # Styles
    styles = {
        'cover_title': ParagraphStyle(
            "CoverTitle", fontName="LuckiestGuy", fontSize=28, leading=30,
            alignment=TA_CENTER, spaceAfter=12
        ),
        'cover_date': ParagraphStyle(
            "CoverDate", fontName="Baloo2", fontSize=22, leading=26,
            alignment=TA_CENTER, spaceAfter=10
        ),
        'intro_header': ParagraphStyle(
            "IntroHeader", fontName="LuckiestGuy", fontSize=20, leading=22,
            alignment=TA_LEFT, spaceAfter=0
        ),
        'intro': ParagraphStyle(
            "Intro", fontName="Baloo2", fontSize=12.5, leading=15,
            spaceAfter=0
        ),
        'toc_title': ParagraphStyle(
            "TOCTitle", fontName="LuckiestGuy", fontSize=20, leading=24,
            spaceAfter=0, alignment=TA_CENTER
        ),
        'toc_item': ParagraphStyle(
            "TOCItem", fontName="Baloo2", fontSize=11.5, leading=14,
            spaceAfter=0, alignment=TA_LEFT
        ),
        'category': ParagraphStyle(
            "CategoryTitle", fontName="Baloo2", fontSize=0.1, leading=1,
            spaceAfter=0, textColor=colors.white, alignment=TA_LEFT
        ),
        'cat_title': ParagraphStyle(
            "CatTitle", fontName="LuckiestGuy", fontSize=20, leading=24,
            spaceAfter=0, spaceBefore=0
        ),
        'title': ParagraphStyle(
            "FactTitle", fontName="Baloo2-Bold", fontSize=14, leading=25,
            spaceAfter=0
        ),
        'story': ParagraphStyle(
            "FactStory", fontName="Baloo2", fontSize=11.5, leading=18,
            spaceAfter=0, spaceBefore=0
        ),
        'wordsearch': ParagraphStyle(
            "Wordsearch", fontName="Baloo2", fontSize=8, leading=12,
            spaceAfter=2, spaceBefore=0
        ),
        'crossword_layout': ParagraphStyle(
            "Crossword_Layout", fontName="LuckiestGuy", fontSize=10, leading=12,
            spaceAfter=2, spaceBefore=0
        ),
        'crossword': ParagraphStyle(
            "Crossword", fontName="Baloo2", fontSize=7, leading=11,
            spaceAfter=2, spaceBefore=0
        ),
        'trivia_title': ParagraphStyle(
            "TriviaTitle", fontName="LuckiestGuy", fontSize=18, leading=22,
            spaceAfter=10, alignment=TA_CENTER
        ),
        'trivia_questions': ParagraphStyle(
            "TriviaQuestions", fontName="Baloo2", fontSize=12, leading=14,
            spaceAfter=0, spaceBefore=0
        ),
        'trivia_answers': ParagraphStyle(
            "TriviaAnswers", fontName="Baloo2", fontSize=10, leading=12,
            spaceAfter=0, spaceBefore=0, leftIndent=10, rightIndent=10
        )
    }




    # First pass – generate page tracker info
    random.seed(book_seed)
    doc1 = MyDocTemplate(output_pdf, pagesize=CUSTOM_PAGE_SIZE, title=f"What Happened on {date_str}")
    elements1 = build_elements(facts, styles, date_str)
    doc1.build(elements1)

    # Capture page locations for TOC and category headings
    category_pages = sorted(
        [(label, page) for label, page in doc1._page_tracker.items()
        if not label.startswith("__TRIVIA_START__")],
        key=lambda x: x[1]
    )

    # 🔧 Hardcode TOC page number(s)
    TOC_PAGE_OVERRIDES = {"Today's Vibe Check": 4}
    category_pages = [(cat, TOC_PAGE_OVERRIDES.get(cat, pg)) for cat, pg in category_pages]

    # Second pass – render again with TOC now present
    random.seed(book_seed)
    doc2_stream = io.BytesIO()
    doc2 = MyDocTemplate(doc2_stream, pagesize=CUSTOM_PAGE_SIZE, title=f"What Happened on {date_str}")
    elements2 = build_elements(facts, styles, date_str, category_pages)
    doc2.build(elements2)

    # Compute background ranges
    background_ranges = compute_background_ranges(doc2._page_tracker, CATEGORY_BACKGROUNDS)

    # Final doc with backgrounds applied
    final_doc = MyDocTemplate(output_pdf, pagesize=CUSTOM_PAGE_SIZE, title=f"What Happened on {date_str}")
    final_doc._background_ranges = background_ranges

    # Rebuild final output
    random.seed(book_seed)
    final_elements = build_elements(facts, styles, date_str, category_pages)

    logging.info("📄 Final build started with full backgrounds...")
    final_doc.build(final_elements)
    logging.info("✅ Final PDF built successfully.")

    # Export final categories for debugging
    output_json = output_pdf.replace(".pdf", "_categories.json")
    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(final_categories_dict, out, indent=2)
    logging.info(f"📁 Categories exported to: {output_json}")
    logging.info(f"✅ PDF created at: {output_pdf}")

    logging.debug("Page tracker keys: %s", list(doc2._page_tracker.keys()))
    for r in final_doc._background_ranges:
        logging.debug(" → Pages %s–%s: %s", r['start'], r['end'], os.path.basename(r['image_path']))

def overlay_trivia_pages(pdf_path, trivia_img_path):
    doc = fitz.open(pdf_path)
    trivia_img_temp = "temp_trivia.jpg"

    # Prepare trivia image at full quality
    img = Image.open(trivia_img_path)
    img = img.convert("RGB")  # Ensure RGB mode
    img.save(trivia_img_temp, format="JPEG", quality=100)

    trivia_indexes = []

    # ✅ Use a precise two-page pattern: marker page + following page
    prev_was_marker = False
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if "__TRIVIA_START__" in text:
            trivia_indexes.append(i)
            prev_was_marker = True
            logging.info(f"📍 Found trivia marker on page {i+1}")
        elif prev_was_marker:
            trivia_indexes.append(i)
            prev_was_marker = False
            logging.info(f"📍 Included Trivia Time content page: {i+1}")

    # ✅ Insert image only on these targeted pages
    for idx in trivia_indexes:
        if idx < len(doc):  # safety check
            page = doc[idx]
            rect = page.rect
            try:
                page.insert_image(rect, filename=trivia_img_temp, overlay=False)
                logging.info(f"✅ Background added to page {idx+1}")
            except Exception as e:
                logging.warning(f"❌ Failed to insert background on page {idx+1}: {e}")

    # Save and clean up
    temp_output = pdf_path + ".temp.pdf"
    doc.save(temp_output)
    doc.close()
    os.replace(temp_output, pdf_path)
    os.remove(trivia_img_temp)

    logging.info(f"✅ Final trivia backgrounds applied to {len(trivia_indexes)} pages.")

def extract_date_with_suffix(filename):
    match = re.search(r'([A-Za-z]+)[ _]?(\d{1,2})', filename)
    if match:
        month = match.group(1)
        day = int(match.group(2))
        return f"{month} {add_ordinal_suffix(day)}"
    return "Unknown Date"

def add_ordinal_suffix(day):
    if 10 <= day % 100 <= 20:
        return f"{day}th"
    return f"{day}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th') }"

def get_unique_filename(directory, base_name):
    name, ext = os.path.splitext(base_name)
    counter = 1
    candidate = os.path.join(directory, base_name)
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{name}_{counter}{ext}")
        counter += 1
    return candidate

if __name__ == "__main__":
    FACTS_DIR = str(FINAL_FACTS_DIR)
    FINAL_ROOT = str(FINAL_OUTPUT_DIR)

    # Build an index: number -> (filename, "Month_Day")
    pattern = re.compile(
        r'^(?P<num>\d+)_((?P<month>[A-Za-z]+)_(?P<day>\d{1,2}))_Final\.json$',
        re.IGNORECASE
    )
    index = {}

    try:
        for fname in os.listdir(FACTS_DIR):
            if not fname.lower().endswith(".json"):
                continue
            m = pattern.match(fname)
            if m:
                num = int(m.group("num"))
                month_day = f"{m.group('month')}_{m.group('day')}"
                index[num] = (fname, month_day)
    except FileNotFoundError:
        print(f"❌ Facts directory not found: {FACTS_DIR}")
        sys.exit(1)

    if not index:
        print("❌ No *_Final.json files found in the facts directory.")
        sys.exit(1)

    # Resolve DOY: --doy arg, FACTBOOK_DOY env var, or interactive prompt
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
        print("❌ Please enter a valid number, e.g., 89")
        sys.exit(1)

    pick = int(user_in)
    if pick not in index:
        # Small hint with the nearest numbers to reduce hunting
        nearest = sorted(index.keys())
        hint = ", ".join(str(n) for n in nearest[:10]) + (" ..." if len(nearest) > 10 else "")
        print(f"❌ {pick} not found. Known numbers start like: {hint}")
        sys.exit(1)

    chosen_file, month_day = index[pick]
    json_path = os.path.join(FACTS_DIR, chosen_file)

    # Output folder: FINAL\<num>_<Month>_<Day>\build_docs\1.pdf
    out_folder = os.path.join(FINAL_ROOT, f"{pick}_{month_day}", "build_docs")
    os.makedirs(out_folder, exist_ok=True)
    output_pdf = os.path.join(out_folder, "1.pdf")

    print(f"📄 Building from: {json_path}")
    print(f"📦 Output to:    {output_pdf}")

    generate_pdf_with_manual_toc(json_path, output_pdf)

    # Overlay trivia backgrounds as you were doing
    overlay_trivia_pages(output_pdf, str(BACKGROUNDS_DIR / "trivia_time.png"))

    print("✅ Done.")
