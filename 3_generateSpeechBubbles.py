import fitz  # PyMuPDF
import json5 as json
import os
import re
import random
from collections import defaultdict
import subprocess, shutil, glob, datetime

# =========================
# Constants & assets
# =========================
INCH = 72
RAISE_Y = 25

# Font
FONT_PATH = r"C:\Personal\factBook\fonts\Baloo2-Bold.ttf"
FONT_NAME = "Baloo2Bold"  # No spaces — required by PyMuPDF

# Quotes & jokes (JSON5 tolerant to trailing commas)
QUOTES_JSON = r"C:\Personal\factBook\quotes\generatedquotes.json"
JOKES_JSON  = r"C:\Personal\factBook\jokes\generatedJokes.json"

# Image assets
IMAGE_MAP = {
    "bonus_fact":        r"C:\Personal\factBook\pics\bonusFact.png",
    "follow_up_question":r"C:\Personal\factBook\pics\followUpQuestion.png",
    "quote":             r"C:\Personal\factBook\pics\quote.png",
    "joke":              r"C:\Personal\factBook\pics\joke.png",
}

# Load quotes/jokes once
with open(QUOTES_JSON, "r", encoding="utf-8") as f:
    quotes_by_category = json.load(f)
with open(JOKES_JSON, "r", encoding="utf-8") as f:
    jokes_by_category = json.load(f)

# Usage tracking
used_quotes = set()
used_jokes = set()
used_bonus_facts = set()
used_follow_ups = set()

insert_counts_by_category = defaultdict(lambda: {
    "quote": 0, "joke": 0, "bonus_fact": 0, "follow_up_question": 0
})
insert_counts = {"quote": 0, "joke": 0, "bonus_fact": 0, "follow_up_question": 0}

# Category headers (union of both sources)
category_headers = list(set(quotes_by_category.keys()) | set(jokes_by_category.keys()))

# =========================
# Helpers
# =========================
def wrap_text_to_two_lines_balanced(text, max_width, font, fontsize):
    words = text.split()
    best_split = None
    best_diff = float("inf")
    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        w1 = font.text_length(line1, fontsize=fontsize)
        w2 = font.text_length(line2, fontsize=fontsize)
        if w1 <= max_width and w2 <= max_width:
            diff = abs(w1 - w2)
            if diff < best_diff:
                best_diff = diff
                best_split = (line1, line2)
    if best_split:
        return list(best_split)
    return [text] if font.text_length(text, fontsize=fontsize) <= max_width else [text[:90] + "..."]

def draw_custom_rounded_bubble(page, bubble_rect, tail_points,
                               fill=(1,1,1), fill_opacity=0.85):
    # simple rect + triangular tail; outline drawn separately
    page.draw_rect(
        bubble_rect, fill=fill, color=None, width=0, overlay=True,
        fill_opacity=fill_opacity, stroke_opacity=0
    )
    page.draw_polyline(
        points=tail_points, closePath=True, fill=fill, color=None,
        width=0, overlay=True, fill_opacity=fill_opacity, stroke_opacity=0
    )

def _find_gs_exe():
    pinned = r"C:\Program Files\gs\gs10.05.1\bin\gswin64c.exe"
    if os.path.exists(pinned): return pinned
    gs = shutil.which("gswin64c") or shutil.which("gs")
    if gs: return gs
    for path in sorted(glob.glob(r"C:\Program Files\gs\gs*\bin\gswin64c.exe"), reverse=True):
        if os.path.exists(path): return path
    return None

