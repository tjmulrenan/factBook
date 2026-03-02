#!/usr/bin/env python3
"""
Adjust PNG backgrounds for print (stronger lightening + pop).
- Lists PNGs in ./backgrounds
- Pick by number(s) or 'all'
- Presets: Light, Strong, Ultra, and Auto (analyzes luminance)
- Vibrance (smart saturation) + Shadow lift + Midtone gamma
- Highlight protection + alpha preserved
- Renames original to *_old.png (auto-incrementing if exists),
  writes adjusted image with the original filename
Requires: Pillow, numpy
"""

import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PROJECT_ROOT, BACKGROUNDS_DIR

# ---- Paths ----
SRC_DIR = BACKGROUNDS_DIR

# --------- Core helpers ---------
def split_alpha(img: Image.Image):
    if img.mode in ("RGBA", "LA"):
        rgb = img.convert("RGBA")
        base = rgb.convert("RGB")
        alpha = rgb.split()[-1]
        return base, alpha
    return img.convert("RGB"), None

def merge_alpha(rgb: Image.Image, alpha):
    if alpha is None:
        return rgb
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out

def to_np(img: Image.Image):
    return np.asarray(img, dtype=np.uint8)

def from_np(arr: np.ndarray, mode="RGB"):
    return Image.fromarray(arr.astype(np.uint8), mode=mode)

def luminance_np(rgb_np: np.ndarray):
    r, g, b = rgb_np[...,0], rgb_np[...,1], rgb_np[...,2]
    return (0.2126*r + 0.7152*g + 0.0722*b).astype(np.float32)

def gamma_map(rgb_np: np.ndarray, gamma: float):
    if abs(gamma - 1.0) < 1e-6:
        return rgb_np
    inv = 1.0 / gamma
    lut = (np.linspace(0, 1, 256) ** inv * 255.0 + 0.5).astype(np.uint8)
    return lut[rgb_np]

def shadow_lift(rgb_np: np.ndarray, lift: int = 16, threshold: int = 180):
    if lift <= 0:
        return rgb_np
    L = luminance_np(rgb_np)
    w = np.clip(1.0 - (L / float(max(threshold,1))), 0.0, 1.0)[..., None]
    out = rgb_np.astype(np.int16) + (lift * w).astype(np.int16)
    return np.clip(out, 0, 255).astype(np.uint8)

def vibrance(rgb_img: Image.Image, amount: float = 0.35, protect_high: bool = True):
    if amount <= 0:
        return rgb_img
    hsv = rgb_img.convert("HSV")
    h, s, v = hsv.split()
    s_np = np.array(s, dtype=np.float32)
    v_np = np.array(v, dtype=np.float32)

    s_norm = s_np / 255.0
    boost = amount * (1.0 - s_norm)

    if protect_high:
        v_norm = v_np / 255.0
        boost *= (1.0 - np.clip((v_norm - 0.85) / 0.15, 0.0, 1.0))

    s_new = np.clip(s_np + boost * 255.0, 0, 255).astype(np.uint8)
    hsv = Image.merge("HSV", (h, Image.fromarray(s_new, mode="L"), v))
    return hsv.convert("RGB")

def contrast_enhance(img: Image.Image, factor: float):
    if abs(factor - 1.0) < 1e-6:
        return img
    return ImageEnhance.Contrast(img).enhance(factor)

def brightness_enhance(img: Image.Image, factor: float):
    if abs(factor - 1.0) < 1e-6:
        return img
    return ImageEnhance.Brightness(img).enhance(factor)

def saturation_enhance(img: Image.Image, factor: float):
    if abs(factor - 1.0) < 1e-6:
        return img
    return ImageEnhance.Color(img).enhance(factor)

def highlight_protect(base_np: np.ndarray, pre_np: np.ndarray, start: int = 220, end: int = 255):
    L = luminance_np(base_np)
    t = np.clip((L - start) / max(end - start, 1), 0.0, 1.0)[..., None]
    out = (pre_np.astype(np.float32) * (1.0 - t) + base_np.astype(np.float32) * t)
    return np.clip(out, 0, 255).astype(np.uint8)

