import hashlib
import json
import logging
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CROSSWORD_DIR, WORDSEARCH_DIR, HOL_DAY_DIR, FINAL_FACTS_DIR, PICTURES_DIR

from PIL import Image
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, Flowable, HRFlowable, Image as RLImage,
)

from book.flowables import (
    BLEED_PT, CUSTOM_BLUE, CUSTOM_PAGE_SIZE, MyDocTemplate,
    MidGapRule, OverlayRule, PAGE_H, PAGE_W,
    TransparentBox, FixedBottomTransparentBox,
)


def stable_shuffle(seq, seed_str):
    rng = random.Random(int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16))
    out = list(seq)
    rng.shuffle(out)
    return out


def extract_fact_text(rec: dict) -> str:
    return rec.get("fact") or rec.get("story") or rec.get("original") or rec.get("title") or ""


# ➕ ADD THIS HELPER (right below extract_fact_text)
def normalize_categories(raw):
    """
    Returns a list of category strings from whatever the JSON has:
    - None  -> ["Other"]
    - "Days That Slay" -> ["Days That Slay"]
    - [{"name":"Days That Slay"}, "Beyond Earth"] -> ["Days That Slay", "Beyond Earth"]
    - Any weird type -> coerced to string
    """
    if raw is None:
        return ["Other"]
    if isinstance(raw, (str, dict)):
        raw = [raw]
    out = []
    for item in raw:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif isinstance(item, dict):
            for key in ("name", "title", "label", "category", "value"):
                v = item.get(key)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                    break
            else:
                out.append(str(item))
        else:
            out.append(str(item))
    return out or ["Other"]


def _collect_answer_images(categories, base_folder, suffix):
    """
    Build [(category_title, image_path), ...] only for files that exist.
    suffix should include leading underscore if needed, e.g. '_answers.png'
    """
    items = []
    for category in categories:
        bg_key = CATEGORY_BACKGROUNDS.get(category)
        if not bg_key:
            continue
        p = os.path.join(base_folder, f"{bg_key.lower()}{suffix}")
        if os.path.exists(p):
            items.append((category, p))
        else:
            logging.warning(f"❌ Missing answers image: {p}")
    return items


def _answers_grid(elements, styles, title_text, items, cell_width=175, rows_per_page=2, cols_per_page=2):
    """
    Thin wrapper so the 'real' answers pages look the same as preview pages.
    Uses the same paginator/scaler as _answers_preview_grid.
    """
    if not items:
        elements.append(PageBreak())
        elements.append(TransparentBox(f"{title_text} not found.", styles['story'], alpha=0.85))
        return

    _answers_preview_grid(
        elements,
        title_text=title_text,
        styles=styles,
        image_paths=items,
        cell_width=cell_width,
        rows_per_page=rows_per_page,
        cols_per_page=cols_per_page
    )


def _trivia_answers_grid(elements, styles, qa_pairs, cell_width=175, rows_per_page=2, cols_per_page=2):
    """
    Paginate a grid of (question + answer) cells like the answers preview.
    qa_pairs: list of tuples -> (question, answer)
    """
    # Build cells (white text, centered title vibe)
    cells = []
    for i, (q, a) in enumerate(qa_pairs, 1):
        # White text to pop on your dark answers backgrounds
        qa_para = Paragraph(
            f"<b>{i}.</b> {q}<br/><b>Answer:</b> {a}",
            ParagraphStyle(
                "TriviaAnswersCell",
                parent=styles['trivia_answers'],
                textColor=colors.white,    # key for dark background
                fontSize=10,
                leading=12,
                spaceAfter=0,
                spaceBefore=0
            )
        )
        # Wrap in a TransparentBox like the preview cells (no offset hacks)
        box = TransparentBox(
            [qa_para],
            styles['trivia_answers'],
            width=cell_width,
            padding=8,
            alpha=0.85,
            border=False
        )
        cells.append(box)

    # Paginate into pages of rows_per_page x cols_per_page
    page_capacity = rows_per_page * cols_per_page
    for i in range(0, len(cells), page_capacity):
        block = cells[i:i + page_capacity]

        # Build rows
        rows = []
        for r in range(0, len(block), cols_per_page):
            row = block[r:r + cols_per_page]
            while len(row) < cols_per_page:
                row.append(Spacer(1, 1))  # pad empty cells
            rows.append(row)

        # Ensure exactly rows_per_page rows per page
        while len(rows) < rows_per_page:
            rows.append([Spacer(1, 1) for _ in range(cols_per_page)])

        table = Table(rows, colWidths=[cell_width]*cols_per_page, hAlign='CENTER')
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            # ('GRID', (0,0), (-1,-1), 0.5, colors.grey),  # debug if needed
        ]))
        elements.append(Spacer(1, 12))
        elements.append(table)


