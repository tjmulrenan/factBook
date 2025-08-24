import fitz  # PyMuPDF
import json5 as json
import os
import re
import random
from collections import defaultdict

INCH = 72
BLEED_IN = 0.125
SAFE_IN = 0.25
SAFE_PAD = int((BLEED_IN + SAFE_IN) * INCH)   # 27 pt  (use 36 if you want extra cushion)
SIDE_PAD = max(SAFE_PAD, 36)                  # bump side pad a touch if you like
BOTTOM_PAD = max(SAFE_PAD, 36)
TOP_PAD = max(SAFE_PAD, 36)

# --- Font Setup ---
font_path = r"C:\Users\timmu\Documents\repos\Factbook Project\fonts\Baloo2-Bold.ttf"
font_name = "Baloo2Bold"  # No spaces — required for PyMuPDF
RAISE_Y = 25  # move bubble + character image 20pt higher (toward the top)

# --- Utility: Text Wrapping ---
def wrap_text_to_two_lines_balanced(text, max_width, font, fontsize):
    words = text.split()
    best_split = None
    best_diff = float('inf')

    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        width1 = font.text_length(line1, fontsize=fontsize)
        width2 = font.text_length(line2, fontsize=fontsize)

        if width1 <= max_width and width2 <= max_width:
            diff = abs(width1 - width2)
            if diff < best_diff:
                best_diff = diff
                best_split = (line1, line2)

    if best_split:
        return list(best_split)
    else:
        return [text] if font.text_length(text, fontsize=fontsize) <= max_width else [text[:90] + "..."]

# --- Utility: JSON Fix for Trailing Commas ---
def fix_trailing_commas(json_text):
    json_text = re.sub(r',(\s*])', r'\1', json_text)
    json_text = re.sub(r',(\s*})', r'\1', json_text)
    return json_text

# --- Fix and Load Quotes ---
with open("quotes/generatedquotes.json", "r", encoding="utf-8") as f:
    raw = f.read()
fixed = fix_trailing_commas(raw)

with open(r"C:\Users\timmu\Documents\repos\Factbook Project\quotes\generatedquotes.json", "r", encoding="utf-8") as f:
    quotes_by_category = json.load(f)

# --- Load Jokes ---
with open(r"C:\Users\timmu\Documents\repos\Factbook Project\jokes\generatedJokes.json", "r", encoding="utf-8") as f:
    jokes_by_category = json.load(f)

# --- Track used items globally ---
used_quotes = set()
used_jokes = set()
used_bonus_facts = set()
used_follow_ups = set()

# --- Per-category insert counts ---
insert_counts_by_category = defaultdict(lambda: {
    "quote": 0,
    "joke": 0,
    "bonus_fact": 0,
    "follow_up_question": 0
})

# --- Track overall insert counts ---
insert_counts = {
    "quote": 0,
    "joke": 0,
    "bonus_fact": 0,
    "follow_up_question": 0
}

# --- Category headers from both sources ---
category_headers = list(set(quotes_by_category.keys()) | set(jokes_by_category.keys()))
current_category = None
pending_category_insert = None

# --- Image paths ---
image_map = {
    "bonus_fact": r"C:\Users\timmu\Documents\repos\Factbook Project\pics\bonusFact.png",
    "follow_up_question": r"C:\Users\timmu\Documents\repos\Factbook Project\pics\followUpQuestion.png",
    "quote": r"C:\Users\timmu\Documents\repos\Factbook Project\pics\quote.png",
    "joke": r"C:\Users\timmu\Documents\repos\Factbook Project\pics\joke.png"
}

# --- File Paths ---
pdf_path = r"C:\Users\timmu\Documents\repos\Factbook Project\books\finishedBook.pdf"
json_path = r"C:\Users\timmu\Documents\repos\Factbook Project\facts\new fact grabber\6_final\March_29_Final.json"
output_path = r"C:\Users\timmu\Documents\repos\Factbook Project\books\finishedBook_with_speechbubbles.pdf"


def draw_custom_rounded_bubble(page, bubble_rect, corner_radius, tail_points, fill, stroke, fill_opacity=1.0, stroke_opacity=1.0, width=2):
    # ❌ No rounded rect support — fallback to standard rectangle
    page.draw_rect(
        bubble_rect,
        fill=fill,
        color=stroke,
        width=width,
        overlay=True,
        fill_opacity=fill_opacity,
        stroke_opacity=stroke_opacity
    )

    # ✅ Tail triangle
    try:
        page.draw_polyline(
            points=tail_points,
            closePath=True,
            fill=fill,
            color=stroke,
            width=width,
            fill_opacity=fill_opacity,
            stroke_opacity=stroke_opacity
        )
    except Exception as e:
        print(f"⚠️ Failed to draw tail: {e}")