def compress_with_ghostscript(inp_pdf, out_pdf,
                              jpeg_quality=100, color_res=300, gray_res=300, mono_res=600):
    gs = _find_gs_exe()
    if not gs:
        raise FileNotFoundError("Ghostscript not found.")
    os.makedirs(os.path.dirname(out_pdf) or ".", exist_ok=True)
    target = out_pdf
    try:
        if os.path.exists(out_pdf):
            os.remove(out_pdf)
    except PermissionError:
        base, ext = os.path.splitext(out_pdf)
        target = base + "_tmp" + ext
        if os.path.exists(target):
            os.remove(target)
    args = [
        gs, "-dBATCH", "-dNOPAUSE", "-dQUIET", "-dNOSAFER",
        "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.7",
        "-dPDFSETTINGS=/printer",
        "-dDetectDuplicateImages=true", "-dCompressFonts=true", "-dSubsetFonts=true",
        "-dAutoRotatePages=/None",
        "-dDownsampleColorImages=true", f"-dColorImageResolution={color_res}",
        "-dColorImageDownsampleType=/Average",
        "-dDownsampleGrayImages=true", f"-dGrayImageResolution={gray_res}",
        "-dGrayImageDownsampleType=/Average",
        "-dDownsampleMonoImages=true", f"-dMonoImageResolution={mono_res}",
        "-dMonoImageDownsampleType=/Subsample",
        "-dEncodeColorImages=true", "-dEncodeGrayImages=true", f"-dJPEGQ={jpeg_quality}",
        f"-sOutputFile={target}", inp_pdf,
    ]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Ghostscript failed.\n"
            f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n\nCommand:\n{' '.join(args)}"
        )
    if target != out_pdf:
        try:
            if os.path.exists(out_pdf):
                os.remove(out_pdf)
        except Exception:
            pass
        os.replace(target, out_pdf)
    return out_pdf

