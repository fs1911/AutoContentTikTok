"""Voiceover-Engine (TTS).

- SilentTTS:     Offline-Fallback, erzeugt stille Spur exakter Länge (kein Key nötig).
- ElevenLabsTTS / OpenAITTS: echte Sprachsynthese via stdlib urllib (Key nötig).

Die Szenendauer wird von der Voiceover-Stufe vorgegeben; jede Spur wird exakt auf diese
Länge zugeschnitten, damit Bild und Untertitel synchron bleiben.
"""
from __future__ import annotations

import tempfile
import urllib.request
from pathlib import Path

from .. import ffmpeg_render as ff
from ..config import CONFIG


class BaseTTS:
    name = "base"

    def synthesize(self, text: str, duration: float, out_path: Path, voice: str = "default") -> Path:
        raise NotImplementedError


class SilentTTS(BaseTTS):
    name = "silent"

    def synthesize(self, text: str, duration: float, out_path: Path, voice: str = "default") -> Path:
        return ff.silent_audio(duration, out_path)


class ElevenLabsTTS(BaseTTS):
    name = "elevenlabs"
    VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Standardstimme

    def synthesize(self, text: str, duration: float, out_path: Path, voice: str = "default") -> Path:
        try:
            body = (
                b'{"text":' + _json_str(text).encode()
                + b',"model_id":"eleven_multilingual_v2"}'
            )
            req = urllib.request.Request(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.VOICE_ID}",
                data=body,
                headers={"content-type": "application/json",
                         "xi-api-key": CONFIG.elevenlabs_api_key},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                audio = r.read()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(audio)
                raw = Path(tmp.name)
            ff.fit_audio(raw, duration, out_path)
            raw.unlink(missing_ok=True)
            return out_path
        except Exception:
            return SilentTTS().synthesize(text, duration, out_path, voice)


class OpenAITTS(BaseTTS):
    name = "openai"

    def synthesize(self, text: str, duration: float, out_path: Path, voice: str = "alloy") -> Path:
        try:
            import json
            body = json.dumps({"model": "tts-1", "voice": voice, "input": text}).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/audio/speech", data=body,
                headers={"content-type": "application/json",
                         "authorization": f"Bearer {CONFIG.openai_api_key}"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                audio = r.read()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(audio)
                raw = Path(tmp.name)
            ff.fit_audio(raw, duration, out_path)
            raw.unlink(missing_ok=True)
            return out_path
        except Exception:
            return SilentTTS().synthesize(text, duration, out_path, voice)


def _json_str(s: str) -> str:
    import json
    return json.dumps(s, ensure_ascii=False)


def get_tts() -> BaseTTS:
    provider = CONFIG.tts_provider
    if provider == "elevenlabs":
        return ElevenLabsTTS()
    if provider == "openai":
        return OpenAITTS()
    return SilentTTS()