# --- Load JSON Facts ---
if not os.path.exists(json_path):
    raise FileNotFoundError(f"❌ JSON file not found at: {json_path}")

with open(json_path, "r", encoding="utf-8") as f:
    facts = json.load(f)

title_to_fact = {fact["title"]: fact for fact in facts}

if not os.path.exists(pdf_path):
    raise FileNotFoundError(f"❌ PDF not found at: {pdf_path}")

doc = fitz.open(pdf_path)

original_page_count = len(doc)
page_number = 3
doc_font = fitz.Font(fontfile=font_path)
insertion_slots = []

while page_number < original_page_count:
    page = doc.load_page(page_number)
    page.insert_font(fontname=font_name, fontfile=font_path)

    print(f"📄 Processing original page {page_number + 1} of {original_page_count}")

    try:
        text = page.get_text()
    except Exception as e:
        print(f"⚠️ Could not extract text from page {page_number + 1}: {e}")
        page_number += 1
        continue

    # 🔍 Detect and log category headers
    detected_category = None
    for header in category_headers:
        if header in text:
            detected_category = header
            print(f"🔎 Found category header '{header}' on page {page_number + 1}")
            pending_category_insert = header  # 🕒 Store for next page
            break


    def normalize(s):
        return re.sub(r'\s+', ' ', s).strip().lower()

    normalized_text = normalize(text)

    matched_facts = []
    for title, fact in title_to_fact.items():
        if normalize(title) in normalized_text:
            print(f"  ✅ Matched normalized title: {title}")
            matched_facts.append(fact)

    if not matched_facts:
        print(f"❌ No matches found on page {page_number + 1}.")
        print("🧾 First 300 characters of page text:")
        print(text[:300])
        page_number += 1
        continue

    best_fact = random.choice(matched_facts)
    available_options = []
    bubble_text = None
    best_type = None
    image_key = None

    opt_type = best_fact.get("optional_type", "").strip()
    fact_text = best_fact.get(opt_type, "").strip()

    # ✅ Only include bonus_fact if it's valid and available
    if fact_text and opt_type == "bonus_fact":
        available_options.append("bonus_fact")

    # ✅ Include follow-up if not yet used
    if best_fact.get("follow_up_question") and best_fact["follow_up_question"] not in used_follow_ups:
        available_options.append("follow_up_question")

    # Detect category (quote/joke fallback)
    if pending_category_insert:
        current_category = pending_category_insert
        pending_category_insert = None

    for header in category_headers:
        if header in text:
            current_category = header
            print(f"🔎 Found category header '{header}' on page {page_number + 1}")
            break

    category = current_category or best_fact.get("category", "").strip()

    def get_closest_category(cat, cat_dict):
        for key in cat_dict:
            if cat.strip().startswith(key.strip()):
                return key
        return None

    quote_cat = get_closest_category(category, quotes_by_category)
    joke_cat = get_closest_category(category, jokes_by_category)

    available_quotes = [q for q in quotes_by_category.get(quote_cat, []) if q not in used_quotes] if quote_cat else []
    available_jokes = [j for j in jokes_by_category.get(joke_cat, []) if j not in used_jokes] if joke_cat else []

    if available_quotes:
        available_options.append("quote")
    if available_jokes:
        available_options.append("joke")

    if not available_options:
        page_number += 1
        continue

    # ⚖️ Sort insert options by least-used in this category so far
    counts = insert_counts_by_category[category]
    sorted_types = sorted(available_options, key=lambda x: counts.get(x, 0))
    bubble_text = None
    best_type = None
    image_key = None

    print(f"🔍 Available options for category '{category}': {available_options}")
    # Prioritize insert types by least-used
    counts = insert_counts_by_category[category]
    sorted_types = sorted(available_options, key=lambda x: counts.get(x, 0))

    for insert_type in sorted_types:
        if insert_type == "bonus_fact":
            candidate = best_fact.get("bonus_fact", "").strip()
            if candidate and len(candidate) <= 120:
                bubble_text = candidate
                best_type = "bonus_fact"
                image_key = "bonus_fact"
                break

        elif insert_type == "follow_up_question":
            candidate = best_fact.get("follow_up_question", "").strip()
            if candidate and candidate not in used_follow_ups and len(candidate) <= 120:
                bubble_text = candidate
                used_follow_ups.add(candidate)
                best_type = "follow_up_question"
                image_key = "follow_up_question"
                break

        elif insert_type == "quote":
            for q in available_quotes:
                if len(q) <= 120:
                    # Try to split at the first colon (e.g., 'MLK: "I have a dream."')
                    if ":" in q:
                        speaker, quote_text = q.split(":", 1)
                        speaker = speaker.strip()
                        quote_text = quote_text.strip().strip('"“”')  # clean quotes
                        bubble_text = f"“{quote_text}” — {speaker}"
                    else:
                        bubble_text = f"“{q.strip().strip('“”')}”"
                    used_quotes.add(q)
                    best_type = "quote"
                    image_key = "quote"
                    break
            if bubble_text:
                break

        elif insert_type == "joke":
            for j in available_jokes:
                if len(j) <= 120:
                    bubble_text = j
                    used_jokes.add(j)
                    best_type = "joke"
                    image_key = "joke"
                    break
            if bubble_text:
                break



    if not bubble_text:
        page_number += 1
        continue


    insert_counts[best_type] += 1
    insert_counts_by_category[category][best_type] += 1
    print(f"📝 Page {page_number + 1}: inserting '{best_type}' bubble — text: {bubble_text[:50]}...")

    bubble_position = "right" if page_number % 2 == 0 else "left"
    page_width, page_height = page.rect.width, page.rect.height
    margin = 120
    font_size = 9
    corner_radius = 50

    # Bubble sizing (dynamic)
    max_bubble_width = page_width * 0.75
    padding_inner = 28        # inner horizontal padding inside bubble
    line_gap = 3              # space between lines

    # Wrap with the new font size
    lines = wrap_text_to_two_lines_balanced(
        bubble_text, max_bubble_width - padding_inner, doc_font, font_size
    )

    # Measure text width
    text_width_estimate = max(
        doc_font.text_length(line, fontsize=font_size) for line in lines
    ) if lines else 0

    # Final bubble width / height
    bubble_width = min(text_width_estimate + padding_inner, max_bubble_width)
    line_height = font_size + line_gap
    bubble_height = len(lines) * line_height + 12   # 16 = top/bottom padding
    bubble_height = max(bubble_height, 32)          # don’t let it get too tiny

    # Tail scales with font so proportions look right
    tail_half_thickness = max(4, int(font_size * 0.45))   # ~5 at 11pt
    tail_len = max(10, int(font_size * 1.0))              # ~11 at 11pt

    
    # 🧼 Clean final width calculation already done — now log it
    char_count = sum(len(line) for line in lines)
    print(f"🔠 Text wrapped to {len(lines)} lines, {char_count} chars — bubble width: {bubble_width:.1f} pt")



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




    draw_custom_rounded_bubble(
        page,
        bubble_rect,
        corner_radius,
        tail,
        fill=(1, 1, 1),
        stroke=None,              # ✅ No stroke color
        fill_opacity=0.85,
        stroke_opacity=0,         # ✅ Fully transparent stroke
        width=0                   # ✅ No stroke width
    )
    
    try:
        if bubble_position == "right":
            # RIGHT SIDE OUTLINE (even pages)
            x0, y0 = bubble_rect.x0, bubble_rect.y0
            x1, y1 = bubble_rect.x1, bubble_rect.y1

            outline_path = [
                fitz.Point(x0, y0),            # top-left
                fitz.Point(x1, y0),            # top-right
                fitz.Point(x1, tail[0].y),     # right edge to top of tail
                tail[0],                       # tail top corner
                tail[1],                       # tail tip
                tail[2],                       # tail bottom corner
                fitz.Point(x1, tail[2].y),     # back to right edge below tail
                fitz.Point(x1, y1),            # bottom-right
                fitz.Point(x0, y1),            # bottom-left
                fitz.Point(x0, y0),            # close
            ]

        else:
            # LEFT SIDE OUTLINE (odd pages)
            x0, y0 = bubble_rect.x0, bubble_rect.y0
            x1, y1 = bubble_rect.x1, bubble_rect.y1

            outline_path = [
                fitz.Point(x0, y0),            # top-left
                fitz.Point(x1, y0),            # top-right
                fitz.Point(x1, y1),            # bottom-right
                fitz.Point(x0, y1),            # bottom-left
                fitz.Point(x0, tail[2].y),     # up to base of tail
                tail[2],                       # tail bottom corner
                tail[1],                       # tail tip
                tail[0],                       # tail top corner
                fitz.Point(x0, tail[0].y),     # rejoin bubble
                fitz.Point(x0, y0),            # close
            ]

        # Now draw the unified outline
        page.draw_polyline(
            points=outline_path,
            closePath=True,
            color=(0, 0, 0),
            fill=None,
            width=1.5,
            overlay=True
        )

    except Exception as e:
        print(f"⚠️ Failed to draw bubble outline: {e}")

    



    image_path = image_map.get(best_type)
    if image_path and page_number % 2 != 0:
        image_path = image_path.replace(".png", "_flipped.png")

    # Check and insert image
    if image_path and os.path.exists(image_path):
        img_width = img_height = 85  # was 90 → ~20% smaller
        outer_margin = 30
        bottom_margin = RAISE_Y

        y1 = page_height - bottom_margin
        y0 = y1 - img_height

        if bubble_position == "right":
            x1 = page_width - outer_margin
            x0 = x1 - img_width
        else:
            x0 = outer_margin
            x1 = x0 + img_width

        img_rect = fitz.Rect(x0, y0, x1, y1)

        try:
            page.insert_image(img_rect, filename=image_path, overlay=True)
        except Exception as e:
            print(f"⚠️ Failed to insert image: {e}")



    # Register the font directly with the page (so PyMuPDF can embed it)
    font_path = r"C:\Users\timmu\Documents\repos\Factbook Project\fonts\Baloo2-Bold.ttf"
    font_name = "Baloo2Bold"  # No spaces — required for PyMuPDF
    page.insert_font(fontname=font_name, fontfile=font_path)

    # Now use that name in the textbox
    wrapped_text = "\n".join(lines)  # Use your already-calculated wrapped lines
    page.insert_textbox(
        bubble_rect,
        wrapped_text,
        fontsize=font_size,
        fontname=font_name,
        color=(0, 0, 0),
        align=1
    )
    page_number += 1