# --------- Preset engine ---------
def apply_preset(img: Image.Image, preset: str = "STRONG"):
    base, alpha = split_alpha(img)
    base_np = to_np(base)
    L = luminance_np(base_np)
    mean_L = float(L.mean())

    if preset.upper() == "AUTO":
        if mean_L < 110:
            params = dict(bright=1.28, contrast=0.93, gamma=0.80, lift=22, vib=0.45, sat=1.12)
        elif mean_L < 135:
            params = dict(bright=1.22, contrast=0.94, gamma=0.85, lift=18, vib=0.40, sat=1.10)
        else:
            params = dict(bright=1.16, contrast=0.96, gamma=0.90, lift=12, vib=0.30, sat=1.08)
    elif preset.upper() == "ULTRA":
        params = dict(bright=1.30, contrast=0.92, gamma=0.78, lift=26, vib=0.50, sat=1.14)
    elif preset.upper() == "LIGHT":
        params = dict(bright=1.12, contrast=0.97, gamma=0.92, lift=10, vib=0.20, sat=1.06)
    else:  # STRONG
        params = dict(bright=1.22, contrast=0.95, gamma=0.82, lift=20, vib=0.38, sat=1.12)

    work = brightness_enhance(base, params["bright"])
    work = contrast_enhance(work, params["contrast"])
    work = saturation_enhance(work, params["sat"])
    work_np = gamma_map(to_np(work), params["gamma"])
    work_np = shadow_lift(work_np, lift=params["lift"], threshold=185)
    work = from_np(work_np, "RGB")
    work = vibrance(work, amount=params["vib"], protect_high=True)
    work_np = highlight_protect(base_np, to_np(work), start=225, end=255)

    return merge_alpha(from_np(work_np, "RGB"), alpha)

# --------- Helpers ---------
def next_old_name(src: Path) -> Path:
    """Finds the next available *_old.png name (increments if needed)."""
    base = src.stem
    parent = src.parent
    old = parent / f"{base}_old.png"
    if not old.exists():
        return old
    i = 2
    while True:
        candidate = parent / f"{base}_old{i}.png"
        if not candidate.exists():
            return candidate
        i += 1

def list_pngs(src_dir: Path):
    return sorted([p for p in src_dir.glob("*.png") if p.is_file()])

def parse_selection(sel_text: str, max_idx: int):
    sel_text = sel_text.strip().lower()
    if sel_text == "all":
        return list(range(1, max_idx + 1))
    nums = set()
    for part in sel_text.split(","):
        part = part.strip()
        if re.fullmatch(r"\d+", part):
            n = int(part)
            if 1 <= n <= max_idx:
                nums.add(n)
        elif re.fullmatch(r"\d+\s*-\s*\d+", part):
            a, b = re.split(r"\s*-\s*", part)
            a, b = int(a), int(b)
            if a > b: a, b = b, a
            for n in range(a, b + 1):
                if 1 <= n <= max_idx:
                    nums.add(n)
    return sorted(nums)

# --------- Main ---------
def main():
    print(f"\nLooking in: {SRC_DIR}")
    files = list_pngs(SRC_DIR)
    if not files:
        print("No PNG files found.")
        return

    print("\nPNG files:")
    for i, p in enumerate(files, 1):
        print(f"  {i:>2}. {p.name}")

    sel = input("\nSelect file number(s) ('1', '1,3,5', '2-6', or 'all'): ")
    idxs = parse_selection(sel, len(files))
    if not idxs:
        print("No valid selections. Exiting.")
        return

    print("\nPreset options:")
    print("  1) LIGHT")
    print("  2) STRONG (recommended)")
    print("  3) ULTRA")
    print("  4) AUTO (analyzes each image)")
    choice = (input("Choose 1–4 [2]: ").strip() or "2")
    preset = {"1":"LIGHT","2":"STRONG","3":"ULTRA","4":"AUTO"}.get(choice, "STRONG")
    print(f"\nApplying preset: {preset}\n")

    for n in idxs:
        src = files[n-1]
        try:
            # rename original to *_old*.png (increment if needed)
            old = next_old_name(src)
            shutil.move(str(src), str(old))

            with Image.open(old) as im:
                out = apply_preset(im, preset=preset)
                out.save(src, dpi=(300, 300))

            print(f"✅ Updated: {src.name} (original saved as {old.name})")

        except Exception as e:
            print(f"❌ {src.name}: {e}")

    print("\nDone. Originals renamed to *_old.png, *_old2.png, etc. New images saved with original names.")

if __name__ == "__main__":
    main()
