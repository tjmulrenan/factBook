
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


from reportlab.platypus import Flowable, Paragraph

class TransparentBox(Flowable):
    def __init__(self, content, style, width=None, height=None, padding=15, alpha=0.85, inner_spacing=None):
        super().__init__()
        self.style = style
        self.padding = padding
        self.alpha = alpha
        self.width = width if width is not None else 450
        self.height = height
        self.inner_spacing = 0 if inner_spacing is None else inner_spacing  # ✅ Add this

        # Normalize content to list of flowables
        if isinstance(content, list):
            self._content = content
        elif isinstance(content, Flowable):
            self._content = [content]
        else:
            self._content = [Paragraph(str(content), style)]

    def wrap(self, availWidth, availHeight):
        used_width = self.width
        content_width = used_width - 2 * self.padding

        total_height = 0
        for i, flowable in enumerate(self._content):
            _, h = flowable.wrap(content_width, availHeight)
            total_height += h
            if i < len(self._content) - 1:
                total_height += self.inner_spacing  # ✅ space between items

        self.eff_width = used_width
        self.eff_height = self.height if self.height is not None else total_height + 2 * self.padding  # ✅ top + bottom

        return self.eff_width, self.eff_height

    def drawOn(self, canvas, x, y, _sW=0):
        centered_x = (canvas._pagesize[0] - self.eff_width) / 2
        super().drawOn(canvas, centered_x, y, _sW)

    def draw(self):
        self.canv.saveState()
        self.canv.setFillColorRGB(1, 1, 1, alpha=self.alpha)

        x = -self._cur_x if hasattr(self, '_cur_x') else 0
        self.canv.rect(x, 0, self.eff_width, self.eff_height, fill=1, stroke=0)

        content_width = self.eff_width - 2 * self.padding
        y_cursor = self.eff_height - self.padding  # start from top

        for i, flowable in enumerate(self._content):
            w, h = flowable.wrap(content_width, self.eff_height)
            flowable.drawOn(self.canv, self.padding, y_cursor - h)
            y_cursor -= h
            if i < len(self._content) - 1:
                y_cursor -= self.inner_spacing  # ✅ only between elements

        self.canv.restoreState()





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
    "Today's Vibe Check": "What’s the mood today? Think weird weather, dramatic animals, and random seasonal chaos.",
    "History's Mic Drop Moments": "Big turning points that made the world go 'WHAAAT?!' — epic wars, revolutions, and game-changing deals.",
    "World Shakers & Icon Makers": "Meet the legends who changed everything — rulers, rebels, geniuses, and icons who made their mark.",
    "Big Brain Energy": "Mind-blowing inventions, wild science, genius ideas, and epic 'aha!' moments.",
    "Beyond Earth": "Stuff that’s out of this world — space launches, alien signals, meteor showers, and cosmic mysteries.",
    "Creature Feature": "Fur, fins, feathers and fangs — meet nature’s wildest creatures and their coolest superpowers.",
    "Vibes, Beats & Brushes": "Where art meets attitude — music, dance, trends, and creativity that made the world pop.",
    "Days That Slay": "Holidays and celebrations that bring the party — from the wacky to the wonderful.",
    "Full Beast Mode": "Sports, stunts, and mega records — where humans (and animals) go all out.",
    "Mother Nature's Meltdowns": "Earth doing the most — volcanoes, wild weather, and nature’s power on full blast.",
    "The What Zone": "Wait... what? The strangest, silliest, and most head-scratching facts you never knew you needed.",
}


final_categories_dict = {}  # For category-to-fact-id export

