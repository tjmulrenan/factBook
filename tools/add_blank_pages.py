# add_blank_pages.py
# pip install pymupdf

import fitz  # PyMuPDF
from pathlib import Path

def add_blank_pages_to_manuscript():
    folder = Path(r"C:\Personal\What Happened On... (The Complete Collection)\196_July_14")
    input_path = folder / "full_manuscript_3.pdf"
    output_path = folder / "full_manuscript_3_blankpages.pdf"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Open the original PDF
    doc = fitz.open(input_path)

    if doc.page_count == 0:
        raise ValueError("Input PDF has no pages; cannot infer page size for blanks.")

    # Use the size of the first page for the blank pages
    first_page = doc.load_page(0)
    rect = first_page.rect
    width, height = rect.width, rect.height

    # Add 6 blank pages at the end
    for _ in range(6):
        doc.new_page(width=width, height=height)

    # Save as new file
    doc.save(output_path)
    doc.close()

    print(f"Saved new PDF with 6 blank pages appended to: {output_path}")

if __name__ == "__main__":
    add_blank_pages_to_manuscript()
