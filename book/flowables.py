import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import BLEED_IN, LOGS_DIR, TRIM_H_IN, TRIM_W_IN

from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Flowable, Paragraph,
)

BLEED_PT = BLEED_IN * inch

PAGE_W = (TRIM_W_IN + 2*BLEED_IN) * inch
PAGE_H = (TRIM_H_IN + 2*BLEED_IN) * inch

# Use the full bleed page size for the document
CUSTOM_PAGE_SIZE = (PAGE_W, PAGE_H)
CUSTOM_BLUE = Color(13/255, 78/255, 111/255)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(LOGS_DIR / "debug_output.log"), mode='w', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)


class OverlayRule(Flowable):
    """Opaque line drawn over the previous box (height=0 → no extra gap)."""
    def __init__(self, target_width=350, thickness=1.8, color=colors.darkgrey,
                 inset=5, offset_up=10):
        super().__init__()
        self.target_width = target_width    # line length
        self.thickness = thickness
        self.color = color
        self.inset = inset                  # left padding inside the box
        self.offset_up = offset_up          # how far up from the current y to draw

    def wrap(self, availWidth, availHeight):
        return 0, 0  # consume no vertical space

    def drawOn(self, canvas, x, y, _sW=0):
        # center horizontally like TransparentBox, then add left inset
        centered_x = (canvas._pagesize[0] - (self.target_width + 2*self.inset)) / 2 + self.inset
        super().drawOn(canvas, centered_x, y, _sW)

    def draw(self):
        c = self.canv
        # force full opacity (don't inherit box alpha)
        try: c.setFillAlpha(1); c.setStrokeAlpha(1)
        except Exception: pass
        c.setFillColor(self.color)
        c.rect(0, self.offset_up, self.target_width, self.thickness, stroke=0, fill=1)


class MidGapRule(Flowable):
    """Opaque horizontal rule drawn inside the <br/><br/> gap (no extra height)."""
    def __init__(self, width_pct=100, thickness=1.8,
                 color=colors.HexColor("#000000"), y_offset=0):
        super().__init__()
        self.width_pct = width_pct
        self.thickness = thickness
        self.color = color
        self.y_offset = y_offset

    def wrap(self, availWidth, availHeight):
        self._w = availWidth * (self.width_pct / 100.0)
        self._x = (availWidth - self._w) / 2.0  # center within text box
        return self._w, 0  # consume no vertical space

    def draw(self):
        c = self.canv
        c.saveState()
        # reset any inherited transparency
        try:
            c.setFillAlpha(1)
        except Exception:
            pass
        try:
            c.setStrokeAlpha(1)
        except Exception:
            pass

        c.setFillColor(self.color)
        # draw a filled rectangle (more solid than a stroked line under blending)
        h = float(self.thickness)
        # place it lower in the gap by y_offset (negative y goes down)
        c.rect(self._x, -self.y_offset - h/2.0, self._w, h, stroke=0, fill=1)
        c.restoreState()


class TransparentBox(Flowable):
    def __init__(self, content, style, width=None, height=None, padding=5, alpha=0.85, inner_spacing=None, border=False):
        super().__init__()
        self.style = style
        self.padding = padding
        self.alpha = alpha
        self.width = width if width is not None else 350
        self.height = height
        self.inner_spacing = 0 if inner_spacing is None else inner_spacing  # ✅ Add this
        self.border = border

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
        c = self.canv
        c.saveState()
        x = -self._cur_x if hasattr(self, '_cur_x') else 0

        # --- draw translucent background in an isolated state ---
        c.saveState()
        c.setFillColorRGB(1, 1, 1, alpha=self.alpha)
        if getattr(self, "border", False):
            c.setStrokeColor(colors.black)
            c.setLineWidth(2)
            c.rect(x, 0, self.eff_width, self.eff_height, fill=1, stroke=1)
        else:
            c.rect(x, 0, self.eff_width, self.eff_height, fill=1, stroke=0)
        c.restoreState()            # <<< resets alpha to 1 for content

        # (extra safety for older ReportLab builds)
        try: c.setFillAlpha(1); c.setStrokeAlpha(1)
        except Exception: pass

        # --- draw contents opaque ---
        content_width = self.eff_width - 2 * self.padding
        y_cursor = self.eff_height - self.padding
        for i, flowable in enumerate(self._content):
            w, h = flowable.wrap(content_width, self.eff_height)
            flowable.drawOn(c, self.padding, y_cursor - h)
            y_cursor -= h
            if i < len(self._content) - 1:
                y_cursor -= self.inner_spacing

        c.restoreState()


