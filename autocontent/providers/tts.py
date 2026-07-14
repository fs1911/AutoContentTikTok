"""Voiceover-Engine (TTS).

Provider-Reihenfolge (automatisch):
  1. ElevenLabs / OpenAI  – echte Cloud-Stimme (Key nötig)
  2. espeak-ng            – echte OFFLINE-Stimme, kein Key/Host nötig (Standard)
  3. silent               – stiller Bett-Track (nur wenn espeak fehlt)

Interface: synthesize(text, out_path, target_duration, voice) -> tatsächliche Dauer (s).
Die Szenendauer richtet sich bei echter Stimme nach der Sprechlänge; der Assembler
zeigt das Bild exakt so lange. So bleiben Bild, Stimme und Untertitel synchron.
"""
from __future__ import annotations

import tempfile
import urllib.request
from pathlib import Path

from .. import espeak, ffmpeg_render as ff
from ..config import CONFIG


class BaseTTS:
    name = "base"
    real = False

    def synthesize(self, text: str, out_path: Path, target_duration: float,
                   voice: str = "de") -> float:
        raise NotImplementedError


class SilentTTS(BaseTTS):
    name = "silent"
    real = False

    def synthesize(self, text, out_path, target_duration, voice="de"):
        ff.silent_audio(target_duration, out_path)
        return target_duration


class EspeakTTS(BaseTTS):
    name = "espeak"
    real = True

    def synthesize(self, text, out_path, target_duration, voice="de"):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
            raw = Path(t.name)
        try:
            natural = espeak.synth_to_wav(text, raw, voice=voice)
            dur = max(CONFIG.min_scene_s, round(natural + 0.35, 2))
            ff.fit_audio(raw, dur, out_path)  # padded, keine Sprache abgeschnitten
            return dur
        finally:
            raw.unlink(missing_ok=True)


class _CloudTTS(BaseTTS):
    real = True

    def _fetch(self, text: str) -> bytes:  # pragma: no cover - netzabhängig
        raise NotImplementedError

    def synthesize(self, text, out_path, target_duration, voice="de"):
        try:
            audio = self._fetch(text)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as t:
                t.write(audio)
                raw = Path(t.name)
            natural = ff.audio_duration(raw)
            dur = max(CONFIG.min_scene_s, round(natural + 0.2, 2))
            ff.fit_audio(raw, dur, out_path)
            raw.unlink(missing_ok=True)
            return dur
        except Exception:
            return EspeakTTS().synthesize(text, out_path, target_duration, voice)


class ElevenLabsTTS(_CloudTTS):
    """Höchste Qualität, sehr natürliche deutsche Stimme (voice_id konfigurierbar)."""
    name = "elevenlabs"

    def _fetch(self, text):  # pragma: no cover
        import json
        body = json.dumps({
            "text": text,
            "model_id": CONFIG.elevenlabs_model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2},
        }).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{CONFIG.elevenlabs_voice_id}",
            data=body,
            headers={"content-type": "application/json", "accept": "audio/mpeg",
                     "xi-api-key": CONFIG.elevenlabs_api_key})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()


class OpenAITTS(_CloudTTS):
    """Sehr günstig, gute natürliche Stimme; Modell/Stimme konfigurierbar."""
    name = "openai"

    def _fetch(self, text):  # pragma: no cover
        import json
        body = json.dumps({"model": CONFIG.openai_tts_model,
                           "voice": CONFIG.openai_tts_voice, "input": text}).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech", data=body,
            headers={"content-type": "application/json",
                     "authorization": f"Bearer {CONFIG.openai_api_key}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()


def get_tts() -> BaseTTS:
    if CONFIG.elevenlabs_api_key:
        return ElevenLabsTTS()
    if CONFIG.openai_api_key:
        return OpenAITTS()
    if espeak.available():
        return EspeakTTS()
    return SilentTTS()
