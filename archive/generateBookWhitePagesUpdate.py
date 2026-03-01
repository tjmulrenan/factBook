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

joke_path = os.path.join("jokes", "generatedJokes.json")
with open(joke_path, "r", encoding="utf-8") as jf:
    CATEGORY_JOKES = json.load(jf)

logging.basicConfig(level=logging.INFO, format="🔍 %(message)s")

CATEGORY_BACKGROUNDS = {
    "Space Exploration": "space",
    "Sporting Achievements": "sporting",
    "Scientific Discoveries": "scientific",
    "Famous Portraits": "famous",
    "Political History": "political",
    "Global Conflicts": "global",
    "Artistic Movements": "artistic",
    "Technological Advances": "technological",
    "Cultural Celebrations": "cultural",
    "Environmental Moments": "environmental"
}

CATEGORY_DESCRIPTIONS = {
    "Space Exploration": "Back on this very date, someone strapped into a rocket and blasted off into the unknown. Whether circling Earth or landing on moons, the great beyond got a little closer to home today.",
    "Sporting Achievements": "On a day just like today, a stadium somewhere shook with cheers as records were broken and champions rose. From muddy fields to Olympic arenas, sports history got a new chapter.",
    "Scientific Discoveries": "Long ago today, in a lab full of questions and caffeine, someone uncovered a truth that changed everything. Whether it was about stars, germs, or gravity—it happened today!",
    "Famous Portraits": "Somewhere in the world, on this very date, a person stepped into the spotlight and made their mark. From red carpets to battlefields, their story started (or soared) today.",
    "Political History": "On this historic date, decisions were made that shook nations. Whether in castles, capitals, or crowded voting halls, the world shifted in a big way today.",
    "Global Conflicts": "Today in history, disagreements turned into defining moments. Across borders and battle lines, choices made on this date shaped the future—for better or worse.",
    "Artistic Movements": "On this date, somewhere between a splash of paint and a spark of inspiration, art took a bold new turn. Whether in galleries or city streets, creativity left its mark today.",
    "Technological Advances": "Today in tech history, a clever idea lit up a screen, beeped to life, or changed how we live forever. From dusty garages to giant labs, innovation struck on this very date.",
    "Cultural Celebrations": "On this date, people around the world sang, danced, and celebrated what mattered most to them. From parades to quiet traditions, today was a time for joy.",
    "Environmental Moments": "Back on this day, someone took action for the Earth—protecting forests, saving animals, or cleaning up something messy. The planet gave a quiet thank you."
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

def prepare_light_background(image_path, output_path, alpha=0.2):
    with PILImage.open(image_path).convert("RGBA") as img:
        r, g, b, a = img.split()
        new_alpha = a.point(lambda p: int(p * alpha))
        faded_img = PILImage.merge("RGBA", (r, g, b, new_alpha))
        faded_img.save(output_path, "PNG")

class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._page_tracker = {}
        self._current_category = None
        self._background_image = None
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')
        template = PageTemplate(id='Content', frames=[frame], onPage=self.draw_background)
        self.addPageTemplates([template])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "CategoryTitle":
            text = flowable.getPlainText()
            self._page_tracker[text] = self.page
            self._current_category = re.sub(r"^[^\w]*\s*", "", text).strip()
            base_name = CATEGORY_BACKGROUNDS.get(self._current_category, self._current_category.split()[0].lower())

            orig_path = os.path.join(os.getcwd(), "backgrounds", f"{base_name}.webp")
            faded_path = os.path.join(os.getcwd(), "backgrounds", f"{base_name}faint.png")

            if os.path.exists(orig_path):
                logging.info(f"🎨 Found original background for '{self._current_category}': {orig_path}")
                if not os.path.exists(faded_path):
                    logging.info(f"🌫️ Generating faint version: {faded_path}")
                    prepare_light_background(orig_path, faded_path)
                else:
                    logging.info(f"✅ Using cached faint background: {faded_path}")
                self._background_image = ImageReader(faded_path)
            else:
                logging.warning(f"🚫 No background found for: {self._current_category}")
                self._background_image = None


    def draw_background(self, canvas, doc):
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)

        current_page = canvas.getPageNumber()
        
        # Don't draw background if this is a category title page
        if current_page in self._page_tracker.values():
            logging.info(f"📄 Skipping background on category page {current_page}")
            self._background_image = None  # Prevents leftover images on this page
        if self._background_image:
            canvas.drawImage(self._background_image, 0, 0, width=letter[0], height=letter[1], mask='auto')

        self.add_page_number(canvas, doc)


    def add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        if page_num > 1:
            canvas.setFont("DejaVu", 10)
            canvas.drawRightString(570, 10, f"Page {page_num}")

