import os
import re
import json
import logging
from io import BytesIO
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Flowable
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.lib.units import cm
import fitz  # PyMuPDF
from PIL import Image

print("CWD:", os.getcwd())

def draw_cloud_shape_background(canvas, doc, alpha=0.88, scale=1.0):
    from reportlab.lib.units import cm
    import math

    canvas.saveState()
    canvas.setFillColorRGB(1, 1, 1, alpha=alpha)

    w = doc.pagesize[0] * 0.80
    h = doc.pagesize[1] * scale
    x = (doc.pagesize[0] - w) / 2
    y = (doc.pagesize[1] - h) / 2

    # Bump settings
    bumps_x = 8
    bumps_y = 6
    bump_radius = 10

    path = canvas.beginPath()

    # Start bottom-left
    path.moveTo(x, y + bump_radius)

    # Left side: bottom to top with bumps
    for i in range(bumps_y):
        cy = y + i * (h / bumps_y)
        path.curveTo(x - bump_radius, cy + bump_radius / 2,
                     x - bump_radius, cy + (h / bumps_y) - bump_radius / 2,
                     x, cy + (h / bumps_y))

    # Top side: left to right with bumps
    for i in range(bumps_x):
        cx = x + i * (w / bumps_x)
        path.curveTo(cx + bump_radius / 2, y + h + bump_radius,
                     cx + (w / bumps_x) - bump_radius / 2, y + h + bump_radius,
                     cx + (w / bumps_x), y + h)

    # Right side: top to bottom with bumps
    for i in range(bumps_y):
        cy = y + h - i * (h / bumps_y)
        path.curveTo(x + w + bump_radius, cy - bump_radius / 2,
                     x + w + bump_radius, cy - (h / bumps_y) + bump_radius / 2,
                     x + w, cy - (h / bumps_y))

    # Bottom side: right to left with bumps
    for i in range(bumps_x):
        cx = x + w - i * (w / bumps_x)
        path.curveTo(cx - bump_radius / 2, y - bump_radius,
                     cx - (w / bumps_x) + bump_radius / 2, y - bump_radius,
                     cx - (w / bumps_x), y)

    path.close()
    canvas.drawPath(path, fill=1, stroke=0)
    canvas.restoreState()




class WhiteoutPage(Flowable):
    def __init__(self, width, height):
        super().__init__()
        self.width = width
        self.height = height
        self._fixedWidth = 1
        self._fixedHeight = 1

    def wrap(self, availWidth, availHeight):
        return (0, 0.1)

    def drawOn(self, canvas, x, y, _sW=0):
        canvas.saveState()
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        canvas.restoreState()

log_file_path = os.path.join(os.getcwd(), "debug_output.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
        logging.StreamHandler()  # Optional: keep showing logs in console too
    ]
)

CATEGORY_BACKGROUNDS = {
    "Today’s Vibe Check": "todays_vibe_check",
    "History’s Mic Drop Moments": "history_mic_drop_moments",
    "World Shakers & Icon Makers": "world_shakers_and_icon_makers",
    "Big Brain Energy": "big_brain_energy",
    "Beyond Earth": "beyond_earth",
    "Creature Feature": "creature_feature",
    "Vibes, Beats & Brushes": "vibes_beats_and_brushes",
    "Days That Slay": "days_that_slay",
    "Full Beast Mode": "full_beast_mode",
    "Mother Nature’s Meltdowns": "mother_natures_meltdowns",
    "The What Zone": "the_what_zone"
}

CATEGORY_DESCRIPTIONS = {
    "Today’s Vibe Check": "seasonal chaos, sky weirdness, animal drama",
    "History’s Mic Drop Moments": "wars, revolutions, treaties, global turning points",
    "World Shakers & Icon Makers": "powerful leaders, world changers, inspiring people",
    "Big Brain Energy": "discoveries, breakthroughs, tech, biology, chemistry",
    "Beyond Earth": "astronomy, space missions, meteorology ",
    "Creature Feature": "cool creatures, conservation, animal records or traits ",
    "Vibes, Beats & Brushes": "Vibes, Beats & Brushes — creativity, artists, music, cultural trends",
    "Days That Slay": "holidays, rituals, festivals, national days",
    "Full Beast Mode": "competitions, record-breakers, sporting firsts",
    "Mother Nature’s Meltdowns": "volcanoes, climate, ecosystems, nature wonders",
    "The What Zone": "oddities, mysteries, unusual facts",
}

