import os
import re
import json
import logging
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
from PIL import Image as PILImage
from reportlab.platypus import Flowable
from reportlab.pdfbase.pdfmetrics import registerFontFamily

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

logging.basicConfig(level=logging.INFO, format="🔍 %(message)s")

CATEGORY_BACKGROUNDS = {}
CATEGORY_DESCRIPTIONS = {}  # Placeholder
final_categories_dict = {}  # For category-to-fact-id export

class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._page_tracker = {}
        self._current_category = None
        self._background_image = ImageReader(os.path.join("backgrounds", "spacefaint.png"))
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')
        template = PageTemplate(id='Content', frames=[frame], onPage=self.draw_background)
        self.addPageTemplates([template])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "CategoryTitle":
            text = flowable.getPlainText()
            self._page_tracker[text] = self.page

    def draw_background(self, canvas, doc):
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
        current_page = canvas.getPageNumber()
        if current_page in self._page_tracker.values():
            return
        if self._background_image:
            canvas.drawImage(self._background_image, 0, 0, width=letter[0], height=letter[1], mask='auto')
        self.add_page_number(canvas, doc)

    def add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        if page_num > 1:
            canvas.setFont("DejaVu", 10)
            canvas.drawRightString(570, 10, f"Page {page_num}")

def build_elements(facts, styles, date_str, category_pages=None):
    elements = []
    num_facts = len(facts)

    elements.append(Spacer(1, 200))
    elements += [
        Paragraph("WHAT HAPPENED ON...", styles['cover_title']),
        Paragraph(f"{date_str}?", styles['cover_date']),
        Spacer(1, 60),
        Paragraph("Written by Timothy John Mulrenan", styles['cover_date'])
    ]
    elements.append(PageBreak())

    intro_text = f"""
    Welcome to the amazing world of history, trivia, and delightfully random facts! This book is your guide to all the wild, weird, and wonderful things that happened around the world — and together, we’re about to answer the big question: <b>What happened on {date_str}?</b>

    I’m TJ, a fact-lover from Saffron Walden. Whether this date is your birthday, your lizard’s, or just a lucky guess — this book’s for you.

    There are <b>{num_facts}</b> facts packed into these pages. Let’s dive in!
    <br/><br/><br/><b>— TJ</b>"""
    elements.append(Paragraph("Before we begin!", styles['intro_header']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(intro_text.strip(), styles['intro']))
    elements.append(PageBreak())

    if category_pages:
        elements.append(Paragraph("Table of Contents", styles['toc_title']))
        toc_data = [[Paragraph(cat, styles['toc_item']), Paragraph(str(pg), styles['toc_item'])] for cat, pg in category_pages]
        table = Table(toc_data, colWidths=[380, 80], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        elements.append(table)

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
        logging.info(f"📦 Final total facts used in book: {final_total}")
            

    

    for category, fact_list in categories.items():
        if category_pages is None:
            logging.info(f"📚 Category: {category} — {len(fact_list)} facts")
        

        elements.append(PageBreak())
        elements.append(Paragraph(f"<b>{category}</b>", styles['category']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Here are the awesome facts in this category:", styles['story']))
        for i, fact in enumerate(fact_list, 1):
            elements.append(Paragraph(f"{i}. <i>{fact['title']}</i>", styles['story']))
        elements.append(PageBreak())

        for fact in fact_list:
            elements.append(Paragraph(f"<i>{fact['title']}</i>", styles['title']))
            elements.append(Paragraph(fact["story"], styles['story']))

        elements.append(PageBreak())
        elements.append(Paragraph("Trivia Time!", styles['category']))
        for i, fact in enumerate(fact_list, 1):
            q = fact.get("activity_question")
            choices = fact.get("activity_choices", [])
            if q and choices:
                elements.append(Paragraph(f"{i}. {q}", styles['story']))
                for idx, opt in enumerate(choices):
                    elements.append(Paragraph(f"    {chr(ord('A') + idx)}. {opt}", styles['story']))
        elements.append(PageBreak())
        elements.append(Paragraph("Answers", styles['category']))
        for i, fact in enumerate(fact_list, 1):
            q = fact.get("activity_question")
            a = fact.get("activity_answer")
            if q and a:
                elements.append(Paragraph(f"• {i}. {q} → <b>{a}</b>", styles['story']))

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


# The rest of the script remains unchanged (generate_pdf_with_manual_toc, extract_date_with_suffix, etc.)


def generate_pdf_with_manual_toc(json_file, output_pdf):
    with open(json_file, "r", encoding="utf-8") as f:
        facts = json.load(f)

    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join("fonts", "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join("fonts", "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", os.path.join("fonts", "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", os.path.join("fonts", "DejaVuSans-BoldOblique.ttf")))
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")

    date_str = extract_date_with_suffix(json_file)

    styles = {
        'cover_title': ParagraphStyle("CoverTitle", fontName="DejaVu-Bold", fontSize=28, alignment=TA_CENTER, spaceAfter=20),
        'cover_date': ParagraphStyle("CoverDate", fontName="DejaVu", fontSize=20, alignment=TA_CENTER),
        'intro_header': ParagraphStyle("IntroHeader", fontName="DejaVu-Bold", fontSize=18, spaceAfter=10, alignment=TA_LEFT),
        'intro': ParagraphStyle("Intro", fontName="DejaVu", fontSize=14, leading=22, spaceAfter=14),
        'toc_title': ParagraphStyle("TOCTitle", fontName="DejaVu-Bold", fontSize=20, spaceAfter=24, alignment=TA_CENTER),
        'toc_item': ParagraphStyle("TOCItem", fontName="DejaVu", fontSize=12, spaceAfter=0, leading=14, alignment=TA_LEFT),
        'category': ParagraphStyle("CategoryTitle", fontName="DejaVu-Bold", fontSize=18, spaceAfter=12, spaceBefore=12),
        'title': ParagraphStyle("FactTitle", fontName="DejaVu-BoldOblique", fontSize=13, spaceAfter=2, leading=14),
        'story': ParagraphStyle("FactStory", fontName="DejaVu", fontSize=11, spaceAfter=12, leading=15)
    }

    doc1 = MyDocTemplate(output_pdf, pagesize=letter, title=f"What Happened on {date_str}")
    elements1 = build_elements(facts, styles, date_str)
    doc1.build(elements1)
    category_pages = sorted(doc1._page_tracker.items(), key=lambda x: x[1])

    logging.info("🔄 Second pass: inserting manual TOC...")
    doc2 = MyDocTemplate(output_pdf, pagesize=letter, title=f"What Happened on {date_str}")
    elements2 = build_elements(facts, styles, date_str, category_pages)
    doc2.build(elements2)

    # Export final categories for debugging
    output_json = output_pdf.replace(".pdf", "_categories.json")
    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(final_categories_dict, out, indent=2)
    logging.info(f"📁 Categories exported to: {output_json}")

    logging.info(f"✅ PDF created at: {output_pdf}")


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
    facts_dir = os.path.join(base_dir, "facts", "newsorted")
    books_dir = os.path.join(base_dir, "books")
    os.makedirs(books_dir, exist_ok=True)

    for filename in os.listdir(facts_dir):
        if filename.endswith(".json"):
            json_path = os.path.join(facts_dir, filename)
            base_name = os.path.splitext(filename)[0]
            safe_pdf_path = get_unique_filename(books_dir, f"{base_name}.pdf")
            generate_pdf_with_manual_toc(json_path, safe_pdf_path)