# =========================
# Core: add bubbles
# =========================
def add_bubbles(input_pdf, facts_json, out_pdf):
    if not os.path.exists(facts_json):
        raise FileNotFoundError(f"Facts JSON not found: {facts_json}")
    with open(facts_json, "r", encoding="utf-8") as f:
        facts = json.load(f)
    title_to_fact = {fact["title"]: fact for fact in facts}

    doc = fitz.open(input_pdf)
    page_count = len(doc)
    page_number = 3  # start from 4th page (0-based index)

    doc_font = fitz.Font(fontfile=FONT_PATH)

    current_category = None
    pending_category_insert = None

    while page_number < page_count:
        page = doc.load_page(page_number)
        page.insert_font(fontname=FONT_NAME, fontfile=FONT_PATH)

        try:
            text = page.get_text()
        except Exception as e:
            print(f"⚠️ Could not extract text from page {page_number + 1}: {e}")
            page_number += 1
            continue

        # detect headers for category
        for header in category_headers:
            if header in text:
                pending_category_insert = header
                break

        def normalize(s): return re.sub(r"\s+", " ", s).strip().lower()
        normalized_text = normalize(text)

        matched_facts = [fact for title, fact in title_to_fact.items()
                         if normalize(title) in normalized_text]

        if not matched_facts:
            page_number += 1
            continue

        best_fact = random.choice(matched_facts)

        available_options = []
        opt_type = best_fact.get("optional_type", "").strip()
        fact_text = best_fact.get(opt_type, "").strip()

        if fact_text and opt_type == "bonus_fact":
            available_options.append("bonus_fact")

        if best_fact.get("follow_up_question") and best_fact["follow_up_question"] not in used_follow_ups:
            available_options.append("follow_up_question")

        if pending_category_insert:
            current_category = pending_category_insert
            pending_category_insert = None
        for header in category_headers:
            if header in text:
                current_category = header
                break
        category = current_category or best_fact.get("category", "").strip()

        def get_closest(cat, cat_dict):
            for key in cat_dict:
                if cat.strip().startswith(key.strip()):
                    return key
            return None

        quote_cat = get_closest(category, quotes_by_category)
        joke_cat  = get_closest(category, jokes_by_category)

        avail_quotes = [q for q in quotes_by_category.get(quote_cat, []) if q not in used_quotes] if quote_cat else []
        avail_jokes  = [j for j in jokes_by_category.get(joke_cat, []) if j not in used_jokes] if joke_cat else []

        if avail_quotes: available_options.append("quote")
        if avail_jokes:  available_options.append("joke")
        if not available_options:
            page_number += 1
            continue

        counts = insert_counts_by_category[category]
        sorted_types = sorted(available_options, key=lambda x: counts.get(x, 0))

        bubble_text = None
        best_type = None

        for insert_type in sorted_types:
            if insert_type == "bonus_fact":
                candidate = best_fact.get("bonus_fact", "").strip()
                if candidate and len(candidate) <= 120:
                    bubble_text = candidate
                    best_type = "bonus_fact"
                    break
            elif insert_type == "follow_up_question":
                candidate = best_fact.get("follow_up_question", "").strip()
                if candidate and candidate not in used_follow_ups and len(candidate) <= 120:
                    bubble_text = candidate
                    used_follow_ups.add(candidate)
                    best_type = "follow_up_question"
                    break
            elif insert_type == "quote":
                for q in avail_quotes:
                    if len(q) <= 120:
                        if ":" in q:
                            speaker, quote_text = q.split(":", 1)
                            bubble_text = f"“{quote_text.strip().strip('“”\"')}” — {speaker.strip()}"
                        else:
                            bubble_text = f"“{q.strip().strip('“”\"')}”"
                        used_quotes.add(q)
                        best_type = "quote"
                        break
                if bubble_text: break
            elif insert_type == "joke":
                for j in avail_jokes:
                    if len(j) <= 120:
                        bubble_text = j
                        used_jokes.add(j)
                        best_type = "joke"
                        break
                if bubble_text: break

        if not bubble_text:
            page_number += 1
            continue

        insert_counts[best_type] += 1
        insert_counts_by_category[category][best_type] += 1

        # layout
        bubble_position = "right" if page_number % 2 == 0 else "left"
        page_width, page_height = page.rect.width, page.rect.height
        margin = 120
        font_size = 9
        line_gap = 3

        max_bubble_width = page_width * 0.75
        padding_inner = 28

        lines = wrap_text_to_two_lines_balanced(
            bubble_text, max_bubble_width - padding_inner, doc_font, font_size
        )
        text_width_estimate = max(doc_font.text_length(line, fontsize=font_size) for line in lines) if lines else 0
        bubble_width = min(text_width_estimate + padding_inner, max_bubble_width)
        line_height = font_size + line_gap
        bubble_height = max(len(lines) * line_height + 12, 32)

        if bubble_position == "right":
            bubble_rect = fitz.Rect(
                page_width - margin - bubble_width,
                page_height - bubble_height - (20 + RAISE_Y),
                page_width - margin,
                page_height - (20 + RAISE_Y)
            )
            tail = [
                fitz.Point(bubble_rect.x1, bubble_rect.y0 + bubble_height / 2 - 6),
                fitz.Point(bubble_rect.x1 + 12, bubble_rect.y0 + bubble_height / 2),
                fitz.Point(bubble_rect.x1, bubble_rect.y0 + bubble_height / 2 + 6),
            ]
        else:
            bubble_rect = fitz.Rect(
                margin,
                page_height - bubble_height - (20 + RAISE_Y),
                margin + bubble_width,
                page_height - (20 + RAISE_Y)
            )
            tail = [
                fitz.Point(bubble_rect.x0, bubble_rect.y0 + bubble_height / 2 - 6),
                fitz.Point(bubble_rect.x0 - 12, bubble_rect.y0 + bubble_height / 2),
                fitz.Point(bubble_rect.x0, bubble_rect.y0 + bubble_height / 2 + 6),
            ]

        # bubble
        draw_custom_rounded_bubble(page, bubble_rect, tail)
        # outline
        try:
            if bubble_position == "right":
                x0, y0 = bubble_rect.x0, bubble_rect.y0
                x1, y1 = bubble_rect.x1, bubble_rect.y1
                outline_path = [
                    fitz.Point(x0, y0), fitz.Point(x1, y0),
                    fitz.Point(x1, tail[0].y), tail[0], tail[1], tail[2],
                    fitz.Point(x1, tail[2].y), fitz.Point(x1, y1),
                    fitz.Point(x0, y1), fitz.Point(x0, y0)
                ]
            else:
                x0, y0 = bubble_rect.x0, bubble_rect.y0
                x1, y1 = bubble_rect.x1, bubble_rect.y1
                outline_path = [
                    fitz.Point(x0, y0), fitz.Point(x1, y0), fitz.Point(x1, y1), fitz.Point(x0, y1),
                    fitz.Point(x0, tail[2].y), tail[2], tail[1], tail[0], fitz.Point(x0, tail[0].y),
                    fitz.Point(x0, y0)
                ]
            page.draw_polyline(points=outline_path, closePath=True, color=(0, 0, 0),
                               fill=None, width=1.5, overlay=True)
        except Exception as e:
            print(f"⚠️ Failed to draw bubble outline: {e}")

        # character image
        image_path = IMAGE_MAP.get(best_type)
        if image_path and page_number % 2 != 0:
            image_path = image_path.replace(".png", "_flipped.png")
        if image_path and os.path.exists(image_path):
            img_w = img_h = 85
            outer_margin = 30
            y1 = page_height - RAISE_Y
            y0 = y1 - img_h
            if bubble_position == "right":
                x1 = page_width - outer_margin
                x0 = x1 - img_w
            else:
                x0 = outer_margin
                x1 = x0 + img_w
            img_rect = fitz.Rect(x0, y0, x1, y1)
            try:
                page.insert_image(img_rect, filename=image_path, overlay=True)
            except Exception as e:
                print(f"⚠️ Failed to insert image: {e}")

        # text
        wrapped_text = "\n".join(lines)
        page.insert_textbox(
            bubble_rect, wrapped_text, fontsize=9, fontname=FONT_NAME,
            color=(0, 0, 0), align=1
        )

        page_number += 1

    os.makedirs(os.path.dirname(out_pdf) or ".", exist_ok=True)
    doc.save(out_pdf)
    doc.close()
    print(f"✅ Bubbled PDF saved to: {out_pdf}")