final_categories_dict = {}  # For category-to-fact-id export

class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._page_tracker = {}  # Tracks where each category starts
        self._background_ranges = []  # Stores start-end ranges with ImageReader backgrounds
        

        margin_size = 0.5

        frame = Frame(
            self.leftMargin + margin_size,          # move right from left edge
            self.bottomMargin + margin_size,        # move up from bottom edge
            self.width - 2 * margin_size,           # shrink width by left+right margins
            self.height - 2 * margin_size,          # shrink height by top+bottom margins
            id='normal'
        )

        template = PageTemplate(id='Content', frames=[frame], onPage=self.draw_background)
        self.addPageTemplates([template])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            text = flowable.getPlainText()

            if flowable.style.name == "CategoryTitle":
                if text not in self._page_tracker:
                    self._page_tracker[text] = self.page
                    logging.info(f"📌 Category page marked: {text} → page {self.page}")

            elif text.strip() == "__TOC_PAGE__":
                if text not in self._page_tracker:
                    self._page_tracker[text] = self.page
                    logging.info(f"📋 TOC marker registered: {text} → page {self.page}")

            elif text.startswith("__TRIVIA_START__"):
                if text not in self._page_tracker:
                    self._page_tracker[text] = self.page
                    logging.info(f"🧠 Trivia marker registered: {text} → page {self.page}")

            elif text.strip() == "__TOC_END__":
                if text not in self._page_tracker:
                    self._page_tracker[text] = self.page
                    logging.info(f"📌 TOC end marker registered: {text} → page {self.page}")

            elif text.strip() == "__INTRO_PAGE__":
                if text not in self._page_tracker:
                    self._page_tracker[text] = self.page
                    logging.info(f"📘 Intro marker registered: {text} → page {self.page}")

            elif text.strip() == "__COVER_PAGE__":
                if text not in self._page_tracker:
                    self._page_tracker[text] = self.page
                    logging.info(f"📖 Cover marker registered: {text} → page {self.page}")




    def draw_background(self, canvas, doc):
        current_page = canvas.getPageNumber()
        canvas.saveState()

        # Always fill base with solid white to avoid bleed-through
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)

        bg_range = None
        for bg in self._background_ranges:
            if bg["start"] <= current_page <= bg["end"]:
                bg_range = bg
                break

        if bg_range:
            img = ImageReader(bg_range.get("image_path")) if "image_path" in bg_range else bg_range.get("image")

            try:
                canvas.drawImage(img, 0, 0, width=doc.pagesize[0], height=doc.pagesize[1])
                label = bg_range.get("label", "unknown")
                img_path = bg_range.get("image_path", "inline ImageReader")
                logging.info(f"✅ Page {current_page}: Applied '{label}' background → {os.path.basename(img_path)}")
            except Exception as e:
                logging.warning(f"❌ Page {current_page}: Failed to draw background image → {e}")

        else:
            logging.warning(f"🚫 Page {current_page}: No background assigned")

        label = bg_range.get("label") if bg_range else None

        if label == "cover":
            scale = 0.4  # Remove cloud on cover
        elif label == "intro":
            scale = 0.8
        elif label == "toc":
            scale = 1.0
        elif label == "category" and current_page != bg_range["start"]:
            scale = 0.8
        else:
            scale = 0.2


        draw_cloud_shape_background(canvas, doc, alpha=0.7, scale=scale)

        canvas.restoreState()
        self.add_page_number(canvas, doc)


    def add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        if page_num >= 3:
            canvas.setFont("DejaVu", 10)
            canvas.setFillColorRGB(1, 1, 1)
            text = f"Page {page_num}"

            if page_num % 2 == 0:
                # Even pages: left-aligned
                canvas.drawString(28, 10, text)
            else:
                # Odd pages: right-aligned
                canvas.drawRightString(595, 10, text)