# save finished book
doc.save(output_path)
doc.close()

print("\n📊 Insert Summary:")
for k, v in insert_counts.items():
    print(f"  {k.title()}: {v}")

print(f"✅ New PDF with speech bubbles saved to:\n{output_path}")

# --- Optional: tighten structure only (no DPI change) ---
# If you don’t want Ghostscript, you can instead do:
# doc.save(output_path, deflate=True, clean=True, garbage=4)

import subprocess, shutil, os, glob, datetime, time

def _find_gs_exe():
    pinned = r"C:\Program Files\gs\gs10.05.1\bin\gswin64c.exe"
    if os.path.exists(pinned): return pinned
    gs = shutil.which("gswin64c") or shutil.which("gs")
    if gs: return gs
    for path in sorted(glob.glob(r"C:\Program Files\gs\gs*\bin\gswin64c.exe"), reverse=True):
        if os.path.exists(path): return path
    return None

def _unique_out(path):
    base, ext = os.path.splitext(path)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{base}_compressed_{ts}{ext}"

def compress_with_ghostscript(inp_pdf, out_pdf=None,
                              jpeg_quality=100, color_res=300, gray_res=300, mono_res=600):
    """
    If out_pdf is None, writes to <inp>_compressed_YYYYmmdd-HHMMSS.pdf
    """
    gs = _find_gs_exe()
    if not gs:
        raise FileNotFoundError("Ghostscript not found.")

    if out_pdf is None:
        out_pdf = _unique_out(inp_pdf)

    out_dir = os.path.dirname(out_pdf) or "."
    os.makedirs(out_dir, exist_ok=True)

    # Don’t try to delete existing; pick a fresh name to avoid lock issues.
    if os.path.exists(out_pdf):
        out_pdf = _unique_out(out_pdf)

    args = [
        gs,
        "-dBATCH", "-dNOPAUSE", "-dQUIET", "-dNOSAFER",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        "-dPDFSETTINGS=/printer",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dAutoRotatePages=/None",

        "-dDownsampleColorImages=true",
        f"-dColorImageResolution={color_res}",
        "-dColorImageDownsampleType=/Average",

        "-dDownsampleGrayImages=true",
        f"-dGrayImageResolution={gray_res}",
        "-dGrayImageDownsampleType=/Average",

        "-dDownsampleMonoImages=true",
        f"-dMonoImageResolution={mono_res}",
        "-dMonoImageDownsampleType=/Subsample",

        "-dEncodeColorImages=true",
        "-dEncodeGrayImages=true",
        f"-dJPEGQ={jpeg_quality}",

        f"-sOutputFile={out_pdf}",
        inp_pdf,
    ]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Ghostscript failed.\n"
            f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n\n"
            f"Command:\n{' '.join(args)}"
        )
    return out_pdf

# === Use it ===
final_pdf = output_path  # your PyMuPDF output
compressed_pdf = compress_with_ghostscript(final_pdf,
                                           jpeg_quality=100,
                                           color_res=300, gray_res=300, mono_res=600)
print(f"🗜️ Compressed PDF written to:\n{compressed_pdf}")