# =========================
# Runner
# =========================
if __name__ == "__main__":
    FINAL_ROOT = r"C:\Personal\What Happened On... (The Complete Collection)"
    FACTS_ROOT = r"C:\Personal\factBook\facts\new fact grabber\6_final"

    dir_re = re.compile(r'^(?P<num>\d+)_([A-Za-z]+)_(\d{1,2})$')
    index = {}
    for entry in os.listdir(FINAL_ROOT):
        m = dir_re.match(entry)
        if not m:
            continue
        num = int(m.group("num"))
        parts = entry.split("_")
        if len(parts) >= 3:
            month_day = f"{parts[1]}_{parts[2]}"
            index[num] = month_day

    if not index:
        raise SystemExit("❌ No valid <num>_<Month>_<Day> folders under FINAL.")

    user_in = input("Type the book number (e.g., 89): ").strip()
    if not user_in.isdigit():
        raise SystemExit("❌ Please enter a number, e.g., 89")
    pick = int(user_in)
    if pick not in index:
        hint = ", ".join(str(n) for n in sorted(index.keys())[:12])
        raise SystemExit(f"❌ {pick} not found. Known numbers start like: {hint} …")

    month_day = index[pick]
    folder = f"{pick}_{month_day}"
    final_dir = os.path.join(FINAL_ROOT, folder)
    build_dir = os.path.join(final_dir, "build_docs")

    # inputs (prefer 2.pdf, then 1.pdf, then global fallback)
    candidates = [
        os.path.join(build_dir, "2.pdf"),
        os.path.join(build_dir, "1.pdf"),
        r"C:\Personal\factBook\books\finishedBook.pdf",
    ]
    pdf_in = next((p for p in candidates if os.path.exists(p)), None)
    if not pdf_in:
        raise SystemExit("❌ No input PDF found (tried build_docs\\2.pdf, 1.pdf, books\\finishedBook.pdf)")

    # facts (prefer <num>_<Month>_<Day>_Final.json, then <Month>_<Day>_Final.json)
    json_candidates = [
        os.path.join(FACTS_ROOT, f"{pick}_{month_day}_Final.json"),  # e.g. 89_March_29_Final.json
        os.path.join(FACTS_ROOT, f"{month_day}_Final.json"),         # fallback: March_29_Final.json
    ]
    json_path = next((p for p in json_candidates if os.path.exists(p)), None)
    if not json_path:
        raise SystemExit("❌ Facts JSON not found. Tried:\n  " + "\n  ".join(json_candidates))

    # outputs
    out_build_3 = os.path.join(build_dir, "3.pdf")               # full manuscript in build_docs
    out_final   = os.path.join(final_dir, "full_manuscript.pdf") # compressed in top folder

    print(f"📄 Input PDF:   {pdf_in}")
    print(f"🧾 Facts JSON:  {json_path}")
    print(f"🧱 Build 3.pdf: {out_build_3}")
    print(f"📦 Final:       {out_final}")

    # 1) add bubbles → build_docs\3.pdf
    add_bubbles(pdf_in, json_path, out_build_3)

    # 2) compress → full_manuscript.pdf
    try:
        compress_with_ghostscript(out_build_3, out_final,
                                  jpeg_quality=100, color_res=300, gray_res=300, mono_res=600)
        print(f"🗜️ Compressed PDF written to:\n{out_final}")
    except FileNotFoundError:
        print("ℹ️  Ghostscript not found — skipping compression.")
