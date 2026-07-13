"""Transkriptions-Service für Link-Input (echte YouTube-Aufnahme).

Ablauf:
  1. fetch_metadata(url)  -> echte Kanal-ID/Lizenz/Metadaten via yt-dlp (für Rechte-Check)
  2. download_audio(url)  -> Audiospur via yt-dlp (nutzt die gebündelte ffmpeg-Binary)
  3. transcribe(...)      -> Segmente mit Timecodes:
        - OpenAI Whisper API (wenn OPENAI_API_KEY gesetzt), sonst
        - faster-whisper lokal (wenn installiert), sonst
        - mitgegebenes Transkript (--transcript), sonst leer.

Alle externen Schritte sind optional und degradieren sauber: fehlt Netz/yt-dlp/Key,
liefert der Service, was verfügbar ist; der Rechte-Check bleibt fail-closed.
"""
from __future__ import annotations

import json
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Optional

import imageio_ffmpeg

from ..config import CONFIG


def _ytdlp_available() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:
        return False


def fetch_metadata(url: str) -> dict[str, Any]:
    """Echte Video-Metadaten. Wichtig für den Rechte-Check (echte channel_id)."""
    if not _ytdlp_available():
        return {}
    try:
        import yt_dlp
        opts = {"quiet": True, "skip_download": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "channel_id": info.get("channel_id") or info.get("uploader_id", ""),
            "channel": info.get("channel") or info.get("uploader", ""),
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "license": info.get("license", ""),
            "webpage_url": info.get("webpage_url", url),
        }
    except Exception:
        return {}


def download_audio(url: str, out_dir: Path) -> Optional[Path]:
    if not _ytdlp_available():
        return None
    try:
        import yt_dlp
        ffmpeg_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
        target = out_dir / "source_audio.%(ext)s"
        opts = {
            "quiet": True, "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": str(target),
            "ffmpeg_location": ffmpeg_dir,
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3"}],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        mp3 = out_dir / "source_audio.mp3"
        return mp3 if mp3.exists() else None
    except Exception:
        return None


def _transcribe_openai(audio: Path) -> list[dict]:
    """OpenAI Whisper API mit Wort-/Segment-Timecodes (multipart/form-data)."""
    import uuid
    boundary = uuid.uuid4().hex
    parts = []

    def field(name: str, value: str) -> bytes:
        return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n").encode()

    parts.append(field("model", "whisper-1"))
    parts.append(field("response_format", "verbose_json"))
    parts.append(field("timestamp_granularities[]", "segment"))
    file_bytes = audio.read_bytes()
    parts.append(
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
         f"filename=\"{audio.name}\"\r\nContent-Type: audio/mpeg\r\n\r\n").encode()
        + file_bytes + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions", data=body,
        headers={"Authorization": f"Bearer {CONFIG.openai_api_key}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
    return [{"start": s.get("start", 0.0), "end": s.get("end", 0.0),
             "text": s.get("text", "").strip()} for s in data.get("segments", [])]


def _transcribe_local(audio: Path) -> list[dict]:
    """faster-whisper, falls installiert."""
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return []
    model = WhisperModel(CONFIG.whisper_model, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio))
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]


class Transcriber:
    name = "yt-whisper"

    def transcribe(self, url: str, provided: Optional[list] = None,
                   work_dir: Optional[Path] = None) -> list[dict]:
        if provided:
            return provided
        work_dir = work_dir or Path(tempfile.mkdtemp())
        work_dir.mkdir(parents=True, exist_ok=True)
        audio = download_audio(url, work_dir)
        if audio is None:
            return []
        if CONFIG.openai_api_key:
            try:
                return _transcribe_openai(audio)
            except Exception:
                pass
        return _transcribe_local(audio)


def load_transcript_file(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "segments" in data:
        return data["segments"]
    return data if isinstance(data, list) else []


def get_transcriber() -> Transcriber:
    return Transcriber()
