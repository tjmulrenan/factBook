import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta

# === CONFIG ===
INPUT_PATH = r"C:\Personal\factBook\cover\raw\cover.png"
FINAL_BASE_DIR = r"C:\Personal\What Happened On... (The Complete Collection)"

FONT_PATH = r"C:\Personal\factBook\fonts\Knewave-Regular.ttf"
FONT_MONTH_SIZE = 75
FONT_DAY_SIZE   = 180

TEXT_COLOR = (0, 0, 0, 255)  # pure black

# Position offsets (+X moves right, +Y moves down)
X_OFFSET = 5
Y_OFFSET = -80

# Vertical gap between month and day (negative pulls closer)
MONTH_DAY_GAP = -10

def generate_cover_for_date(d, output_filename="front_cover.png"):
    """Generate cover for a single date `d` (datetime), saving under
    FINAL/<DOY>_<Month>_<Day>/front_cover.png, where DOY is 1–366."""
    month_name = d.strftime("%B")
    day_num = d.day
    doy = d.timetuple().tm_yday  # 1..366 in leap year

    print(f"📅 Generating: DOY {doy} — {month_name} {day_num}")

    base_img = Image.open(INPUT_PATH).convert("RGBA")
    width, height = base_img.size

    # Render text onto its own layer (raw, no effects)
    text_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    font_month = ImageFont.truetype(FONT_PATH, size=FONT_MONTH_SIZE)
    font_day   = ImageFont.truetype(FONT_PATH, size=FONT_DAY_SIZE)

    # Measure
    bbox_month = draw.textbbox((0, 0), month_name.upper(), font=font_month)
    bbox_day   = draw.textbbox((0, 0), str(day_num), font=font_day)

    w_month = bbox_month[2] - bbox_month[0]
    h_month = bbox_month[3] - bbox_month[1]
    w_day   = bbox_day[2]   - bbox_day[0]
    h_day   = bbox_day[3]   - bbox_day[1]

    # Layout: day centered vertically; month above it
    y_day = (height - h_day) // 2 + Y_OFFSET
    x_day = (width  - w_day) // 2  + X_OFFSET

    y_month = y_day - MONTH_DAY_GAP - h_month
    x_month = (width - w_month) // 2 + X_OFFSET

    # Draw (raw)
    draw.text((x_month, y_month), month_name.upper(), font=font_month, fill=TEXT_COLOR)
    draw.text((x_day,   y_day),   str(day_num),       font=font_day,   fill=TEXT_COLOR)

    # Composite directly
    final_img = Image.alpha_composite(base_img, text_layer)

    # Save under "<DOY>_<Month>_<Day>"
    out_dir = os.path.join(FINAL_BASE_DIR, f"{doy}_{month_name}_{day_num}")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, output_filename)
    final_img.save(out_path)
    print(f"💾 Saved: {out_path}")

# === RUN FOR ALL DAYS IN A LEAP YEAR (INCLUDES FEB 29) ===
if __name__ == "__main__":
    start = datetime(2024, 1, 1)  # leap year so Feb 29 exists
    for i in range(366):
        generate_cover_for_date(start + timedelta(days=i))