class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._page_tracker = {}  # Tracks where each category starts
        self._background_ranges = []  # Stores start-end ranges with ImageReader backgrounds
        self._page_usage = {}  # Tracks used vertical space per page
        self._current_y_position = 0



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
        super().afterFlowable(flowable)

        if isinstance(flowable, Paragraph):
            text = flowable.getPlainText().strip()
            if flowable.style.name == "CategoryTitle" and text not in self._page_tracker:
                self._page_tracker[text] = self.page
            elif text.startswith("__TRIVIA_START__") and text not in self._page_tracker:
                self._page_tracker[text] = self.page
            elif text in (
                "__TOC_PAGE__", "__TOC_END__", "__INTRO_PAGE__", "__COVER_PAGE__",
                "__DAYS_THAT_SLAY__", "__TODAYS_VIBE_CHECK__"
            ):
                self._page_tracker[text] = self.page




    def draw_background(self, canvas, doc):
        current_page = canvas.getPageNumber()
        canvas.saveState()

        # Always clear background
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)

        # Pick background range if one matches
        bg_range = None
        for bg in self._background_ranges:
            if bg["start"] <= current_page <= bg["end"]:
                bg_range = bg
                break

        if bg_range:
            try:
                img = bg_range.get("image")
                if not img and "image_path" in bg_range:
                    from reportlab.lib.utils import ImageReader
                    img = ImageReader(bg_range["image_path"])
                canvas.drawImage(img, 0, 0, width=doc.pagesize[0], height=doc.pagesize[1])
            except Exception as e:
                logging.warning(f"❌ Page {current_page}: Failed to draw background → {e}")

        canvas.restoreState()
        self.add_page_number(canvas, doc)


    def add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        if page_num >= 3:
            canvas.setFont("DejaVu", 12)
            canvas.setFillColorRGB(1, 1, 1)
            text = f"Page {page_num}"

            if page_num % 2 == 0:
                # Even pages: left-aligned
                canvas.drawString(28, 770, text)
            else:
                # Odd pages: right-aligned
                canvas.drawRightString(595, 770, text)

# before
#             if page_num % 2 == 0:
#                 # Even pages: left-aligned
#                 canvas.drawString(28, 10, text)
#             else:
#                 # Odd pages: right-aligned
#                 canvas.drawRightString(595, 10, text)

global_answers = []  # Collect answers to render later