def _answers_preview_grid(elements, title_text, styles, image_paths, cell_width=175, rows_per_page=2, cols_per_page=2):
    """
    Paginate a 2x2 grid of (title + image) cells across as many pages as needed.
    image_paths: list of tuples -> (category_title, image_path)
    """
    # Title
    elements.append(PageBreak())
    elements.append(TransparentBox(title_text, styles['cat_title'], alpha=0.85))
    elements.append(Spacer(1, 12))
    elements.append(Spacer(1, 12))

    # Build cells
    cells = []
    for cat_title, img_path in image_paths:
        try:
            img_reader = ImageReader(img_path)
            ow, oh = img_reader.getSize()

            # keep aspect by fixing width, adapt height
            max_w = float(cell_width)
            # keep some headroom; target around 150–170 high usually
            scale = max_w / float(ow)
            new_w = max_w
            new_h = oh * scale

            # Caption (white text so it pops on your dark backgrounds)
            title_para = Paragraph(cat_title, ParagraphStyle(
                "AnswersPreviewTitle",
                fontName="Baloo2-Bold",
                fontSize=12,
                leading=14,
                alignment=TA_CENTER,
                spaceAfter=4,
                textColor=colors.white
            ))
            image = RLImage(img_path, width=new_w, height=new_h)

            cells.append([title_para, Spacer(1, 4), image])
        except Exception as e:
            logging.warning(f"❌ Could not load answers preview image for {cat_title}: {e}")

    # Pagination into pages of (rows_per_page x cols_per_page)
    page_capacity = rows_per_page * cols_per_page
    for i in range(0, len(cells), page_capacity):
        block = cells[i:i + page_capacity]
        # build rows
        rows = []
        for r in range(0, len(block), cols_per_page):
            row = block[r:r + cols_per_page]
            while len(row) < cols_per_page:
                row.append([Spacer(1, 1)])  # pad empty
            rows.append(row)

        # ensure exactly rows_per_page rows per page (pad if needed)
        while len(rows) < rows_per_page:
            rows.append([[Spacer(1, 1)] for _ in range(cols_per_page)])

        table = Table(rows, colWidths=[cell_width] * cols_per_page, hAlign='CENTER')
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            # ('GRID', (0,0), (-1,-1), 0.5, colors.grey),  # enable if you want gridlines
        ]))
        elements.append(Spacer(1, 12))
        elements.append(table)

CATEGORY_BACKGROUNDS = {
    "Today's Vibe Check": "todays_vibe_check",
    "History's Mic Drop Moments": "history_mic_drop_moments",
    "World Shakers & Icon Makers": "world_shakers_and_icon_makers",
    "Big Brain Energy": "big_brain_energy",
    "Beyond Earth": "beyond_earth",
    "Creature Feature": "creature_feature",
    "Vibes, Beats & Brushes": "vibes_beats_and_brushes",
    "Days That Slay": "days_that_slay",
    "Full Beast Mode": "full_beast_mode",
    "Mother Nature's Meltdowns": "mother_natures_meltdowns",
    "The What Zone": "the_what_zone",
}

CATEGORY_DESCRIPTIONS = {
    "Today's Vibe Check": "What's the mood today? Think weird weather, dramatic animals, and random seasonal chaos.",
    "History's Mic Drop Moments": "Big turning points that made the world go 'WHAAAT?!' — epic wars, revolutions, and game-changing deals.",
    "World Shakers & Icon Makers": "Meet the legends who changed everything — rulers, rebels, geniuses, and icons who made their mark.",
    "Big Brain Energy": "Mind-blowing inventions, wild science, genius ideas, and epic 'aha!' moments.",
    "Beyond Earth": "Stuff that's out of this world — space launches, alien signals, meteor showers, and cosmic mysteries.",
    "Creature Feature": "Fur, fins, feathers and fangs — meet nature's wildest creatures and their coolest superpowers.",
    "Vibes, Beats & Brushes": "Where art meets attitude — music, dance, trends, and creativity that made the world pop.",
    "Days That Slay": "Holidays and celebrations that bring the party — from the wacky to the wonderful.",
    "Full Beast Mode": "Sports, stunts, and mega records — where humans (and animals) go all out.",
    "Mother Nature's Meltdowns": "Earth doing the most — volcanoes, wild weather, and nature's power on full blast.",
    "The What Zone": "Wait... what? The strangest, silliest, and most head-scratching facts you never knew you needed.",
}


