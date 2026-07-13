"""Zentrale Konfiguration. Alles über Environment-Variablen steuerbar.

Das System läuft vollständig offline mit deterministischen Fallbacks. Sobald echte
Provider-Keys gesetzt sind, werden automatisch die echten Dienste genutzt.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Config:
    # Verzeichnisse
    root: Path = ROOT
    db_path: Path = field(default_factory=lambda: ROOT / "output" / "autocontent.db")
    output_dir: Path = field(default_factory=lambda: ROOT / "output")
    assets_dir: Path = field(default_factory=lambda: ROOT / "output" / "assets")
    data_dir: Path = field(default_factory=lambda: ROOT / "data")

    # Video-Spezifikation (9:16 TikTok)
    width: int = 1080
    height: int = 1920
    fps: int = 30
    min_duration_s: float = 8.0
    max_duration_s: float = 90.0

    # Sprechtempo (Wörter pro Sekunde) für Timing-Schätzung
    words_per_second: float = 2.6
    min_scene_s: float = 1.8
    max_scene_s: float = 8.0

    # Qualitäts-Gate
    auto_publish_threshold: int = 80
    review_threshold: int = 60

    # Autonomie / Publishing
    publish_mode: str = field(default_factory=lambda: _env("PUBLISH_MODE", "dry_run"))  # dry_run | draft | direct_post

    # Provider-Keys (leer => Offline-Fallback)
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))

    # TikTok Login Kit + Content Posting API
    tiktok_access_token: str = field(default_factory=lambda: _env("TIKTOK_ACCESS_TOKEN"))
    tiktok_refresh_token: str = field(default_factory=lambda: _env("TIKTOK_REFRESH_TOKEN"))
    tiktok_client_key: str = field(default_factory=lambda: _env("TIKTOK_CLIENT_KEY"))
    tiktok_client_secret: str = field(default_factory=lambda: _env("TIKTOK_CLIENT_SECRET"))
    tiktok_redirect_uri: str = field(default_factory=lambda: _env("TIKTOK_REDIRECT_URI"))
    tiktok_privacy_level: str = field(default_factory=lambda: _env("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY"))

    # Link-Ingestion (yt-dlp + Whisper)
    whisper_model: str = field(default_factory=lambda: _env("WHISPER_MODEL", "base"))

    # Modell-IDs
    anthropic_model: str = field(default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-sonnet-5"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))

    # Retry
    max_retries: int = 4

    def ensure_dirs(self) -> None:
        for d in (self.output_dir, self.assets_dir, self.data_dir):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def llm_provider(self) -> str:
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "template"

    @property
    def tts_provider(self) -> str:
        if self.elevenlabs_api_key:
            return "elevenlabs"
        if self.openai_api_key:
            return "openai"
        return "silent"


CONFIG = Config()
