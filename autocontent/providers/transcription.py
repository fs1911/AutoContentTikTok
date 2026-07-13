"""Transkriptions-Service für Link-Input.

- Wenn eine `.transcript.json` neben/zur URL vorliegt oder mitgegeben wird, wird sie genutzt.
- Echte Anbindung (yt-dlp + Whisper/OpenAI) ist als Erweiterungspunkt vorgesehen und wird
  aktiv, sobald die Werkzeuge/Keys vorhanden sind.

Format eines Transkripts: Liste von Segmenten {start, end, text}.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class Transcriber:
    name = "base"

    def transcribe(self, url: str, provided: Optional[list] = None) -> list[dict]:
        if provided:
            return provided
        # Erweiterungspunkt: yt-dlp Audio-Download + Whisper.
        # Offline liefern wir ein leeres Transkript -> Rights/Planning behandeln das.
        return []


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