def build_elements(facts, styles, date_str, category_pages=None):
    elements = []
    num_facts = len(facts)

    elements.append(Spacer(1, 200))
    elements += [
        Paragraph("__COVER_PAGE__", ParagraphStyle("HiddenCoverMarker", fontSize=1, textColor=colors.white)),
        Paragraph("WHAT HAPPENED ON...", styles['cover_title']),
        Paragraph(f"{date_str}?", styles['cover_date']),
        Spacer(1, 60),
        Paragraph("Written by Timothy John Mulrenan", styles['cover_date'])
    ]
    elements.append(PageBreak())

    intro_text = f"""
    Welcome to the amazing world of history, trivia, and delightfully random facts! This book is your guide to all the wild, weird, and wonderful things that happened around the world — and together, we’re about to answer the big question: <b>What happened on {date_str}?</b>

    I’m TJ, a fact-lover from Saffron Walden, a small town in the UK. Whether this date is your birthday, your lizard’s, or just a lucky guess — this book’s for you.

    There are <b>{num_facts}</b> facts packed into these pages. Let’s dive in!
    <br/><br/><br/><b>— TJ</b>"""
    elements.append(Paragraph(
        "__INTRO_PAGE__",
        ParagraphStyle("HiddenIntroMarker", fontSize=1, textColor=colors.white)
    ))
    elements.append(Paragraph("Before we begin!", styles['intro_header']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(intro_text.strip(), styles['intro']))

    if category_pages:
        elements.append(PageBreak())
        elements.append(Paragraph(
            "__TOC_PAGE__",
            ParagraphStyle("HiddenTOCMarker", fontSize=1, textColor=colors.grey)
        ))
        elements.append(Spacer(1, 12))

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

        table = Table(toc_data, colWidths=[380, 80], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.darkgrey),
        ]))

        # ⛔ Force TOC to stay together on one page
        toc_block = KeepTogether([
            Paragraph("Table of Contents", styles['toc_title']),
            Paragraph("__TOC_PAGE__", ParagraphStyle("HiddenTOCMarker", fontSize=1, textColor=colors.grey)),
            Spacer(1, 12),
            table,
            Paragraph("__TOC_END__", ParagraphStyle("HiddenTOCEndMarker", fontSize=1, textColor=colors.white)),
        ])

        elements.append(toc_block)
    
    # 🌤️ Today's Vibe Check Section
    elements.append(Paragraph(
        "__TODAYS_VIBE_CHECK__",
        ParagraphStyle("HiddenVibeMarker", fontSize=1, textColor=colors.white)
    ))

    # Estimate vertical space like category headers
    page_height = letter[1]
    estimated_content_height = 180
    spacer_height = max(0, (page_height - estimated_content_height) / 2 - 50)

    elements.append(Spacer(1, spacer_height))
    elements.append(KeepTogether([
        Spacer(1, 12),
        Paragraph("<para align='center'><b>Today's Vibe Check</b></para>", styles['category']),
        Spacer(1, 12),
        Paragraph("<para align='center'>What's the deal with this day? Seasonal chaos, sky weirdness, animal drama — it's all happening.</para>", styles['story']),
    ]))
    elements.append(PageBreak())

    try:
        month, day = date_str.split()
        day = ''.join(filter(str.isdigit, day))
        vibe_filename = f"{month}_{day}_Facts.json"
        vibe_path = os.path.join(
            "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/a_rawDay",
            vibe_filename
        )
        with open(vibe_path, "r", encoding="utf-8") as f:
            vibe_facts = json.load(f)

        added_any = False
        for fact in vibe_facts:
            if fact.get("kid_friendly", False):
                fact_block = KeepTogether([
                    Paragraph(f"• {fact['fact']}", styles['story']),
                    Spacer(1, 10)
                ])
                elements.append(fact_block)
                added_any = True

        if not added_any:
            elements.append(Paragraph("No kid-friendly facts available today.", styles['story']))

    except Exception as e:
        logging.warning(f"🚫 Could not load Today's Vibe Check facts: {e}")
        elements.append(Paragraph("Oops! Vibe Check facts couldn’t load.", styles['story']))

    # 🎉 Days That Slay Section
    elements.append(Paragraph(
        "__DAYS_THAT_SLAY__",
        ParagraphStyle("HiddenSlayMarker", fontSize=1, textColor=colors.white)
    ))

    # Vertical spacing like category headers
    page_height = letter[1]
    estimated_content_height = 180
    spacer_height = max(0, (page_height - estimated_content_height) / 2 - 50)
    elements.append(Spacer(1, spacer_height))

    elements.append(KeepTogether([
        Spacer(1, 12),
        Paragraph("<para align='center'><b>Days That Slay</b></para>", styles['category']),
        Spacer(1, 12),
        Paragraph("The most extra, random, and delightful holidays hitting today. Weird food? Niche magic? Major vibes.", styles['story']),
    ]))
    elements.append(PageBreak())

    try:
        month, day = date_str.split()
        day = ''.join(filter(str.isdigit, day))
        slay_filename = f"{month}_{day}_Holidays_scored_enhanced.json"
        slay_path = os.path.join(
            "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/c_enhanced",
            slay_filename
        )
        with open(slay_path, "r", encoding="utf-8") as f:
            slay_facts = json.load(f)

        added_any = False
        for entry in slay_facts:
            if entry.get("suitable_for_8_to_12_year_old", False):
                fact_block = KeepTogether([
                    Paragraph(f"<b>{entry['title']}</b>", styles['story']),
                    Spacer(1, 4),
                    Paragraph(entry["story"], styles['story']),
                    Spacer(1, 12)
                ])
                elements.append(fact_block)
                added_any = True

        if not added_any:
            elements.append(Paragraph("No fun holidays hit today — weird!", styles['story']))

    except Exception as e:
        logging.warning(f"🚫 Could not load Days That Slay facts: {e}")
        elements.append(Paragraph("Oops! Slay day stories couldn’t load.", styles['story']))

    elements.append(PageBreak())



    # Categorize facts
    categories = {}
    leftover = []
    for fact in facts:
        matched = False
        for cat in fact.get("categories", ["Other"]):
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(fact)
            matched = True
        if not matched:
            leftover.append(fact)

    # Reassign categories with fewer than 6 facts to stronger categories
    reassigned = []
    filtered_categories = {}

    for cat, facts_in_cat in categories.items():
        if len(facts_in_cat) < 6:
            for fact in facts_in_cat:
                reassigned.append(fact)
        else:
            filtered_categories[cat] = facts_in_cat

    for fact in reassigned:
        reassigned_to = False
        for alt_cat in fact.get("categories", []):
            if alt_cat in filtered_categories:
                filtered_categories[alt_cat].append(fact)
                reassigned_to = True
                break
        if not reassigned_to:
            filtered_categories.setdefault("Extra Awesome Facts 🌟", []).append(fact)

    categories = filtered_categories

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
            

    

    for category, fact_list in categories.items():
        if category_pages is None:
            logging.info(f"📚 Category: {category} — {len(fact_list)} facts")

        # 🔁 PageBreak starts a new page with the category title
        elements.append(PageBreak())
        
        title = Paragraph(f"<b>{category}</b>", styles['category'])
        desc = CATEGORY_DESCRIPTIONS.get(category, "")
        desc_paragraph = Paragraph(desc, styles['story'])

        # Build content as a block
        title_block = KeepTogether([
            Spacer(1, 12),
            Paragraph(f"<para align='center'><b>{category}</b></para>", styles['category']),
            Spacer(1, 12),
            Paragraph(f"<para align='center'>{desc}</para>", styles['story']),
        ])

        # Add dynamic vertical centering
        page_height = letter[1]
        estimated_content_height = 180  # adjust this if your text is taller
        spacer_height = max(0, (page_height - estimated_content_height) / 2 - 50)

        elements.append(Spacer(1, spacer_height))
        elements.append(title_block)
        elements.append(PageBreak())


        # ✅ This is where the background will kick in — nothing after this breaks it
        for i, fact in enumerate(fact_list):
            fact_block = KeepTogether([
                Paragraph(f"<i>{fact['title']}</i>", styles['title']),
                Paragraph(fact["story"], styles['story'])
            ])
            elements.append(fact_block)

        elements.append(PageBreak())

        # Add centered trivia intro block
        estimated_content_height = 180
        spacer_height = max(0, (letter[1] - estimated_content_height) / 2 - 50)
        elements.append(Spacer(1, spacer_height))

        # Trivia title + marker placed here
        elements.append(Paragraph("<para align='center'><b>Trivia Time!</b></para>", styles['trivia_title']))

        elements.append(Paragraph(
            f"__TRIVIA_START__{category}",
            ParagraphStyle("HiddenTriviaMarker", fontSize=1, textColor=colors.white)
        ))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            "<para align='center'>Test your brainpower with some tricky questions from this chapter. "
            "Get them right and you might just become the world’s next quiz champion!</para>",
            styles['story']
        ))
        elements.append(PageBreak())



        logging.info(f"🧠 Trivia start marker added for category: {category}")

        # Add "Questions" heading before trivia starts
        elements.append(Paragraph("Questions", styles['category']))
        elements.append(Spacer(1, 12))

        # Trivia Questions
        for i, fact in enumerate(fact_list, 1):
            q = fact.get("activity_question")
            choices = fact.get("activity_choices", [])
            if q and choices:
                question_paragraph = Paragraph(f"{i}. {q}", styles['story'])
                checkboxes = [Paragraph(f"☐ {opt}", styles['story']) for opt in choices]
                grid = [checkboxes[i:i+2] for i in range(0, len(checkboxes), 2)]

                # Pad the last row if needed
                if len(grid[-1]) == 1:
                    grid[-1].append("")

                table = Table(grid, colWidths=[240, 220])
                table.setStyle(TableStyle([
                    ('LEFTPADDING', (0, 0), (0, -1), 36),
                    ('LEFTPADDING', (1, 0), (1, -1), 0),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))

                # Wrap in KeepTogether to avoid page splitting
                elements.append(KeepTogether([
                    question_paragraph,
                    table,
                    Spacer(1, 12)
                ]))

        # Answers
        elements.append(PageBreak())
        elements.append(Paragraph("Answers", styles['category']))
        elements.append(Spacer(1, 12))
        for i, fact in enumerate(fact_list, 1):
            q = fact.get("activity_question")
            a = fact.get("activity_answer")
            if q and a:
                elements.append(Paragraph(f"• {i}. {q} → <b>{a}</b>", styles['story']))

        # ✅ Insert image immediately after title/description
        image_path = os.path.join("pictures", f"{CATEGORY_BACKGROUNDS.get(category, '').lower()}.png")
        if os.path.exists(image_path):
            elements.append(RLImage(image_path, width=400, height=300))
            elements.append(Spacer(1, 20))

    # Export category structure for external validation with word counts
    global final_categories_dict
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

    return elements


def compute_background_ranges(page_tracker, category_backgrounds):
    import os
    import unicodedata
    import logging

    def normalize_text(text):
        import unicodedata

        # Remove emojis
        text = ''.join(c for c in text if not unicodedata.category(c).startswith('So'))

        # Normalize curly quotes/apostrophes to straight ones
        text = text.replace("’", "'").replace("‘", "'")  # single quotes/apostrophes
        text = text.replace("“", '"').replace("”", '"')  # double quotes

        return text.strip()

    sorted_pages = sorted(page_tracker.items(), key=lambda x: x[1])
    temp_ranges = []
    skip_until = None

    for i, (label, start_page) in enumerate(sorted_pages):
        # ✅ Skip anything that falls inside the TOC range
        if skip_until is not None and start_page <= skip_until:
            logging.debug(f"⏭️ Skipping label '{label}' at page {start_page} (within TOC range ending {skip_until})")
            continue

        # Default end page: just before the next marker or end of doc
        end_page = sorted_pages[i + 1][1] - 1 if i + 1 < len(sorted_pages) else 999
        logging.debug(f"🔍 Considering label '{label}' → page {start_page} to {end_page}")

        if label == "__COVER_PAGE__":
            bg_path = os.path.join("backgrounds", "cover.png")
            kind = "cover"
            logging.info(f"📕 Cover page detected → pages {start_page}–{end_page}")
            if os.path.exists(bg_path):
                temp_ranges.append((start_page, end_page, bg_path, kind))
            else:
                logging.warning(f"❌ Cover background image not found: {bg_path}")
            continue

        elif label == "__INTRO_PAGE__":
            bg_path = os.path.join("backgrounds", "before_we_begin.png")
            kind = "intro"
            logging.info(f"📘 Intro range detected → pages {start_page}–{end_page}")
            if os.path.exists(bg_path):
                temp_ranges.append((start_page, end_page, bg_path, kind))
            else:
                logging.warning(f"❌ Intro background image not found: {bg_path}")
            continue

        elif label == "__TOC_PAGE__":
            end_page = page_tracker.get("__TOC_END__", start_page)
            toc_path = os.path.join("backgrounds", "table_of_contents.png")
            if os.path.exists(toc_path):
                temp_ranges.append((start_page, end_page, toc_path, "toc"))
                logging.info(f"🧭 TOC range added: pages {start_page}–{end_page}")
            else:
                logging.warning(f"🚫 TOC image missing at: {toc_path}")
            skip_until = end_page
            continue

        elif label == "__TODAYS_VIBE_CHECK__":
            bg_path = os.path.join("backgrounds", "todays_vibe_check.png")
            kind = "vibe"
            logging.info(f"🌤️ Vibe Check page detected → pages {start_page}–{end_page}")
            if os.path.exists(bg_path):
                temp_ranges.append((start_page, end_page, bg_path, kind))
            else:
                logging.warning(f"❌ Vibe Check background image not found: {bg_path}")
            continue

        elif label == "__DAYS_THAT_SLAY__":
            bg_path = os.path.join("backgrounds", "days_that_slay.png")
            kind = "slay"
            logging.info(f"🎉 Days That Slay page detected → pages {start_page}–{end_page}")
            if os.path.exists(bg_path):
                temp_ranges.append((start_page, end_page, bg_path, kind))
            else:
                logging.warning(f"❌ Days That Slay background image not found: {bg_path}")
            continue

        elif label.startswith("__TRIVIA_START__"):
            bg_path = os.path.join("backgrounds", "trivia_time.png")
            kind = "trivia"
            logging.info(f"🎲 Trivia range detected: '{label}' → pages {start_page}–{end_page}")


        else:
            stripped = normalize_text(label)

            match_key = next(
                (k for k in category_backgrounds if normalize_text(k) == stripped),
                None
            )
            if not match_key:
                logging.warning(f"❓ No match for category label '{label}' (stripped: '{stripped}')")
                continue
            bg_file = f"{category_backgrounds[match_key]}.png"
            bg_path = os.path.join("backgrounds", bg_file)
            kind = "category"
            logging.info(f"📂 Category range: '{label}' → using '{bg_file}' → pages {start_page}–{end_page}")

        if os.path.exists(bg_path):
            temp_ranges.append((start_page, end_page, bg_path, kind))
        else:
            logging.warning(f"❌ Background image not found: {bg_path}")

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

    # Font registration
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join("fonts", "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join("fonts", "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", os.path.join("fonts", "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", os.path.join("fonts", "DejaVuSans-BoldOblique.ttf")))
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")

    date_str = extract_date_with_suffix(json_file)

    # Styles
    styles = {
        'cover_title': ParagraphStyle("CoverTitle", fontName="DejaVu-Bold", fontSize=28, alignment=TA_CENTER, spaceAfter=20),
        'cover_date': ParagraphStyle("CoverDate", fontName="DejaVu", fontSize=20, alignment=TA_CENTER),
        'intro_header': ParagraphStyle("IntroHeader", fontName="DejaVu-Bold", fontSize=18, spaceAfter=10, alignment=TA_LEFT),
        'intro': ParagraphStyle("Intro", fontName="DejaVu", fontSize=14, leading=22, spaceAfter=14),
        'toc_title': ParagraphStyle("TOCTitle", fontName="DejaVu-Bold", fontSize=20, spaceAfter=24, alignment=TA_CENTER),
        'toc_item': ParagraphStyle("TOCItem", fontName="DejaVu", fontSize=12, spaceAfter=0, leading=14, alignment=TA_LEFT),
        'category': ParagraphStyle("CategoryTitle", fontName="DejaVu-Bold", fontSize=18, spaceAfter=12, spaceBefore=12),
        'title': ParagraphStyle("FactTitle", fontName="DejaVu-BoldOblique", fontSize=13, spaceAfter=6, leading=14),
        'story': ParagraphStyle("FactStory", fontName="DejaVu", fontSize=16, leading=20, spaceAfter=16, spaceBefore=0),
        'trivia_title': ParagraphStyle("TriviaTitle", fontName="DejaVu-Bold", fontSize=16, spaceAfter=12, alignment=TA_CENTER),
    }

    # First pass – generate page tracker info
    doc1 = MyDocTemplate(output_pdf, pagesize=letter, title=f"What Happened on {date_str}")
    elements1 = build_elements(facts, styles, date_str)
    doc1.build(elements1)

    # Capture page locations for TOC and category headings
    category_pages = sorted(
        [(label, page) for label, page in doc1._page_tracker.items() if not label.startswith("__TRIVIA_START__")],
        key=lambda x: x[1]
    )

    # Second pass – render again with TOC now present
    doc2_stream = BytesIO()
    doc2 = MyDocTemplate(doc2_stream, pagesize=letter, title=f"What Happened on {date_str}")
    elements2 = build_elements(facts, styles, date_str, category_pages)
    doc2.build(elements2)

    # Compute background ranges
    background_ranges = compute_background_ranges(doc2._page_tracker, CATEGORY_BACKGROUNDS)

    # Final doc with backgrounds applied
    final_doc = MyDocTemplate(output_pdf, pagesize=letter, title=f"What Happened on {date_str}")
    final_doc._background_ranges = background_ranges

    # Rebuild final output
    final_elements = build_elements(facts, styles, date_str, category_pages)

    frame = Frame(final_doc.leftMargin, final_doc.bottomMargin, final_doc.width, final_doc.height, id='normal')
    template = PageTemplate(id='Content', frames=[frame], onPage=final_doc.draw_background)
    final_doc.addPageTemplates([template])

    logging.info("📄 Final build started with full backgrounds...")
    final_doc.build(final_elements)
    logging.info("✅ Final PDF built successfully.")

    # Export final categories for debugging
    output_json = output_pdf.replace(".pdf", "_categories.json")
    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(final_categories_dict, out, indent=2)
    logging.info(f"📁 Categories exported to: {output_json}")
    logging.info(f"✅ PDF created at: {output_pdf}")

    print("Page tracker keys:", doc2._page_tracker.keys())
    print("🎯 Final background ranges applied:")
    for r in final_doc._background_ranges:
        print(f" → Pages {r['start']}–{r['end']}: {os.path.basename(r['image_path'])}")


def overlay_trivia_pages(pdf_path, trivia_img_path):
    import fitz
    from PIL import Image

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
    base_dir = os.getcwd()
    facts_dir = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/4_categorised"
    books_dir = os.path.join(base_dir, "books")
    os.makedirs(books_dir, exist_ok=True)

    for filename in os.listdir(facts_dir):
        if filename.endswith(".json"):
            json_path = os.path.join(facts_dir, filename)
            base_name = os.path.splitext(filename)[0]
            safe_pdf_path = get_unique_filename(books_dir, f"{base_name}.pdf")

            generate_pdf_with_manual_toc(json_path, safe_pdf_path)

            # ✅ Correct usage here — safe_pdf_path is defined now
            overlay_trivia_pages(safe_pdf_path, os.path.join("backgrounds", "trivia_time.png"))