def build_elements(facts, styles, date_str, category_pages=None):
    elements = [Spacer(1, 180),
                Paragraph("WHAT HAPPENED ON...", styles['cover_title']),
                Paragraph(date_str, styles['cover_date']),
                PageBreak()]

    if category_pages:
        elements.append(Paragraph("Table of Contents", styles['toc_title']))
        toc_data = [[Paragraph(cat, styles['toc_item']), Paragraph(str(pg), styles['toc_item'])]
                    for cat, pg in category_pages]
        table = Table(toc_data, colWidths=[380, 80], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        elements.append(table)
        # ❌ No PageBreak here — categories start fresh anyway

    categories = {}
    for fact in facts:
        cat = fact.get("category", "Other")
        categories.setdefault(cat, []).append(fact)

    first_category = True  # 🟢 Only skip whiteout for the first category

    for category, fact_list in categories.items():
        elements.append(PageBreak())  # Always start each category on a new page
        logging.info(f"➡️ Processing category: {category} ({len(fact_list)} facts)")

        if first_category:
            # ✅ First category: keep background, no whiteout
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"<b>{category}</b>", styles['category']))
            if category in CATEGORY_DESCRIPTIONS:
                elements.append(Paragraph(CATEGORY_DESCRIPTIONS[category], styles['desc']))

            # 🖼 Image for first category (optional, on same page)
            image_path = os.path.join(os.getcwd(), "pictures", f"{category.split()[0].lower()}.png")
            if os.path.exists(image_path):
                elements.append(Spacer(1, 20))
                elements.append(RLImage(image_path, width=400, height=300))
                elements.append(Spacer(1, 20))

        else:
            # ✅ Later categories: whiteout background + all content on same page
            elements.append(WhiteoutPage(letter[0], letter[1]))  # ⬜ White background
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"<b>{category}</b>", styles['category']))
            if category in CATEGORY_DESCRIPTIONS:
                elements.append(Paragraph(CATEGORY_DESCRIPTIONS[category], styles['desc']))

            # 🖼 Image directly below description (same page)
            image_path = os.path.join(os.getcwd(), "pictures", f"{category.split()[0].lower()}.png")
            if os.path.exists(image_path):
                elements.append(Spacer(1, 20))
                elements.append(RLImage(image_path, width=400, height=300))
                elements.append(Spacer(1, 20))

        first_category = False  # ✅ Make sure the next iteration isn't "first"
        elements.append(PageBreak())  # ⏭ Start facts on a new page

        # ➕ Facts and jokes section
        page_word_limit = 375
        current_page_words = 0
        facts_on_this_page = 0
        max_facts_per_page = 3

        jokes_available = CATEGORY_JOKES.get(category, []).copy()

        for i, fact in enumerate(fact_list):
            story_words = len(fact["story"].split())
            will_exceed_word_limit = current_page_words + story_words > page_word_limit
            will_exceed_fact_limit = facts_on_this_page + 1 > max_facts_per_page

            # 👉 Insert joke if needed before breaking
            if (will_exceed_word_limit or will_exceed_fact_limit) and facts_on_this_page == 2:
                if jokes_available:
                    joke = jokes_available.pop(0)
                    joke_para = Paragraph(f"🃏 <i>{joke}</i>", styles['joke'])

                    joke_box = Table([[joke_para]], colWidths=[460])
                    joke_box.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                        ('BOX', (0, 0), (-1, -1), 0.25, colors.white),
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                    ]))
                    elements.append(Spacer(1, 20))
                    elements.append(KeepTogether([joke_box, Spacer(1, 12)]))

                elements.append(PageBreak())
                current_page_words = 0
                facts_on_this_page = 0

            # 📝 Add the fact
            fact_block = [
                [Paragraph(f"<i>{fact['title']}</i>", styles['title'])],
                [Paragraph(fact["story"], styles['story'])]
            ]
            table = Table(fact_block, colWidths=[460])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.25, colors.white),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(KeepTogether([table, Spacer(1, 10)]))

            current_page_words += story_words
            facts_on_this_page += 1

            if current_page_words > page_word_limit or facts_on_this_page >= max_facts_per_page:
                elements.append(PageBreak())
                current_page_words = 0
                facts_on_this_page = 0

    return elements

def generate_pdf_with_manual_toc(json_file, output_pdf):
    with open(json_file, "r", encoding="utf-8") as f:
        facts = json.load(f)

    # Font registration
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
        'joke': ParagraphStyle("Joke", fontName="DejaVu-Oblique", fontSize=10, textColor=colors.darkgrey, spaceBefore=6, spaceAfter=6, rightIndent=0),
        'white_marker': ParagraphStyle("WhiteOverlayMarker", fontSize=1, leading=1, textColor=colors.white, spaceAfter=0, spaceBefore=0)
    }

    # First pass: builds document and tracks category pages
    doc1 = MyDocTemplate(output_pdf, pagesize=letter, title=f"What Happened on {date_str}")
    elements1 = build_elements(facts, styles, date_str)
    doc1.build(elements1)

    category_pages = sorted(doc1._page_tracker.items(), key=lambda x: x[1])

    # Second pass: now with table of contents
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