final_categories_dict = {}  # For category-to-fact-id export

global_answers = []  # Collect answers to render later


def find_vibe_json_path(base_dir, month, day_str):
    """
    Return full path to the vibe JSON for Month/Day, handling files like:
      - 3_January_3_Facts.json
      - January_3_Facts.json   (legacy)
    """
    day_num = str(int(day_str))  # normalize '03' -> '3'
    candidates = []
    patts = [
        rf"^\d+_{re.escape(month)}_{day_num}_Facts\.json$",
        rf"^{re.escape(month)}_{day_num}_Facts\.json$",
    ]
    regexes = [re.compile(p, re.IGNORECASE) for p in patts]
    try:
        for fname in os.listdir(base_dir):
            for rx in regexes:
                if rx.match(fname):
                    candidates.append(os.path.join(base_dir, fname))
                    break
    except FileNotFoundError:
        logging.warning(f"🚫 Vibe base folder not found: {base_dir}")
        return None

    if not candidates:
        logging.warning(f"🚫 No vibe file found for {month} {day_num} in {base_dir}")
        return None

    # Prefer the one with a numeric prefix if both exist
    candidates.sort(key=lambda p: (0 if re.match(r"^\d+_", os.path.basename(p)) else 1, p.lower()))
    return candidates[0]


def is_kid_friendly(rec: dict) -> bool:
    return bool(
        rec.get("kid_friendly") is True
        or rec.get("suitable_for_8_to_12_year_old") is True
        or rec.get("is_kid_friendly") is True
    )


