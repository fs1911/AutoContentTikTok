"""Visual-Engine.

Standard (offline, kein Key): generiert pro Szene ein 1080x1920-Bild mit
Themen-Farbverlauf, grossem On-Screen-Text und Szenen-Badge (PIL + numpy).

Erweiterungspunkt: `get_visuals()` kann durch Stock-/AI-Provider ersetzt werden
(z. B. OpenAI Images, Stock-API). Jedes Asset trägt eine `license_ref`.
"""
from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..config import CONFIG

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _palette(seed: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Deterministische, kräftige Farbpaare aus dem Thema."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    hue = (h % 360) / 360.0
    import colorsys
    top = colorsys.hsv_to_rgb(hue, 0.55, 0.28)
    bot = colorsys.hsv_to_rgb((hue + 0.08) % 1.0, 0.65, 0.14)
    to255 = lambda c: tuple(int(x * 255) for x in c)
    return to255(top), to255(bot)


def _gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    ramp = np.linspace(0, 1, h)[:, None]
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(3):
        arr[:, :, i] = (top[i] * (1 - ramp) + bottom[i] * ramp).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


class PILVisuals:
    name = "pil"

    def render_scene(self, scene: dict, seed: str, out_path: Path) -> dict:
        w, h = CONFIG.width, CONFIG.height
        top, bottom = _palette(seed + scene.get("role", ""))
        img = _gradient(w, h, top, bottom)
        draw = ImageDraw.Draw(img)

        role = scene.get("role", "BODY")
        on_text = str(scene.get("on_screen_text", "")).strip()

        # Akzentbalken oben
        accent = tuple(min(255, int(c * 1.8) + 40) for c in top)
        draw.rectangle([0, 0, w, 16], fill=accent)
        draw.rectangle([0, h - 16, w, h], fill=accent)

        # Szenen-Badge (ausser Hook)
        if role == "BODY":
            badge = _font(64)
            draw.text((70, 120), f"#{scene.get('scene_id', 0) - 1}", font=badge, fill=accent)

        # Grosser On-Screen-Text: Schriftgröße auf Safe-Width einpassen.
        max_w = int(w * 0.86)
        size = 150 if role in ("HOOK", "CTA") else 120
        text_base = on_text or role
        for size in range(size, 44, -6):
            font = _font(size)
            wrap_at = max(6, int(max_w / (size * 0.6)))
            wrapped = textwrap.fill(text_base, width=wrap_at) or role
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=18)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw <= max_w and th <= h * 0.5:
                break
        # Schatten + Text
        cx, cy = w / 2, h * 0.42
        for dx, dy in ((4, 4), (-4, 4), (4, -4), (-4, -4)):
            draw.multiline_text((cx - tw / 2 + dx, cy - th / 2 + dy), wrapped, font=font,
                                fill=(0, 0, 0), align="center", spacing=18)
        draw.multiline_text((cx - tw / 2, cy - th / 2), wrapped, font=font,
                            fill=(255, 255, 255), align="center", spacing=18)

        img.save(out_path, "PNG")
        return {
            "scene_id": scene.get("scene_id"),
            "asset_url": str(out_path),
            "type": "image",
            "license_ref": "GEN-INTERNAL-PIL",
            "source": "generated",
        }


def get_visuals():
    return PILVisuals()