def build_elements(facts, styles, date_str, category_pages=None):
    elements = []
    global global_answers
    global_answers = []  # ⬅️ Reset before accumulating again
    num_facts = len(facts)

    elements.append(Spacer(1, 200))

    elements += [
        Paragraph("__COVER_PAGE__", ParagraphStyle("HiddenCoverMarker", fontSize=1, textColor=colors.white)),
        Spacer(1, 10),
        TransparentBox("WHAT HAPPENED ON...", styles['cover_title'], alpha=0.85),
        Spacer(1, 12),
        TransparentBox(f"{date_str}?", styles['cover_date'], alpha=0.85),
        Spacer(1, 60),
        TransparentBox("By Timothy John Mulrenan", styles['cover_date'], alpha=0.85)
    ]


    elements.append(PageBreak())

    intro_text = f"""
        Hey you — yeah, you with the excellent taste in books. Whether today’s your birthday, your dog’s birthday, or just a totally random spin of the calendar wheel — this book is here to make your day 100% more interesting.

        I’m TJ — your guide, fact hoarder, and proud human from Saffron Walden (it's a town, not a wizard spell, I checked). I’ve spent way too much time digging through history books, science sites, fun facts, and the weird corners of the internet so you don’t have to.

        So the big question is: <b>What happened on {date_str}?</b>

        Flip the page, trust the chaos, and become the class trivia weapon your teacher never saw coming.
        <br/><br/><br/><b>— TJ</b>"""

    elements.append(Paragraph(
        "__INTRO_PAGE__",
        ParagraphStyle("HiddenIntroMarker", fontSize=1, textColor=colors.white)
    ))
    elements += [
        TransparentBox("Before we begin!", styles['intro_header'], alpha=0.85),
        Spacer(1, 12),
        TransparentBox(intro_text.strip(), styles['intro'], alpha=0.85)
    ]

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

        table = Table(toc_data, colWidths=[380, 40], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -2), 0.25, colors.darkgrey),
        ]))

        # ⛔ Force TOC to stay together on one page
        toc_block = KeepTogether([
            TransparentBox("<para align='center'><b>Table of Contents</b></para>", styles['toc_title'], alpha=0.85),
            
            # Hidden marker before the table
            Paragraph("__TOC_PAGE__", ParagraphStyle("HiddenTOCMarker", fontSize=1, textColor=colors.grey)),

            Spacer(1, 12),

            # ✅ Table wrapped in TransparentBox
            TransparentBox(table, styles['story'], alpha=0.85),

            # Hidden end marker
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

    # Vibe Check intro in transparent boxes
    vibe_intro = KeepTogether([
        Paragraph("<para align='center'><b>Today's Vibe Check</b></para>", styles['category']),
    #     TransparentBox("<para align='center'><b>Today's Vibe Check</b></para>", styles['cat_title'], alpha=0.85),
    #     Spacer(1, 10),
    #     TransparentBox(
    #         "What's the deal with this day? Seasonal chaos, sky weirdness, animal drama — it's all happening.",
    #         styles['story'],
    #         alpha=0.85
        # )
    ])
    elements.append(vibe_intro)

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
                    TransparentBox(f"• {fact['fact']}", styles['story'], alpha=0.85),
                    # Spacer(1, 10)
                ])
                elements.append(fact_block)
                added_any = True

        if not added_any:
            elements.append(Paragraph("No kid-friendly facts available today.", styles['story']))
        elements.append(PageBreak())

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

    

    # Slay header and intro inside transparent boxes (matching Vibe Check)
    slay_intro = KeepTogether([
        Paragraph("<para align='center'><b>Days That Slay</b></para>", styles['category']),
    #     TransparentBox("<para align='center'><b>Days That Slay</b></para>", styles['cat_title'], alpha=0.85),
    #     Spacer(1, 10),
    #     TransparentBox(
    #         "The most extra, random, and delightful holidays hitting today. Weird food? Niche magic? Major vibes.",
    #         styles['story'],
    #         alpha=0.85
    #     )
    ])
    elements.append(slay_intro)
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
                    TransparentBox(f"<i>{entry['title']}</i>", styles['title']),
                    TransparentBox(entry["story"], styles['story'])
                ])
                elements.append(fact_block)
                added_any = True

        if not added_any:
            elements.append(Paragraph("No fun holidays hit today — weird!", styles['story']))

    except Exception as e:
        logging.warning(f"🚫 Could not load Days That Slay facts: {e}")
        elements.append(Paragraph("Oops! Slay day stories couldn’t load.", styles['story']))




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

