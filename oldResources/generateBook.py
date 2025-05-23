import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, ListFlowable, ListItem
from reportlab.lib.styles import ParagraphStyle
import json

def clean_fact(fact):
    """Removes leading numbers and punctuation from a fact string."""
    return re.sub(r'^\d+\.\s*', '', fact).strip()  # Removes leading "1. ", "2. ", etc.

def generate_pdf(json_file, output_pdf):
    # Load JSON data
    with open(json_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Setup PDF document
    doc = SimpleDocTemplate(output_pdf, pagesize=letter)
    elements = []
    
    # Define styles
    category_style = ParagraphStyle('CategoryTitle', fontSize=16, fontName="Helvetica-Bold", spaceAfter=12)
    fact_style = ParagraphStyle('Fact', fontSize=12, fontName="Helvetica", spaceAfter=6)

    # Loop through all categories
    for category, facts in data.get("categories", {}).items():
        # Add category title
        elements.append(Paragraph(category, category_style))
        elements.append(Spacer(1, 12))  # Space after category title

        # Ensure facts are handled as a list
        if not isinstance(facts, list):
            print(f"⚠️ Warning: Expected a list of facts for category '{category}', but got {type(facts)}")
            continue

        # Remove numbering from each fact and format as bullet points
        bullet_points = [ListItem(Paragraph(clean_fact(fact), fact_style)) for fact in facts if fact.strip()]
        elements.append(ListFlowable(bullet_points, bulletType="bullet"))

        # Add a page break after each category
        elements.append(PageBreak())

    # Build the PDF
    doc.build(elements)
    print(f"✅ PDF saved as {output_pdf}")

# Example usage
generate_pdf("facts/Janurary_14.json", "books/What_Happened_On_Janurary_14.pdf")
