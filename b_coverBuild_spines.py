# colorize_spines_all_months_dark_rainbow.py
# pip install pillow numpy

import os, calendar, math, numpy as np
from datetime import date
from PIL import Image, ImageOps

# --- CONFIG ---
SPINES_DIR  = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\spines"
OUTPUT_BASE = r"C:\Users\timmu\Documents\repos\Factbook Project\FINAL"
YEAR        = 2024                 # leap year so Feb 29 exists
SEED        = 29                   # per-day wobble

# Darkness & saturation controls (tweak these)
SAT_CENTER      = 0.60             # target saturation for recolor (muted)
SAT_JITTER      = 0.06             # ± around target
V_MAX_DARK      = 0.55             # hard cap on brightness (lower = darker)
V_MIN_DARK      = 0.28             # floor so it doesn't go muddy/black
V_GAIN_BASE     = 0.95             # global multiplier on luminance (darken a touch)
V_GAIN_JITTER   = 0.02             # random micro-variance
V_GAMMA         = 1.20             # >1 darkens midtones; 1.0 = linear

FRONT_REF   = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\front.png"
BACK_REF    = r"C:\Users\timmu\Documents\repos\Factbook Project\cover\back.png"

# --- Helpers ---
def ensure_rgba(img: Image.Image) -> Image.Image:
    return img.convert("RGBA")

def wrap_deg(x): 
    return x % 360.0

def hue_full_wheel(index: int, total_needed: int) -> float:
    """Evenly distribute hues around the full 0..360° wheel."""
    if total_needed <= 1:
        return 0.0
    t = index / float(total_needed)   # 0..(1-1/total)
    return wrap_deg(t * 360.0)

def hsv_to_rgb_numpy(h, s, v):
    i = np.floor(h * 6).astype(int)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    i_mod = i % 6
    r = np.where(i_mod == 0, v, np.where(i_mod == 1, q, np.where(i_mod == 2, p, np.where(i_mod == 3, p, np.where(i_mod == 4, t, v)))))
    g = np.where(i_mod == 0, t, np.where(i_mod == 1, v, np.where(i_mod == 2, v, np.where(i_mod == 3, q, np.where(i_mod == 4, p, p)))))
    b = np.where(i_mod == 0, p, np.where(i_mod == 1, p, np.where(i_mod == 2, t, np.where(i_mod == 3, v, np.where(i_mod == 4, v, q)))))
    rgb = np.stack([r, g, b], axis=-1)
    rgb = np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)
    return rgb

def colorize_grayscale_dark(img_rgba: Image.Image, hue_deg: float, sat: float,
                            v_gain=1.0, v_gamma=1.0, v_min=0.0, v_max=1.0) -> Image.Image:
    arr = np.array(img_rgba)
    rgb = arr[..., :3].astype(np.float32) / 255.0
    alpha = arr[..., 3:4]

    # Use original luminance as V so highlight/shadow pattern is preserved
    v = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])
    v = np.clip(v * v_gain, 0.0, 1.0)
    if v_gamma != 1.0:
        v = np.power(v, v_gamma)
    v = np.clip(v, v_min, v_max)

    h = np.full_like(v, (hue_deg % 360) / 360.0, dtype=np.float32)
    s = np.full_like(v, np.clip(sat, 0.0, 1.0), dtype=np.float32)

    colored_rgb = hsv_to_rgb_numpy(h, s, v)
    out = np.concatenate([colored_rgb, alpha], axis=-1)
    return Image.fromarray(out, mode="RGBA")

def days_in_month(year: int, month_index: int) -> int:
    return calendar.monthrange(year, month_index)[1]

# --- Main ---
def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    rng = np.random.default_rng(SEED)

    for month_index in range(1, 13):
        month_name = calendar.month_name[month_index]
        spine_file = f"{month_name.lower()}.png"  # january.png, ...
        src_path = os.path.join(SPINES_DIR, spine_file)

        if not os.path.isfile(src_path):
            print(f"⚠️  Missing spine: {src_path}, skipping {month_name}...")
            continue

        base_img = ensure_rgba(Image.open(src_path))
        total_days = days_in_month(YEAR, month_index)

        for day in range(1, total_days + 1):
            # Hue selection + small wobble
            hue_deg = hue_full_wheel(day - 1, total_days)
            hue_deg = wrap_deg(hue_deg + float(rng.uniform(-4.0, 4.0)))

            sat = float(np.clip(SAT_CENTER + rng.uniform(-SAT_JITTER, SAT_JITTER), 0.40, 0.75))
            v_gain = float(np.clip(V_GAIN_BASE + rng.uniform(-V_GAIN_JITTER, V_GAIN_JITTER), 0.88, 1.02))

            colored = colorize_grayscale_dark(
                base_img,
                hue_deg=hue_deg,
                sat=sat,
                v_gain=v_gain,
                v_gamma=V_GAMMA,
                v_min=V_MIN_DARK,
                v_max=V_MAX_DARK
            )

            # Compute day-of-year (1..366) for the leap year
            d = date(YEAR, month_index, day)
            doy = d.timetuple().tm_yday  # includes Feb 29 because YEAR=2024

            # Save under "<DOY>_<Month>_<Day>"
            out_dir = os.path.join(OUTPUT_BASE, f"{doy}_{month_name}_{day}")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "spine.png")
            colored.save(out_path)
            print(f"Saved: {out_path}  (DOY={doy}, h≈{hue_deg:6.2f}°, s≈{sat:.2f}, vmax={V_MAX_DARK})")

if __name__ == "__main__":
    main()