# THIS IS FOR MAKING SURE A CATAGORY HAS AT LEAST 6 FACTS
    # # Reassign categories with fewer than 6 facts to stronger categories
    # reassigned = []
    # filtered_categories = {}

    # for cat, facts_in_cat in categories.items():
    #     if len(facts_in_cat) < 6:
    #         for fact in facts_in_cat:
    #             reassigned.append(fact)
    #     else:
    #         filtered_categories[cat] = facts_in_cat

    # for fact in reassigned:
    #     reassigned_to = False
    #     for alt_cat in fact.get("categories", []):
    #         if alt_cat in filtered_categories:
    #             filtered_categories[alt_cat].append(fact)
    #             reassigned_to = True
    #             break
    #     if not reassigned_to:
    #         filtered_categories.setdefault("Extra Awesome Facts 🌟", []).append(fact)

    # categories = filtered_categories

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
            logging.info(f"📚 Category: {category} — {len(fact_list)} facts")

        # 🔁 PageBreak starts a new page with the category title
        elements.append(PageBreak())
        
        title = Paragraph(f"<b>{category}</b>", styles['cat_title'])
        desc = CATEGORY_DESCRIPTIONS.get(category, "")
        desc_paragraph = Paragraph(desc, styles['story'])

        # Build content as a block (TOC-compatible + transparent visuals)
        title_block = KeepTogether([
            Spacer(1, 12),
            
            # ⚠️ Paragraph version just to support TOC logic (not visible in output)
            Paragraph(f"<b>{category}</b>", styles['category']),
            
            # # ✅ TransparentBox version for actual visual appearance
            # TransparentBox(f"<para align='center'><b>{category}</b></para>", styles['cat_title'], alpha=0.85),
            
            # Spacer(1, 12),
            # TransparentBox(f"<para align='center'>{desc}</para>", styles['story'], alpha=0.85),
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
                TransparentBox(f"<i>{fact['title']}</i>", styles['title']),
                TransparentBox(fact["story"], styles['story'])
            ])
            elements.append(fact_block)

        elements.append(PageBreak())

        # Add centered trivia intro block
        estimated_content_height = 180
        spacer_height = max(0, (letter[1] - estimated_content_height) / 2 - 50)
        elements.append(Spacer(1, spacer_height))

        # Trivia intro inside TransparentBoxes
        # trivia_intro = KeepTogether([
        #     TransparentBox("Trivia Time!", styles['trivia_title'], alpha=0.85),
        #     Spacer(1, 10),
        #     TransparentBox(
        #         "Test your brainpower with some tricky questions from this chapter. "
        #         "Get them right and you might just become the world’s next quiz champion!",
        #         styles['story'],
        #         alpha=0.85
        #     )
        # ])
        # elements.append(trivia_intro)

        # Trivia marker (kept outside the box for parsing accuracy)
        elements.append(Paragraph(
            f"__TRIVIA_START__{category}",
            ParagraphStyle("HiddenTriviaMarker", fontSize=1, textColor=colors.white)
        ))
        elements.append(PageBreak())

        logging.info(f"🧠 Trivia start marker added for category: {category}")

        # Questions block
        elements.append(
            TransparentBox(
                Paragraph("Questions", styles['cat_title']),
                styles['story'],
                alpha=0.85
            )
        )


        # Add each question and checkbox table
        for fact in fact_list:
            q = fact.get("activity_question")
            choices = fact.get("activity_choices", [])
            if q and choices:
                question_paragraph = Paragraph(f"<b>{question_number}.</b> {q}", styles['trivia_questions'])
                checkboxes = [Paragraph(f"☐ {opt}", styles['trivia_questions']) for opt in choices]
                grid = [checkboxes[i:i+2] for i in range(0, len(checkboxes), 2)]
                if len(grid[-1]) == 1:
                    grid[-1].append("")

                table = Table(grid, colWidths=[210, 210])
                table.setStyle(TableStyle([
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LINEBELOW', (0, 0), (-1, -2), 0.25, colors.grey),
                    ('LINEAFTER', (0, 0), (0, -1), 0.25, colors.grey),
                ]))


                # Wrap each question in its own TransparentBox
                elements.append(TransparentBox([
                    question_paragraph,
                    Spacer(1, 4),
                    table
                ], styles['trivia_questions'], alpha=0.85))

                question_number += 1 
                # elements.append(Spacer(1, 12))

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
        # elements.append(Spacer(1, 20))  # space before image

        # Word search image (centered below description)
        category_key = CATEGORY_BACKGROUNDS.get(category, '').lower()
        image_path = os.path.join(
            "C:/Users/timmu/Documents/repos/Factbook Project/wordsearch",
            f"{category_key}.png"
        )
        if os.path.exists(image_path):
            try:
                img_reader = ImageReader(image_path)
                original_width, original_height = img_reader.getSize()

                # Set fixed height
                desired_height = 450
                aspect_ratio = original_width / original_height
                new_width = desired_height * aspect_ratio

                elements.append(Spacer(1, -10))
                elements.append(RLImage(image_path, width=new_width, height=desired_height))
                elements.append(Spacer(1, -10))
            except Exception as e:
                logging.warning(f"❌ Could not scale image properly: {e}")
        else:
            elements.append(Paragraph("Word search image not found.", styles['story']))
        # Word list below the picture
        all_words_path = os.path.join(
            "C:/Users/timmu/Documents/repos/Factbook Project/wordsearch",
            "letter_quest_words.json"
        )
        if os.path.exists(all_words_path):
            try:
                with open(all_words_path, "r", encoding="utf-8") as f:
                    all_words = json.load(f)
                words = all_words.get(category_key, [])
                if words:
                    # Wrap words by total character length per line
                    max_chars_per_line = 90  # Adjust this as needed
                    lines = []
                    current_line = ""
                    for word in words[:20]:
                        word_upper = word.upper()
                        if len(current_line) + len(word_upper) + 6 > max_chars_per_line:  # 6 for spacing
                            lines.append(current_line.strip())
                            current_line = ""
                        current_line += word_upper + "      "  # 6 spaces
                    if current_line:
                        lines.append(current_line.strip())

                    # Combine into a single paragraph with <br/> line breaks
                    inline_text = "<para align='center'>" + "<br/>".join(lines) + "</para>"

                    word_block = TransparentBox(
                        Paragraph(inline_text, styles['wordsearch']),
                        styles['wordsearch'],
                        alpha=0.85,
                        padding=10
                    )
                    elements.append(word_block)
                else:
                    elements.append(Paragraph("No word list found for this category.", styles['story']))
            except Exception as e:
                logging.warning(f"❌ Could not load Letter Quest words: {e}")
                elements.append(Paragraph("Couldn’t load word list!", styles['story']))
        else:
            elements.append(Paragraph("Word list file is missing!", styles['story']))



        # # Answers
        # elements.append(PageBreak())
        # elements.append(
        #     TransparentBox(
        #         Paragraph("Answers", styles['cat_title']),
        #         styles['story'],
        #         alpha=0.85
        #     )
        # )

        elements.append(Spacer(1, 12))

        for i, fact in enumerate(fact_list, 1):
            q = fact.get("activity_question")
            a = fact.get("activity_answer")
            if q and a:
                global_answers.append((q, a))


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

    if global_answers:
        elements.append(PageBreak())

        elements.append(
            TransparentBox(
                Paragraph("Answers", styles['cat_title']),
                styles['story'],
                alpha=0.85
            )
        )

    elements.append(Spacer(1, 12))

    for i, (q, a) in enumerate(global_answers, 1):
        para = Paragraph(f"<b>{i}.</b> {q}<br/><b>Answer:</b> {a}", styles['trivia_answers'])
        elements.append(TransparentBox([para], styles['trivia_answers'], alpha=0.85, padding=4, inner_spacing=0))

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
            base_path = os.path.join("backgrounds", "trivia_time.png")
            title_path = os.path.join("backgrounds", "trivia_time_t.png")
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
            t_path = os.path.join("backgrounds", f"{bg_base}_t.png")
            normal_path = os.path.join("backgrounds", f"{bg_base}.png")

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

    # Font registration
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join("fonts", "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join("fonts", "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", os.path.join("fonts", "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", os.path.join("fonts", "DejaVuSans-BoldOblique.ttf")))
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")

    pdfmetrics.registerFont(TTFont("LuckiestGuy", "fonts/LuckiestGuy-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("Baloo2", "fonts/Baloo2-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("Baloo2-Bold", "fonts/Baloo2-Bold.ttf"))

    registerFontFamily("Baloo2", normal="Baloo2", bold="Baloo2-Bold")

    date_str = extract_date_with_suffix(json_file)

    # Styles
    styles = {
        'cover_title': ParagraphStyle(
            "CoverTitle", fontName="LuckiestGuy", fontSize=40, leading=34,
            alignment=TA_CENTER, spaceAfter=12
        ),
        'cover_date': ParagraphStyle(
            "CoverDate", fontName="Baloo2", fontSize=34, leading=26,
            alignment=TA_CENTER, spaceAfter=12
        ),
        'intro_header': ParagraphStyle(
            "IntroHeader", fontName="LuckiestGuy", fontSize=28, leading=20,
            alignment=TA_LEFT, spaceAfter=10
        ),
        'intro': ParagraphStyle(
            "Intro", fontName="Baloo2", fontSize=18, leading=18,
            spaceAfter=14
        ),
        'toc_title': ParagraphStyle(
            "TOCTitle", fontName="LuckiestGuy", fontSize=28, leading=22,
            spaceAfter=24, alignment=TA_CENTER
        ),
        'toc_item': ParagraphStyle(
            "TOCItem", fontName="Baloo2", fontSize=18, leading=14,
            spaceAfter=0, alignment=TA_LEFT
        ),
        'category': ParagraphStyle(
            "CategoryTitle", fontName="Baloo2", fontSize=0.1, leading=1,
            spaceAfter=0, textColor=colors.white, alignment=TA_LEFT
        ),
        'cat_title': ParagraphStyle(
            "CatTitle", fontName="LuckiestGuy", fontSize=28, leading=22,
            spaceAfter=12, spaceBefore=12
        ),
        'title': ParagraphStyle(
            "FactTitle", fontName="Baloo2-Bold", fontSize=22, leading=16,
            spaceAfter=6
        ),
        'story': ParagraphStyle(
            "FactStory", fontName="Baloo2", fontSize=18, leading=19,
            spaceAfter=16, spaceBefore=0
        ),
        'wordsearch': ParagraphStyle(
            "Wordsearch", fontName="Baloo2", fontSize=12, leading=19,
            spaceAfter=16, spaceBefore=0
        ),
        'trivia_title': ParagraphStyle(
            "TriviaTitle", fontName="LuckiestGuy", fontSize=24, leading=20,
            spaceAfter=12, alignment=TA_CENTER
        ),
        'trivia_questions': ParagraphStyle(
            "TriviaQuestions", fontName="Baloo2", fontSize=18, leading=19,
            spaceAfter=6, spaceBefore=0
        ),
        'trivia_answers': ParagraphStyle(
            "TriviaAnswers", fontName="Baloo2", fontSize=14, leading=12,
            spaceAfter=2, spaceBefore=0
        )

    }

    # styles = {
    #     'cover_title': ParagraphStyle(
    #         "CoverTitle", fontName="DejaVu-Bold", fontSize=28, leading=34,
    #         alignment=TA_CENTER, spaceAfter=12
    #     ),
    #     'cover_date': ParagraphStyle(
    #         "CoverDate", fontName="DejaVu", fontSize=20, leading=26,
    #         alignment=TA_CENTER, spaceAfter=12
    #     ),
    #     'intro_header': ParagraphStyle(
    #         "IntroHeader", fontName="DejaVu-Bold", fontSize=16, leading=20,
    #         alignment=TA_LEFT, spaceAfter=10
    #     ),
    #     'intro': ParagraphStyle(
    #         "Intro", fontName="DejaVu", fontSize=14, leading=18,
    #         spaceAfter=14
    #     ),
    #     'toc_title': ParagraphStyle(
    #         "TOCTitle", fontName="DejaVu-Bold", fontSize=18, leading=22,
    #         spaceAfter=24, alignment=TA_CENTER
    #     ),
    #     'toc_item': ParagraphStyle(
    #         "TOCItem", fontName="DejaVu", fontSize=12, leading=14,
    #         spaceAfter=0, alignment=TA_LEFT
    #     ),
    #     'category': ParagraphStyle(
    #         "CategoryTitle", fontName="DejaVu", fontSize=0.1, leading=1,
    #         spaceAfter=0, textColor=colors.white, alignment=TA_LEFT
    #     ),
    #     'cat_title': ParagraphStyle(
    #         "CatTitle", fontName="DejaVu-Bold", fontSize=17, leading=22,
    #         spaceAfter=12, spaceBefore=12
    #     ),
    #     'title': ParagraphStyle(
    #         "FactTitle", fontName="DejaVu-BoldOblique", fontSize=13, leading=16,
    #         spaceAfter=6
    #     ),
    #     'story': ParagraphStyle(
    #         "FactStory", fontName="DejaVu", fontSize=15, leading=19,
    #         spaceAfter=16, spaceBefore=0
    #     ),
    #     'trivia_title': ParagraphStyle(
    #         "TriviaTitle", fontName="DejaVu-Bold", fontSize=16, leading=20,
    #         spaceAfter=12, alignment=TA_CENTER
    #     ),
    # }



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

def visually_fill_transparent_gaps(pdf_path, alpha=0.85, dpi=144):
    import fitz
    from PIL import Image, ImageDraw
    import numpy as np
    import io
    from itertools import groupby
    from operator import itemgetter
    import os

    doc = fitz.open(pdf_path)
    total_pages = min(len(doc), 10)
    print(f"📘 Patching up to {total_pages} pages...")

    for page_index in range(total_pages):
        page = doc[page_index]
        print(f"\n📄 Processing page {page_index + 1}/{total_pages}")

        # Render page at higher resolution
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(alpha=True, matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
        arr = np.array(img)
        height, width = arr.shape[:2]

        stripe_width = int(width * 0.02)
        candidates = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

        best_x = None
        max_bright_rows = -1
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
            if brightness > 130:  # lowered threshold
                bright_rows.append(y)

            if y % 20 == 0:  # print brightness every 20px
                print(f"🔍 y={y}, brightness={brightness:.1f}")


        blocks = []
        for _, g in groupby(enumerate(bright_rows), lambda ix: ix[0] - ix[1]):
            group = list(map(itemgetter(1), g))
            if len(group) > 3:
                start_y = min(group)
                end_y = max(group)
                block_slice = arr[start_y:end_y + 1, :, :3]
                avg_cols = np.mean(block_slice, axis=(0, 2))
                bright_cols = np.where(avg_cols > 160)[0]
                x_start = int(np.min(bright_cols)) if len(bright_cols) > 0 else 0
                x_end = int(np.max(bright_cols)) if len(bright_cols) > 0 else width
                blocks.append((start_y, end_y, x_start, x_end))

        draw = ImageDraw.Draw(img, "RGBA")
        gap_count = 0

        for i in range(len(blocks) - 1):
            top = blocks[i][1] + 1
            bottom = blocks[i + 1][0] - 1
            x_start = blocks[i][2]
            x_end = blocks[i][3]

            if bottom > top and (x_end - x_start) > 10:
                stripe = arr[top:bottom + 1, probe_x_start:probe_x_start + stripe_width, :3]
                row_brightness = np.mean(stripe, axis=(1, 2))
                is_white = row_brightness > 180

                min_height = 20
                max_gap = 12
                merged_runs = []
                current_start = current_end = None

                for j, val in enumerate(is_white):
                    if val:
                        if current_start is None:
                            current_start = j
                        current_end = j
                    else:
                        if current_start is not None and (j - current_end > max_gap):
                            if current_end - current_start + 1 >= min_height:
                                merged_runs.append((current_start, current_end))
                            current_start = current_end = None

                if current_start is not None and (current_end - current_start + 1 >= min_height):
                    merged_runs.append((current_start, current_end))

                for k in range(len(merged_runs) - 1):
                    fill_top = top + merged_runs[k][1] + 1
                    fill_bottom = top + merged_runs[k + 1][0] - 1
                    if fill_bottom > fill_top:
                        draw.rectangle(
                            [(x_start, fill_top), (x_end, fill_bottom)],
                            fill=(255, 255, 255, int(alpha * 255))
                        )
                        gap_count += 1
                        print(f"🩹 Page {page_index + 1}: patched y={fill_top}-{fill_bottom}")

        # Save debug output
        debug_path = pdf_path.replace(".pdf", f"_page{page_index + 1}_debug.png")
        img.save(debug_path)
        print(f"🖼️ Debug image saved: {debug_path}")

        # 🔴 TEST: Draw red cross to prove overlay is visible
        draw.line([(0, 0), (width, height)], fill=(255, 0, 0, 255), width=10)
        draw.line([(width, 0), (0, height)], fill=(255, 0, 0, 255), width=10)

        # Reinsert using page.rect to match original PDF geometry
        out_bytes = io.BytesIO()
        img.save(out_bytes, format="PNG")
        page.clean_contents()
        page.insert_image(
            page.rect,
            stream=out_bytes.getvalue(),
            overlay=True
        )

        print(f"✅ Page {page_index + 1} complete with {gap_count} gaps filled.")

    doc.saveIncr()
    doc.close()
    print("🎉 All done — first 10 pages patched and saved.")



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
    facts_dir = "C:/Users/timmu/Documents/repos/Factbook Project/facts/new fact grabber/5_catagorised"
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
            # visually_fill_transparent_gaps(r"C:\Users\timmu\Documents\repos\Factbook Project\books\fresh_test.pdf", alpha=0.85)



