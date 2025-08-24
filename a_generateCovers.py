import os
from PIL import Image, ImageDraw, ImageFont, ImageTransform
import numpy as np
from datetime import datetime, timedelta

# === CONFIG ===
INPUT_PATH = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\raw\cover.png"
OUTPUT_DIR = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\complete"
OUTPUT_FILENAME = "March_29_cover.png"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)

TEXT_TOP = "DECEMBER"
TEXT_BOTTOM = "1"
FONT_PATH = r"C:\Users\timmu\Documents\repos\Factbook Project\fonts\Domine-Bold.ttf"
FONT_SIZE = 120
TEXT_COLOR = (0, 0, 0, 255)  # Black

# Offset config
X_OFFSET = 50  # move right
Y_OFFSET = -50  # move up

def generate_cover(month_name, day_num, output_filename):
    print(f"📅 Generating: {output_filename}")
    base_img = Image.open(INPUT_PATH).convert("RGBA")
    width, height = base_img.size

    text_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    font_month = ImageFont.truetype(FONT_PATH, size=60)
    font_day = ImageFont.truetype(FONT_PATH, size=250)

    bbox_month = draw.textbbox((0, 0), month_name.upper(), font=font_month)
    bbox_day = draw.textbbox((0, 0), str(day_num), font=font_day)

    w_month = bbox_month[2] - bbox_month[0]
    h_month = bbox_month[3] - bbox_month[1]
    w_day = bbox_day[2] - bbox_day[0]
    h_day = bbox_day[3] - bbox_day[1]

    gap = 30
    total_height = h_month + gap + h_day
    y_start = (height - total_height) // 2 + Y_OFFSET

    draw.text(((width - w_month) // 2 + 30, y_start), month_name.upper(), font=font_month, fill=TEXT_COLOR)
    draw.text(((width - w_day) // 2 + 30, y_start + h_month + gap), str(day_num), font=font_day, fill=TEXT_COLOR)

    text_np = np.array(text_layer).astype('int16')
    noise = np.random.normal(loc=0, scale=14, size=(height, width)).astype('int16')
    alpha_mask = text_np[..., 3] > 0
    for c in range(3):
        channel = text_np[..., c]
        channel[alpha_mask] += noise[alpha_mask]
        text_np[..., c] = np.clip(channel, 0, 255)
    text_np = text_np.astype('uint8')
    grainy_text_layer = Image.fromarray(text_np, mode='RGBA')

    skewed_text_layer = perspective_transform(grainy_text_layer, bottom_skew_x=350)

    canvas = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    canvas.paste(skewed_text_layer, (-150, 0), skewed_text_layer)
    final_img = Image.alpha_composite(base_img, canvas)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_img.save(os.path.join(OUTPUT_DIR, output_filename))

def find_perspective_coeffs(src, dst):
    """Calculate coefficients for a perspective transform."""
    matrix = []
    for p1, p2 in zip(dst, src):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0,
                      -p2[0]*p1[0], -p2[0]*p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1,
                      -p2[1]*p1[0], -p2[1]*p1[1]])

    A = np.array(matrix, dtype=np.float32)
    B = np.array(src).flatten()
    res = np.linalg.lstsq(A, B, rcond=None)[0]
    return res

def perspective_transform(image, bottom_skew_x=100):
    width, height = image.size
    src = [(0, 0), (width, 0), (width, height), (0, height)]

    # Shift the bottom-left and bottom-right points to the right
    dst = [
        (0, 0),                            # Top-left stays
        (width, 0),                        # Top-right stays
        (width + bottom_skew_x, height),   # Bottom-right shifted right
        (0 + bottom_skew_x, height)        # Bottom-left shifted right
    ]

    coeffs = find_perspective_coeffs(src, dst)
    return image.transform((width + bottom_skew_x, height), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC)


def draw_wiggly_text(draw, text, x, y, font, fill, max_angle=5):
    from PIL import Image

    for i, char in enumerate(text):
        angle = np.random.uniform(-max_angle, max_angle)

        # Create individual rotated letter
        letter_img = Image.new("RGBA", (FONT_SIZE * 2, FONT_SIZE * 2), (0, 0, 0, 0))
        letter_draw = ImageDraw.Draw(letter_img)
        letter_draw.text((FONT_SIZE // 2, FONT_SIZE // 2), char, font=font, fill=fill)
        rotated = letter_img.rotate(angle, resample=Image.BICUBIC, expand=1)

        # Paste onto the main text layer
        text_layer.alpha_composite(rotated, dest=(int(x), int(y)))
        w, _ = draw.textsize(char, font=font)
        x += w * 0.9  # spacing


# === LOAD BASE IMAGE ===
print("📥 Loading base image...")
base_img = Image.open(INPUT_PATH).convert("RGBA")
width, height = base_img.size
print(f"✅ Loaded image size: {width}x{height}")

# === DRAW TEXT ===
print("✏️ Drawing offset text...")
text_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(text_layer)
font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

# Use two different fonts: small for month, large for day number
font_month = ImageFont.truetype(FONT_PATH, size=60)   # e.g. MARCH
font_day = ImageFont.truetype(FONT_PATH, size=250)     # e.g. 29

# Measure sizes
bbox_month = draw.textbbox((0, 0), TEXT_TOP.upper(), font=font_month)
bbox_day = draw.textbbox((0, 0), TEXT_BOTTOM, font=font_day)

w_month = bbox_month[2] - bbox_month[0]
h_month = bbox_month[3] - bbox_month[1]
w_day = bbox_day[2] - bbox_day[0]
h_day = bbox_day[3] - bbox_day[1]

# Total height
gap = 30
total_height = h_month + gap + h_day
y_start = (height - total_height) // 2 + Y_OFFSET

# Draw month and big number
draw.text(((width - w_month) // 2 + 30, y_start), TEXT_TOP.upper(), font=font_month, fill=TEXT_COLOR)
draw.text(((width - w_day) // 2 + 30, y_start + h_month + gap), TEXT_BOTTOM, font=font_day, fill=TEXT_COLOR)



# === COMPOSITE AND SAVE ===
# === ADD GRAINY TEXTURE TO TEXT_LAYER ===
print("🌾 Adding soft grain to text...")
text_np = np.array(text_layer).astype('int16')  # to avoid overflow

# Softer grain (range -8 to +8)
noise = np.random.normal(loc=0, scale=14, size=(height, width)).astype('int16')
alpha_mask = text_np[..., 3] > 0  # Only modify text areas

for c in range(3):  # RGB channels
    channel = text_np[..., c]
    channel[alpha_mask] += noise[alpha_mask]
    text_np[..., c] = np.clip(channel, 0, 255)

# Convert back
text_np = text_np.astype('uint8')
grainy_text_layer = Image.fromarray(text_np, mode='RGBA')


print("📐 Skewing just the text layer...")

# Composite and paste back onto original canvas size
skewed_text_layer = perspective_transform(grainy_text_layer, bottom_skew_x=350)

# Create a new canvas same size as base image
canvas = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
canvas.paste(skewed_text_layer, (-150, 0), skewed_text_layer)

final_img = Image.alpha_composite(base_img, canvas)


print("📐 Applying slight perspective skew...")


# === RUN FOR ALL DAYS ===
leap_year = 2024  # Use a leap year to include Feb 29
start = datetime(leap_year, 1, 1)

for i in range(366):
    date = start + timedelta(days=i)
    month_name = date.strftime("%B")
    day_number = date.day
    filename = f"{month_name}_{day_number}_cover.png"
    generate_cover(month_name, day_number, filename)

print("✅ All covers generated!")

