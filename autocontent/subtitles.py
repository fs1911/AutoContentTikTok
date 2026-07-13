"""Untertitel-Engine: erzeugt eine ASS-Datei (libass) und eine SRT-Sidecar.

Untertitel liegen in der Safe-Area (unteres Drittel, aber oberhalb der TikTok-UI),
hoher Kontrast, kräftiger Umriss.
"""
from __future__ import annotations

from pathlib import Path

from .config import CONFIG

_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,DejaVu Sans,64,&H00FFFFFF,&H00000000,&H64000000,-1,1,4,2,2,80,80,360,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _srt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap(text: str, width: int = 24) -> str:
    import textwrap
    return "\\N".join(textwrap.wrap(text, width=width)) or text


def build_ass(timed_scenes: list[dict], out_path: Path) -> Path:
    """timed_scenes: [{subtitle_text, start, end}]"""
    lines = [_ASS_HEADER.format(w=CONFIG.width, h=CONFIG.height)]
    for sc in timed_scenes:
        text = _wrap(str(sc.get("subtitle_text", "")).strip())
        if not text:
            continue
        lines.append(
            f"Dialogue: 0,{_ts(sc['start'])},{_ts(sc['end'])},Sub,,0,0,0,,{text}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def build_srt(timed_scenes: list[dict], out_path: Path) -> Path:
    blocks = []
    for i, sc in enumerate(timed_scenes, 1):
        text = str(sc.get("subtitle_text", "")).strip()
        if not text:
            continue
        blocks.append(f"{i}\n{_srt_ts(sc['start'])} --> {_srt_ts(sc['end'])}\n{text}\n")
    out_path.write_text("\n".join(blocks), encoding="utf-8")
    return out_path
