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

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="🔍 %(message)s")

# ✅ Updated, humorous "on this day" category descriptions
CATEGORY_DESCRIPTIONS = {
    "Space Exploration": "On this day, humans (and sometimes monkeys!) dared to leave the planet and float among the stars. These stories remind us that space is awesome, weird, and occasionally full of duct tape fixes.",
    "Sporting Achievements": "On this very day, athletes wowed the world with epic wins, record-breaking moments, and maybe even a cartwheel or two. Sports history has never been this exciting!",
    "Scientific Discoveries": "On this day, some curious minds changed how we understand the universe. Beakers bubbled, lightbulbs blinked, and science got a little cooler.",
    "Famous Portraits": "On this day, the spotlight hit someone who made their mark in a big way. From presidents to pop stars, these people did something worth remembering—and now they’re in your book!",
    "Political History": "On this day, the world took a sharp turn, voted loudly, or made a surprising decision. Politics can be messy, wild, or downright funny—and history remembers every twist.",
    "Global Conflicts": "On this day, big disagreements shaped the world. But don’t worry—this version keeps things clear, thoughtful, and way less stressful than actual battle.",
    "Artistic Movements": "On this day, the world got more colorful, more creative, and a little more magical. These moments prove art can come from paint, poetry, or pure imagination.",
    "Technological Advances": "On this day, humans got a little more clever with wires, widgets, and what-ifs. These tech tales might just make you appreciate Wi-Fi a little more.",
    "Cultural Celebrations": "On this day, people around the world danced, feasted, or just had a good time celebrating something important. It’s a global party—and you’re invited!",
    "Environmental Moments": "On this day, the Earth got a helping hand. Whether planting trees or saving whales, these eco-friendly efforts deserve a standing ovation from Mother Nature herself."
}

def add_ordinal_suffix(day):
    if 10 <= day % 100 <= 20:
        return f"{day}th"
    return f"{day}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th') }"

def extract_date_with_suffix(filename):
    match = re.search(r'([A-Za-z]+)[ _]?(\d{1,2})', filename)
    if match:
        month = match.group(1)
        day = int(match.group(2))
        return f"{month} {add_ordinal_suffix(day)}"
    return "Unknown Date"

def get_unique_filename(directory, base_name):
    name, ext = os.path.splitext(base_name)
    counter = 1
    candidate = os.path.join(directory, base_name)
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{name}_{counter}{ext}")
        counter += 1
    return candidate

class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._page_tracker = {}
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')
        template = PageTemplate(id='Content', frames=[frame], onPage=self.add_page_number)
        self.addPageTemplates([template])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "CategoryTitle":
            text = flowable.getPlainText()
            logging.info(f"📌 TOC Entry: '{text}' on page {self.page}")
            self._page_tracker[text] = self.page

    def add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        if page_num > 1:
            canvas.setFont("DejaVu", 10)
            canvas.drawRightString(570, 10, f"Page {page_num}")

def build_elements(facts, styles, date_str, category_pages=None):
    elements = []
    elements.append(Spacer(1, 180))
    elements.append(Paragraph("WHAT HAPPENED ON...", styles['cover_title']))
    elements.append(Paragraph(date_str, styles['cover_date']))
    elements.append(PageBreak())

    if category_pages:
        elements.append(Paragraph("Table of Contents", styles['toc_title']))

        toc_data = [
            [Paragraph(cat, styles['toc_item']), Paragraph(str(pg), styles['toc_item'])]
            for cat, pg in category_pages
        ]
        table = Table(toc_data, colWidths=[380, 80], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),       # double spacing
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),   # double spacing
            ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        elements.append(table)
        elements.append(PageBreak())

    categories = {}
    for fact in facts:
        cat = fact.get("category", "Other")
        categories.setdefault(cat, []).append(fact)

    for category, fact_list in categories.items():
        logging.info(f"➡️ Processing category: {category} ({len(fact_list)} facts)")
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"<b>{category}</b>", styles['category']))  # Bold header
        if category in CATEGORY_DESCRIPTIONS:
            elements.append(Paragraph(CATEGORY_DESCRIPTIONS[category], styles['desc']))
        elements.append(Spacer(1, 6))

        for fact in fact_list:
            elements.append(KeepTogether([
                Paragraph(f"<i>{fact['title']}</i>", styles['title']),  # Italic title
                Paragraph(fact["story"], styles['story']),
                Spacer(1, 10)
            ]))

        elements.append(PageBreak())

    return elements

def generate_pdf_with_manual_toc(json_file, output_pdf):
    with open(json_file, "r", encoding="utf-8") as f:
        facts = json.load(f)

    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join("fonts", "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join("fonts", "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", os.path.join("fonts", "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", os.path.join("fonts", "DejaVuSans-BoldOblique.ttf")))

    date_str = extract_date_with_suffix(json_file)

    styles = {
    'cover_title': ParagraphStyle("CoverTitle", fontName="DejaVu-Bold", fontSize=28, alignment=TA_CENTER, spaceAfter=20),
    'cover_date': ParagraphStyle("CoverDate", fontName="DejaVu", fontSize=20, alignment=TA_CENTER),
    'toc_title': ParagraphStyle("TOCTitle", fontName="DejaVu-Bold", fontSize=20, spaceAfter=24, alignment=TA_CENTER),
    'toc_item': ParagraphStyle("TOCItem", fontName="DejaVu", fontSize=12, spaceAfter=0, leading=14, alignment=TA_LEFT),
    'category': ParagraphStyle("CategoryTitle", fontName="DejaVu-Bold", fontSize=18, spaceAfter=12, spaceBefore=12),
    'desc': ParagraphStyle("CategoryDesc", fontName="DejaVu-Oblique", fontSize=11, spaceAfter=12),
    'title': ParagraphStyle("FactTitle", fontName="DejaVu-BoldOblique", fontSize=13, spaceAfter=2, leading=14),
    'story': ParagraphStyle("FactStory", fontName="DejaVu", fontSize=11, spaceAfter=12, leading=15),
}


    # First pass
    doc1 = MyDocTemplate(output_pdf, pagesize=letter, title=f"What Happened on {date_str}")
    elements1 = build_elements(facts, styles, date_str)
    doc1.build(elements1)

    # TOC sorted by page number
    category_pages = sorted(doc1._page_tracker.items(), key=lambda x: x[1])

    # Second pass with TOC inserted
    logging.info("🔄 Second pass: inserting manual TOC...")
    doc2 = MyDocTemplate(output_pdf, pagesize=letter, title=f"What Happened on {date_str}")
    elements2 = build_elements(facts, styles, date_str, category_pages)
    doc2.build(elements2)
    logging.info(f"✅ PDF created at: {output_pdf}")

if __name__ == "__main__":
    base_dir = os.getcwd()
    facts_dir = os.path.join(base_dir, "facts", "sorted")
    books_dir = os.path.join(base_dir, "books")
    os.makedirs(books_dir, exist_ok=True)

    for filename in os.listdir(facts_dir):
        if filename.endswith(".json"):
            json_path = os.path.join(facts_dir, filename)
            base_name = os.path.splitext(filename)[0]
            safe_pdf_path = get_unique_filename(books_dir, f"{base_name}.pdf")
            generate_pdf_with_manual_toc(json_path, safe_pdf_path)