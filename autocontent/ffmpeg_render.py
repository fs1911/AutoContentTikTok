"""ffmpeg-Wrapper und Video-Assembly. Nutzt die von imageio-ffmpeg gebündelte
statische ffmpeg-Binary — keine System-Installation nötig.

Baut aus pro-Szene-Bildern + pro-Szene-Audio + ASS-Untertiteln ein 1080x1920 MP4
(H.264 / AAC), mit sanftem Ken-Burns-Zoom je Szene.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

import imageio_ffmpeg

from .config import CONFIG

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


class RenderError(RuntimeError):
    pass


def run(args: Sequence[str]) -> None:
    """Führt ffmpeg mit den gegebenen Argumenten aus (ohne führendes 'ffmpeg')."""
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(f"ffmpeg failed: {' '.join(args[:6])}...\n{proc.stderr[-800:]}")


def silent_audio(duration: float, out_path: Path) -> Path:
    """Erzeugt eine stille AAC-Spur exakter Länge (Offline-Voiceover-Fallback)."""
    run([
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", f"{duration:.3f}", "-c:a", "aac", "-b:a", "128k", str(out_path),
    ])
    return out_path


def fit_audio(src: Path, duration: float, out_path: Path) -> Path:
    """Schneidet/pad-et beliebiges Audio auf exakt `duration` Sekunden."""
    run([
        "-i", str(src),
        "-af", f"apad,atrim=0:{duration:.3f}",
        "-t", f"{duration:.3f}", "-c:a", "aac", "-b:a", "128k", str(out_path),
    ])
    return out_path


def scene_clip(image: Path, audio: Path, duration: float, out_path: Path,
               zoom: bool = True) -> Path:
    """Rendert eine Szene: Standbild (mit Ken-Burns-Zoom) + Audiospur."""
    w, h, fps = CONFIG.width, CONFIG.height, CONFIG.fps
    frames = max(1, int(duration * fps))
    if zoom:
        # sanfter Zoom von 1.0 auf 1.08
        vf = (
            f"scale={w*2}:{h*2},"
            f"zoompan=z='min(zoom+0.0007,1.08)':d={frames}:s={w}x{h}:fps={fps},"
            f"format=yuv420p"
        )
    else:
        vf = f"scale={w}:{h},format=yuv420p"
    run([
        "-loop", "1", "-framerate", str(fps), "-i", str(image),
        "-i", str(audio),
        "-vf", vf,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(out_path),
    ])
    return out_path


def concat_clips(clips: Sequence[Path], out_path: Path) -> Path:
    """Fügt Szenen-Clips verlustarm zusammen (concat demuxer)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for c in clips:
            f.write(f"file '{Path(c).resolve()}'\n")
        listfile = f.name
    try:
        run([
            "-f", "concat", "-safe", "0", "-i", listfile,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", str(out_path),
        ])
    finally:
        Path(listfile).unlink(missing_ok=True)
    return out_path


def burn_subtitles(video: Path, ass_file: Path, out_path: Path) -> Path:
    """Brennt ASS-Untertitel via libass in das Video."""
    ass = str(ass_file).replace("\\", "/").replace(":", r"\:")
    run([
        "-i", str(video),
        "-vf", f"ass={ass}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "copy", str(out_path),
    ])
    return out_path


def extract_cover(video: Path, out_path: Path, at: float = 0.5) -> Path:
    """Extrahiert einen Cover-Frame als JPG."""
    run(["-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out_path)])
    return out_path
