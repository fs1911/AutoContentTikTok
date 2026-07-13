"""Vollständiger Client für TikTok Login Kit (OAuth) + Content Posting API v2.

Deckt den kompletten Weg für echtes Veröffentlichen ab:
  1. OAuth Authorization-Code-Flow (authorization_url -> exchange_code)
  2. Token-Refresh
  3. Creator-Info-Abfrage (verfügbare privacy_levels)
  4. Direct-Post- bzw. Inbox(Draft)-Init
  5. Gechunkter Datei-Upload (Content-Range)
  6. Status-Polling

Alle Aufrufe laufen über die stdlib (urllib) — keine zusätzlichen Abhängigkeiten.
Ohne gesetzte Credentials/Netzwerk wirft der Client aussagekräftige Fehler, die die
Pipeline als Retry/Eskalation behandelt (der Dry-Run-Publisher bleibt der sichere Default).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG

AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
DIRECT_POST_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"
INBOX_INIT = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

MIN_CHUNK = 5 * 1024 * 1024        # 5 MB
MAX_CHUNK = 64 * 1024 * 1024       # 64 MB


class TikTokError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------
def _post_json(url: str, payload: dict, access_token: Optional[str] = None,
               timeout: int = 60) -> dict[str, Any]:
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:  # pragma: no cover - netzabhängig
        raise TikTokError(f"HTTP {e.code} @ {url}: {e.read().decode(errors='ignore')[:400]}")


def _post_form(url: str, form: dict, timeout: int = 60) -> dict[str, Any]:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:  # pragma: no cover
        raise TikTokError(f"HTTP {e.code} @ {url}: {e.read().decode(errors='ignore')[:400]}")


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------
def authorization_url(state: str = "xstate",
                      scopes: str = "video.publish,video.upload") -> str:
    if not CONFIG.tiktok_client_key or not CONFIG.tiktok_redirect_uri:
        raise TikTokError("TIKTOK_CLIENT_KEY und TIKTOK_REDIRECT_URI erforderlich.")
    q = urllib.parse.urlencode({
        "client_key": CONFIG.tiktok_client_key,
        "scope": scopes,
        "response_type": "code",
        "redirect_uri": CONFIG.tiktok_redirect_uri,
        "state": state,
    })
    return f"{AUTH_BASE}?{q}"


def exchange_code(code: str) -> dict[str, Any]:
    return _post_form(TOKEN_URL, {
        "client_key": CONFIG.tiktok_client_key,
        "client_secret": CONFIG.tiktok_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": CONFIG.tiktok_redirect_uri,
    })


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    return _post_form(TOKEN_URL, {
        "client_key": CONFIG.tiktok_client_key,
        "client_secret": CONFIG.tiktok_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })


def resolve_access_token() -> str:
    """Direkter Token hat Vorrang; sonst per Refresh-Token erneuern."""
    if CONFIG.tiktok_access_token:
        return CONFIG.tiktok_access_token
    if CONFIG.tiktok_refresh_token:
        data = refresh_access_token(CONFIG.tiktok_refresh_token)
        token = data.get("access_token")
        if not token:
            raise TikTokError(f"Refresh fehlgeschlagen: {data}")
        return token
    raise TikTokError("Kein TIKTOK_ACCESS_TOKEN oder TIKTOK_REFRESH_TOKEN gesetzt.")


# ---------------------------------------------------------------------------
# Chunk-Planung (reine Logik, unit-getestet)
# ---------------------------------------------------------------------------
@dataclass
class ChunkPlan:
    video_size: int
    chunk_size: int
    total_chunk_count: int

    def ranges(self) -> list[tuple[int, int]]:
        """[(start, end_inclusive)] gemäß TikTok-Regeln (letzter Chunk trägt den Rest)."""
        out = []
        for i in range(self.total_chunk_count):
            start = i * self.chunk_size
            end = (start + self.chunk_size - 1 if i < self.total_chunk_count - 1
                   else self.video_size - 1)
            out.append((start, end))
        return out


def plan_chunks(video_size: int, chunk_size: int = MIN_CHUNK) -> ChunkPlan:
    if video_size <= MIN_CHUNK:
        # Kleine Datei: genau ein Chunk in Dateigröße.
        return ChunkPlan(video_size, video_size, 1)
    chunk_size = max(MIN_CHUNK, min(chunk_size, MAX_CHUNK))
    total = video_size // chunk_size  # letzter Chunk nimmt den Rest mit
    return ChunkPlan(video_size, chunk_size, max(1, total))


# ---------------------------------------------------------------------------
# Content Posting
# ---------------------------------------------------------------------------
def query_creator_info(access_token: str) -> dict[str, Any]:
    return _post_json(CREATOR_INFO_URL, {}, access_token)


def init_direct_post(access_token: str, title: str, plan: ChunkPlan,
                     privacy_level: str = "SELF_ONLY",
                     cover_ms: int = 1000) -> dict[str, Any]:
    payload = {
        "post_info": {
            "title": title[:2200],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": cover_ms,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": plan.video_size,
            "chunk_size": plan.chunk_size,
            "total_chunk_count": plan.total_chunk_count,
        },
    }
    return _post_json(DIRECT_POST_INIT, payload, access_token)


def init_inbox_upload(access_token: str, plan: ChunkPlan) -> dict[str, Any]:
    payload = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": plan.video_size,
            "chunk_size": plan.chunk_size,
            "total_chunk_count": plan.total_chunk_count,
        }
    }
    return _post_json(INBOX_INIT, payload, access_token)


def upload_file(upload_url: str, video_path: Path, plan: ChunkPlan,
                timeout: int = 300) -> None:
    data = Path(video_path).read_bytes()
    total = plan.video_size
    for start, end in plan.ranges():
        chunk = data[start:end + 1]
        req = urllib.request.Request(upload_url, data=chunk, method="PUT")
        req.add_header("Content-Type", "video/mp4")
        req.add_header("Content-Length", str(len(chunk)))
        req.add_header("Content-Range", f"bytes {start}-{end}/{total}")
        try:
            with urllib.request.urlopen(req, timeout=timeout):
                pass
        except urllib.error.HTTPError as e:  # pragma: no cover
            # 201/206 kommen teils als "error" durch urllib – nur echte Fehler werfen
            if e.code not in (200, 201, 206):
                raise TikTokError(f"Upload-Chunk {start}-{end} fehlgeschlagen: HTTP {e.code}")


def fetch_status(access_token: str, publish_id: str) -> dict[str, Any]:
    return _post_json(STATUS_URL, {"publish_id": publish_id}, access_token)