def build_elements(facts, styles, date_str, category_pages=None):
    elements = []
    global global_answers
    global_answers = []  # ⬅️ Reset before accumulating again
    num_facts = len(facts)

    # ✅ Insert only the hidden marker and a page break — no visible content
    elements += [
        Paragraph("__COVER_PAGE__", ParagraphStyle("HiddenCoverMarker", fontSize=0, textColor=colors.white)),
        PageBreak()
    ]

    intro_text = f"""
        Hey you! Yeah, you with the excellent taste in books. Whether today's your birthday, your dog's birthday, or just a totally random spin of the calendar wheel, this book is here to make your day 100% more interesting.

        I'm TJ: your guide, fact hoarder, and proud human from Saffron Walden (it's a town, not a wizard spell — I checked). I've spent way too much time digging through history books, science sites, fun facts, and the weird corners of the internet so you don't have to.

        So the big question is: <b>What happened on {date_str}?</b>

        Flip the page, trust the chaos, and become the class trivia weapon your teacher never saw coming.

        <br/><br/><i>P.S. I'll be hiding at the start of each chapter...<br/>Can you find me?</i>
        <br/><br/><b>— TJ</b>
    """


    elements.append(Paragraph(
        "__INTRO_PAGE__",
        ParagraphStyle("HiddenIntroMarker", fontSize=0, textColor=colors.white)
    ))
    elements += [
        TransparentBox("Before we begin!", styles['intro_header'], alpha=0.85),
        TransparentBox(intro_text.strip(), styles['intro'], alpha=0.85)
    ]

    if category_pages:
        # elements.append(PageBreak())
        elements.append(Paragraph(
            "__TOC_PAGE__",
            ParagraphStyle("HiddenTOCMarker", fontSize=0, textColor=colors.grey)
        ))

        filtered_category_pages = [
            (cat, pg) for cat, pg in category_pages
            if not cat.startswith("__TRIVIA_START__")
            and "Trivia Time!" not in cat
            and "Questions" not in cat
            and "Answers" not in cat
            and "__" not in cat  # catch any other hidden markers
        ]

        toc_data = [
            [Paragraph(cat, styles['toc_item']), Paragraph(str(pg), styles['toc_item'])]
            for cat, pg in filtered_category_pages
        ]

        table = Table(toc_data, colWidths=[300, 20], hAlign='LEFT')
        row_h = styles['toc_item'].leading + 10   # tweak the +10 to taste (e.g., 8–12)

        table = Table(
            toc_data,
            colWidths=[300, 20],
            rowHeights=[row_h] * len(toc_data),
            hAlign='LEFT'
        )

        table.setStyle(TableStyle([
            ('FONTNAME',   (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE',   (0, 0), (-1, -1), 12),
            ('ALIGN',      (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING',(0,0),(-1,-1), 0),
            ('LEFTPADDING',(0, 0), (-1, -1), 0),
            ('RIGHTPADDING',(0,0), (-1, -1), 0),
            ('LINEBELOW',  (0, 0), (-1, -2), 0.25, colors.darkgrey)
        ]))

        # ⛔ Force TOC to stay together on one page
        toc_block = KeepTogether([
            # Hidden marker before the table
            Paragraph("__TOC_PAGE__", ParagraphStyle("HiddenTOCMarker", fontSize=0, textColor=colors.grey)),

            TransparentBox("<para align='center'><b>Table of Contents</b></para>", styles['toc_title'], alpha=0.85),

            # ✅ Table wrapped in TransparentBox
            TransparentBox(table, styles['story'], alpha=0.85),

            # Hidden end marker
            Paragraph("__TOC_END__", ParagraphStyle("HiddenTOCEndMarker", fontSize=0, textColor=colors.white)),

        ])


        elements.append(toc_block)
        elements.append(PageBreak())


    # 🌤️ Today's Vibe Check Section

    # Estimate vertical space like category headers
    page_height = CUSTOM_PAGE_SIZE[1]
    estimated_content_height = 180
    spacer_height = max(0, (page_height - estimated_content_height) / 2 - 50)

    # Vibe Check intro in transparent boxes
    vibe_intro = KeepTogether([
        Paragraph("<para align='center'><b>Today's Vibe Check</b></para>", styles['category']),
    ])
    elements.append(vibe_intro)

    elements.append(PageBreak())


    try:
        month, day = date_str.split()
        day = ''.join(filter(str.isdigit, day))

        vibe_base = str(HOL_DAY_DIR)
        vibe_path = find_vibe_json_path(vibe_base, month, day)

        if not vibe_path:
            elements.append(Paragraph("Oops! Vibe Check facts couldn't load.", styles['story']))
        else:
            with open(vibe_path, "r", encoding="utf-8") as f:
                vibe_facts = json.load(f)

            kid_facts = [rec for rec in vibe_facts if is_kid_friendly(rec)]

            if kid_facts:
                pad = 5
                gap_leading = styles['story'].leading
                offset_up = pad + gap_leading * (-0.3)
                line_thickness = 1.2
                line_color = colors.darkgrey

                for idx, fact in enumerate(kid_facts):
                    text = extract_fact_text(fact).strip()
                    story_box = TransparentBox(
                        Paragraph(f"{text}<br/>", styles['story']),
                        styles['story'],
                        alpha=0.85,
                        padding=pad,
                        inner_spacing=0
                    )
                    elements.append(story_box)

                    if idx < len(kid_facts) - 1:
                        elements.append(OverlayRule(
                            target_width=350 - 2*pad,
                            thickness=line_thickness,
                            color=line_color,
                            inset=pad,
                            offset_up=offset_up
                        ))
            else:
                elements.append(Paragraph("No kid-friendly facts available today.", styles['story']))

    except Exception as e:
        logging.warning(f"🚫 Could not load Today's Vibe Check facts: {e}")
        elements.append(Paragraph("Oops! Vibe Check facts couldn't load.", styles['story']))

    # Categorize facts (robust to non-string category entries)
    categories = {}
    leftover = []

    # optional: quick diagnostic to log the first offending record, if any
    for i, fact in enumerate(facts, 1):
        raw = fact.get("categories")
        items = raw if isinstance(raw, (list, tuple)) else [raw]
        bad = [type(x).__name__ for x in items if x is not None and not isinstance(x, (str, dict))]
        if any(isinstance(x, dict) for x in items) or bad:
            logging.debug(f"🧪 Category shapes for id={fact.get('id')}: {raw}")

    for fact in facts:
        norm_cats = normalize_categories(fact.get("categories"))
        if not norm_cats:
            leftover.append(fact)
            continue
        for cat in norm_cats:
            categories.setdefault(cat, []).append(fact)


    # Step 1: Collect all facts across all categories (avoid counting duplicates)
    all_facts_by_id = {}
    fact_to_cats = {}
    for cat, cat_facts in categories.items():
        for fact in cat_facts:
            all_facts_by_id[fact["id"]] = fact
            fact_to_cats.setdefault(fact["id"], set()).add(cat)

    # Step 1.5: Remove duplicate category assignments from overloaded categories
    changed = True
    while changed:
        changed = False
        largest_cat = max(categories.items(), key=lambda x: len(set(f["id"] for f in x[1])))[0]
        if len(set(f["id"] for f in categories[largest_cat])) <= 30:
            break

        for fact in list(categories[largest_cat]):
            fid = fact["id"]
            if len(fact_to_cats[fid]) > 1:
                categories[largest_cat] = [f for f in categories[largest_cat] if f["id"] != fid]
                fact_to_cats[fid].remove(largest_cat)
                changed = True
                break
    unique_facts = list(all_facts_by_id.values())
    def get_fact_score(fact):
        return sum(fact.get(k, 0) for k in ("quirkiness", "importance", "kidAppeal", "storyPotential", "inspiration"))

    unique_facts.sort(key=get_fact_score)

    # Step 3: If over limit, remove lowest scoring and set aside
    removed_ids = set()
    if len(unique_facts) > 100:
        to_remove = unique_facts[:len(unique_facts) - 100]
        for fact in to_remove:
            removed_ids.add(fact["id"])
        logging.info(f"🧹 Total facts removed to reach 100: {len(to_remove)}")
        for fact in unique_facts[:len(unique_facts) - 100]:
            removed_ids.add(fact["id"])

    # Step 4: Remove from original categories (but don't count duplicates)
    removed_counter = {}
    removed_facts = {}
    for cat in list(categories):
        new_list = []
        for fact in categories[cat]:
            if fact["id"] in removed_ids:
                removed_facts[fact["id"]] = fact
                removed_counter[cat] = removed_counter.get(cat, 0) + 1
            else:
                new_list.append(fact)
        if new_list:
            categories[cat] = new_list
        else:
            del categories[cat]

    # Step 5: Reassign removed facts into underfilled categories if possible
    reassignment_pool = [fact for fact in unique_facts if fact["id"] in removed_ids]
    for fact in reassignment_pool:
        for alt_cat in fact.get("categories", []):
            if alt_cat in categories and len(categories[alt_cat]) < 14:
                categories[alt_cat].append(fact)
                removed_ids.remove(fact["id"])
                break

    # Step 6: Reassign still-removed facts to highest-need category (balance the book)
    # Cap max size per category to 30
    fact_reassign_log = {}
    for fact_id, fact in removed_facts.items():
        best_fit = None
        smallest_size = float('inf')
        for alt_cat in fact.get("categories", []):
            if alt_cat in categories and len(categories[alt_cat]) < 30 and len(categories[alt_cat]) < smallest_size:
                best_fit = alt_cat
                smallest_size = len(categories[alt_cat])
        if best_fit:
            categories[best_fit].append(fact)
            fact_reassign_log[fact_id] = best_fit
            removed_ids.discard(fact_id)

    # Step 7: Deduplicate across categories – ensure each fact appears only once
    seen_ids = set()
    for cat in list(categories.keys()):
        new_list = []
        for fact in categories[cat]:
            fid = fact["id"]
            if fid not in seen_ids:
                new_list.append(fact)
                seen_ids.add(fid)
        categories[cat] = new_list

    # Final log (only first pass)
    if removed_counter and category_pages is None:
        total_reassigned = 0
        logging.info("🗑️ Fact redistribution breakdown:")
        for cat, count in removed_counter.items():
            reassigned_count = sum(1 for fid, target in fact_reassign_log.items() if cat in removed_facts[fid].get("categories", []))
            if reassigned_count:
                logging.info(f"   • Moved {reassigned_count} from {cat}")
                total_reassigned += reassigned_count
        if total_reassigned:
            logging.info(f"🔄 Total facts moved to new categories: {total_reassigned}")
        if removed_ids:
            logging.info(f"🗑️ Facts not reassigned (excluded): {len(removed_ids)}")
            for fid in removed_ids:
                logging.info(f"   • Removed: {removed_facts[fid]['title']} (ID {fid})")

        final_total = len(seen_ids)
        logging.info(f"📦 Final total facts used in book: {final_total}")


    question_number = 1

    for category, fact_list in categories.items():
        if category_pages is None:
            fact_ids = [f["id"] for f in fact_list]
            logging.info(f"📚 Category: {category} — {len(fact_ids)} facts")
            logging.info(f"   🆔 IDs: {', '.join(fact_ids)}")

        # 🔁 PageBreak starts a new page with the category title
        elements.append(PageBreak())

        title = Paragraph(f"<b>{category}</b>", styles['cat_title'])
        desc = CATEGORY_DESCRIPTIONS.get(category, "")
        desc_paragraph = Paragraph(desc, styles['story'])

        # Build content as a block (TOC-compatible + transparent visuals)
        title_block = KeepTogether([

            # ⚠️ Paragraph version just to support TOC logic (not visible in output)
            Paragraph(f"<b>{category}</b>", styles['category']),

            # # ✅ TransparentBox version for actual visual appearance
            # TransparentBox(f"<para align='center'><b>{category}</b></para>", styles['cat_title'], alpha=0.85),

            # Spacer(1, 12),
            # TransparentBox(f"<para align='center'>{desc}</para>", styles['story'], alpha=0.85),
        ])


        # Add dynamic vertical centering
        page_height = CUSTOM_PAGE_SIZE[1]
        estimated_content_height = 180  # adjust this if your text is taller
        spacer_height = max(0, (page_height - estimated_content_height) / 2 - 50)

        elements.append(title_block)
        elements.append(PageBreak())


        # ✅ This is where the background will kick in — nothing after this breaks it
        for i, fact in enumerate(fact_list):
            fact_block = KeepTogether([
                TransparentBox(f"<i>{fact['title']}</i>", styles['title']),
                TransparentBox(fact["story"] + "<br/><br/>", styles['story'])
            ])
            elements.append(fact_block)

        elements.append(PageBreak())

        # Add centered trivia intro block
        estimated_content_height = 180
        spacer_height = max(0, (CUSTOM_PAGE_SIZE[1] - estimated_content_height) / 2 - 50)

        # Trivia intro inside TransparentBoxes
        # trivia_intro = KeepTogether([
        #     TransparentBox("Trivia Time!", styles['trivia_title'], alpha=0.85),
        #     Spacer(1, 10),
        #     TransparentBox(
        #         "Test your brainpower with some tricky questions from this chapter. "
        #         "Get them right and you might just become the world's next quiz champion!",
        #         styles['story'],
        #         alpha=0.85
        #     )
        # ])
        # elements.append(trivia_intro)

        # Trivia marker (kept outside the box for parsing accuracy)
        elements.append(Paragraph(
            f"__TRIVIA_START__{category}",
            ParagraphStyle("HiddenTriviaMarker", fontSize=0, textColor=CUSTOM_BLUE)
        ))
        elements.append(PageBreak())

        logging.info(f"🧠 Trivia start marker added for category: {category}")

        # Questions block
        elements.append(
            TransparentBox(
                Paragraph("Trivia Time", styles['cat_title']),
                styles['story'],
                alpha=0.85
            )
        )

        # Add each question and checkbox table
        for fact in fact_list:
            q = fact.get("activity_question")
            choices = fact.get("activity_choices", [])

            if not q or not choices:
                continue

            # 🔀 Shuffle the options so the correct one isn't always first
            fact_id = fact.get("id") or f"{category}-{question_number}"
            seed_str = f"{date_str}-{category}-{fact_id}"
            shuffled_choices = stable_shuffle(choices, seed_str)

            question_paragraph = Paragraph(
                f"<b>{question_number}.</b> {q}",
                styles['trivia_questions']
            )

            checkboxes = [
                Paragraph(f"☐ {opt}", styles['trivia_questions'])
                for opt in shuffled_choices
            ]

            grid = [checkboxes[i:i + 2] for i in range(0, len(checkboxes), 2)]
            if len(grid[-1]) == 1:
                grid[-1].append("")

            table = Table(grid, colWidths=[160, 160])
            table.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LINEBELOW', (0, 0), (-1, -2), 0.25, colors.darkgrey),
                ('LINEAFTER', (0, 0), (0, -1), 0.25, colors.darkgrey),
            ]))

            elements.append(TransparentBox(
                [question_paragraph, table],
                styles['trivia_questions'],
                alpha=0.85,
                inner_spacing=8  # keep the nice spacing, but no fixed height
            ))

            question_number += 1


        # ➕ Letter Quest Page
        elements.append(PageBreak())

        # Title and description at top (same styling as Questions section)
        # elements.append(Spacer(1, 40))
        elements.append(TransparentBox("Letter Quest", styles['cat_title'], alpha=0.85))
        elements.append(TransparentBox(
            "Unleash your inner word wizard with this word search! ",
            styles['trivia_questions'],
            alpha=0.85
        ))
        elements.append(Spacer(1, 12))  # space before image

        # Word search image (centered below description)
        category_key = CATEGORY_BACKGROUNDS.get(category, '').lower()
        image_path = os.path.join(
            str(WORDSEARCH_DIR),
            f"{category_key}.png"
        )
        if os.path.exists(image_path):
            try:
                img_reader = ImageReader(image_path)
                original_width, original_height = img_reader.getSize()

                # ---- content frame width (same as your Frame calc) ----
                margin_in = 0.5
                margin_pt = margin_in * inch
                content_width = (PAGE_W - 2*BLEED_PT) - 2*margin_pt  # cap by margins

                # ---- height cap ----
                max_height = 380
                max_width = float(content_width)

                # ---- scale by the tighter of the two caps (keep ratio) ----
                scale = min(max_width / original_width, max_height / original_height)
                new_width = original_width * scale
                new_height = original_height * scale

                elements.append(Spacer(1, 12))
                elements.append(RLImage(image_path, width=new_width, height=new_height))
                elements.append(Spacer(1, 12))

            except Exception as e:
                logging.warning(f"❌ Could not scale image properly: {e}")
        else:
            elements.append(Paragraph("Word search image not found.", styles['story']))
        # Word list below the picture
        all_words_path = os.path.join(
            str(WORDSEARCH_DIR),
            "letter_quest_words.json"
        )
        if os.path.exists(all_words_path):
            try:
                with open(all_words_path, "r", encoding="utf-8") as f:
                    all_words = json.load(f)
                words = all_words.get(category_key, [])

                if words:
                    # Format words into rows of 4 (or whatever you want)
                    row_length = 4
                    # Convert all words to uppercase
                    words_upper = [w.upper() for w in words]

                    # Slice into rows of 6
                    table_data = [words_upper[i:i + row_length] for i in range(0, len(words_upper), row_length)]

                    # Pad last row if needed
                    if len(table_data[-1]) < row_length:
                        table_data[-1] += [""] * (row_length - len(table_data[-1]))

                    # Create table
                    word_table = Table(table_data, colWidths=330 // row_length)
                    word_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Baloo2'),
                        ('FONTSIZE', (0, 0), (-1, -1), 11),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ('TOPPADDING', (0, 0), (-1, -1), 2),
                        # Optional: background if needed for visibility
                        # ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ]))

                    # Wrap in FixedBottomTransparentBox
                    word_block = FixedBottomTransparentBox(
                        word_table,
                        styles['wordsearch'],
                        page_height=CUSTOM_PAGE_SIZE[1],
                        width=350,
                        padding=10,
                        alpha=0.85,
                        border=True
                    )
                    elements.append(word_block)
                else:
                    elements.append(Paragraph("No word list found for this category.", styles['story']))
            except Exception as e:
                logging.warning(f"❌ Could not load Letter Quest words: {e}")
                elements.append(Paragraph("Couldn't load word list!", styles['story']))
        else:
            elements.append(Paragraph("Word list file is missing!", styles['story']))

        # ➕ Grid Gauntlet Page
        elements.append(PageBreak())

        # Title and intro
        elements.append(TransparentBox("Grid Gauntlet", styles['cat_title'], alpha=0.85))
        elements.append(TransparentBox(
            "Test your brainpower with a tricky crossword challenge!",
            styles['trivia_questions'],
            alpha=0.85
        ))

        elements.append(Spacer(1, 20))  # space before image

        # Crossword image
        category_key = CATEGORY_BACKGROUNDS.get(category, '').lower()
        crossword_path = os.path.join(
            str(CROSSWORD_DIR),
            f"{category_key}.png"
        )

        if os.path.exists(crossword_path):
            try:
                img_reader = ImageReader(crossword_path)
                ow, oh = img_reader.getSize()

                # Content-frame width (matches your Frame calc)
                margin_in = 0.5
                margin_pt = margin_in * inch
                content_width = (PAGE_W - 2*BLEED_PT) - 2*margin_pt  # width cap by margins

                # Height cap (same logic as word search previews)
                max_height =300.0

                # Scale by the tighter cap, keep aspect ratio
                scale = min(float(content_width) / ow, max_height / oh)
                new_w = ow * scale
                new_h = oh * scale

                elements.append(Spacer(1, 12))
                elements.append(RLImage(crossword_path, width=new_w, height=new_h))
                elements.append(Spacer(1, 12))

            except Exception as e:
                logging.warning(f"❌ Could not load crossword image for {category_key}: {e}")
                elements.append(Paragraph("Crossword image couldn't load.", styles['story']))
        else:
            logging.warning(f"❌ Crossword image not found: {crossword_path}")
            elements.append(Paragraph("Crossword image not found.", styles['story']))

        # Load clue data
        clue_path = str(CROSSWORD_DIR / "grid_gauntlet_words.json")
        clue_key = f"{category_key}_crossword"

        across_clues = {}
        down_clues = {}

        if os.path.exists(clue_path):
            try:
                with open(clue_path, "r", encoding="utf-8") as f:
                    all_clues = json.load(f)
                    if clue_key in all_clues:
                        across_clues = all_clues[clue_key].get("across", {})
                        down_clues = all_clues[clue_key].get("down", {})
                    else:
                        logging.warning(f"❓ No crossword clues found for key: {clue_key}")
            except Exception as e:
                logging.warning(f"❌ Error reading crossword clues: {e}")
        else:
            logging.warning("❌ grid_gauntlet_words.json not found")

        # Display clue table below the image
        if across_clues or down_clues:
            across_items = sorted(across_clues.items(), key=lambda x: int(x[0]))
            down_items = sorted(down_clues.items(), key=lambda x: int(x[0]))

            # Build paragraphs separately
            across_paragraphs = [Paragraph("<b>ACROSS</b>", styles['crossword_layout'])] + [
                Paragraph(f"<b>{number}.</b> {clue}", styles['crossword']) for number, clue in across_items
            ]
            down_paragraphs = [Paragraph("<b>DOWN</b>", styles['crossword_layout'])] + [
                Paragraph(f"<b>{number}.</b> {clue}", styles['crossword']) for number, clue in down_items
            ]

            # Build 2-column table with two vertical stacks (each a list of flowables)
            clue_table = Table(
                [[across_paragraphs, down_paragraphs]],
                colWidths=[170, 170]
            )
            clue_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))

            elements.append(FixedBottomTransparentBox(
                clue_table,
                styles['crossword'],
                page_height=CUSTOM_PAGE_SIZE[1],
                width=350,
                padding=12,
                alpha=0.85,
                border=True
            ))



        # # Answers
        # elements.append(PageBreak())
        # elements.append(
        #     TransparentBox(
        #         Paragraph("Answers", styles['cat_title']),
        #         styles['story'],
        #         alpha=0.85
        #     )
        # )

        for i, fact in enumerate(fact_list, 1):
            q = fact.get("activity_question")
            a = fact.get("activity_answer")
            if q and a:
                global_answers.append((q, a))


        # ✅ Insert image immediately after title/description
        image_path = str(PICTURES_DIR / f"{CATEGORY_BACKGROUNDS.get(category, '').lower()}.png")
        if os.path.exists(image_path):
            elements.append(RLImage(image_path, width=460, height=300))


    # Export category structure for external validation with word counts
    global final_categories_dict
    print("🧩 Final categories at export time:", list(categories.keys()))
    final_categories_dict = {
        category: [
            {
                "id": fact["id"],
                "title": fact["title"],
                "word_count": len(fact.get("story", "").split())
            }
            for fact in fact_list
        ]

        for category, fact_list in categories.items()
    }

    if global_answers:
        # Hidden marker for background computation
        elements.append(PageBreak())
        elements.append(Paragraph(
            "__ANSWERS_START__",
            ParagraphStyle("HiddenAnswersMarker", fontSize=0, textColor=CUSTOM_BLUE)
        ))

        # Title page → leave blank so only the background shows
        elements.append(PageBreak())

        # Questions page (content header)
        elements.append(
            TransparentBox(
                Paragraph("Trivia Time Answers", styles['cat_title']),
                styles['story'],
                alpha=0.85
            )
        )

    for i, (q, a) in enumerate(global_answers, 1):
        para = Paragraph(f"<b>{i}.</b> {q}<br/><b>Answer:</b> {a}", styles['trivia_answers'])
        box = TransparentBox(
            [para],
            styles['trivia_answers'],
            alpha=0.85,
            padding=4,
            inner_spacing=0,
            width=350  # keep default width to avoid extra wrapping
        )
        # 🔽 Horizontally offset the box inward by 45 pts (~0.6 inch)
        box.drawOn = lambda canvas, x, y, _sW=0, box=box: TransparentBox.drawOn(
            box, canvas, x + 45, y, _sW
        )
        elements.append(box)

    # ➕ Letter Quest Answers Section (match preview look)
    if category_pages:
        lq_items = _collect_answer_images(
            categories=categories.keys(),
            base_folder=str(WORDSEARCH_DIR),
            suffix="_answers.png"
        )

        _answers_grid(
            elements,
            styles,
            title_text="🧩 Letter Quest Answers",
            items=lq_items,
            cell_width=175,
            rows_per_page=2,
            cols_per_page=2
        )

        # ➕ Grid Gauntlet Answers Section (match preview look)
        gg_items = _collect_answer_images(
            categories=categories.keys(),
            base_folder=str(CROSSWORD_DIR),
            suffix="_answers.png"
        )

        _answers_grid(
            elements,
            styles,
            title_text="🧠 Grid Gauntlet Answers",
            items=gg_items,
            cell_width=175,
            rows_per_page=2,
            cols_per_page=2
        )






    return elements