class FixedBottomTransparentBox(TransparentBox):
    def __init__(self, content, style, page_height, bottom_margin=30, **kwargs):
        super().__init__(content, style, **kwargs)
        self.page_height = page_height
        self.bottom_margin = bottom_margin

    def wrap(self, availWidth, availHeight):
        # Let it calculate internally, but report no height
        super().wrap(availWidth, availHeight)
        return 0, 0  # force ReportLab to "ignore" it for layout

    def drawOn(self, canvas, x, y, _sW=0):
        y_position = self.bottom_margin
        centered_x = (canvas._pagesize[0] - self.eff_width) / 2
        super().drawOn(canvas, centered_x, y_position, _sW)


class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        # Make sure you're building with pagesize=CUSTOM_PAGE_SIZE where you instantiate this doc
        super().__init__(filename, **kwargs)

        self._page_tracker = {}       # Tracks where each category starts
        self._background_ranges = []  # Stores start-end ranges with ImageReader backgrounds
        self._page_usage = {}         # Tracks used vertical space per page
        self._current_y_position = 0

        # Keep your original inside-trim margins the same (0.5")
        margin_in = 0.5
        margin_pt = margin_in * inch

        EXTRA_BOTTOM = 50  # points — stop text 20pts higher

        frame = Frame(
            x1=BLEED_PT + margin_pt,
            y1=BLEED_PT + margin_pt - 10 + EXTRA_BOTTOM,  # move bottom UP by 20
            width=(PAGE_W - 2*BLEED_PT) - 2*margin_pt,
            height=(PAGE_H - 2*BLEED_PT) - 2*margin_pt - 10 - EXTRA_BOTTOM,  # shrink by 20
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
                "__TOC_PAGE__", "__TOC_END__", "__INTRO_PAGE__", "__COVER_PAGE__", "__TODAYS_VIBE_CHECK__", "__ANSWERS_START__"
            ):
                self._page_tracker[text] = self.page

    # ===== BACKGROUNDS =====
    # Your draw_background already draws to full page; keep it that way:
    def draw_background(self, canvas, doc):
        current_page = canvas.getPageNumber()
        canvas.saveState()

        # Clear full page INCLUDING BLEED
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)

        # Draw background images full-page (0,0 to PAGE_W,PAGE_H)
        bg_range = None
        for bg in self._background_ranges:
            if bg["start"] <= current_page <= bg["end"]:
                bg_range = bg
                break

        if bg_range:
            try:
                img = bg_range.get("image")
                if not img and "image_path" in bg_range:
                    img = ImageReader(bg_range["image_path"])
                # Full-page draw = extends to bleed
                canvas.drawImage(img, 0, 0, width=doc.pagesize[0], height=doc.pagesize[1])
            except Exception as e:
                logging.warning(f"❌ Page {current_page}: Failed to draw background → {e}")

        canvas.restoreState()
        self.add_page_number(canvas, doc)

    # ===== PAGE NUMBERS (keep inside trim) =====
    def add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        if page_num >= 3:
            canvas.setFont("DejaVu", 12)
            canvas.setFillColorRGB(1, 1, 1)
            text = f"Page {page_num}"

            # Safe zone inside trim
            top_y = doc.pagesize[1] - BLEED_PT - 30  # 20pt down from top trim
            left_x = BLEED_PT + 28
            right_x = (doc.pagesize[0] - BLEED_PT) - 28

            if page_num % 2 == 0:
                # even pages = left corner
                canvas.drawString(left_x, top_y, text)
            else:
                # odd pages = right corner
                canvas.drawRightString(right_x, top_y, text)


