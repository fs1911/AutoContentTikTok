"""SQLite Content-Hub. Eine zentrale `jobs`-Tabelle als Single Source of Truth.

Komplexe Felder (scenes, script, media, metriken) werden als JSON-Text abgelegt.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import Status, now_iso, new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id            TEXT PRIMARY KEY,
    created_at        TEXT NOT NULL,
    last_update       TEXT NOT NULL,
    input_type        TEXT NOT NULL,
    input_value       TEXT NOT NULL,
    topic             TEXT,
    language          TEXT DEFAULT 'de',
    content_type      TEXT,
    status            TEXT NOT NULL,
    rights_status     TEXT,
    reason_if_blocked TEXT,
    source_channel_id TEXT,
    license_ref       TEXT,
    transcript_json   TEXT,
    scenes_json       TEXT,
    script_json       TEXT,
    voiceover_url     TEXT,
    media_assets      TEXT,
    render_status     TEXT,
    video_url         TEXT,
    quality_score     INTEGER,
    quality_breakdown TEXT,
    publish_status    TEXT DEFAULT 'NONE',
    publish_mode      TEXT,
    scheduled_time    TEXT,
    tiktok_post_id    TEXT,
    caption           TEXT,
    hashtags          TEXT,
    cover_frame_ref   TEXT,
    views             INTEGER DEFAULT 0,
    watchtime         INTEGER DEFAULT 0,
    avg_view_duration REAL DEFAULT 0,
    saves             INTEGER DEFAULT 0,
    shares            INTEGER DEFAULT 0,
    follows           INTEGER DEFAULT 0,
    clicks            INTEGER DEFAULT 0,
    engagement_score  REAL DEFAULT 0,
    error_code        TEXT,
    retry_count       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS whitelist (
    channel_id  TEXT PRIMARY KEY,
    owner       TEXT,
    license_type TEXT,
    valid_from  TEXT,
    valid_to    TEXT,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    job_id    TEXT,
    module    TEXT,
    level     TEXT,
    message   TEXT
);
"""

# JSON-serialisierte Spalten
_JSON_FIELDS = {
    "transcript_json", "scenes_json", "script_json", "media_assets",
    "quality_breakdown", "hashtags",
}


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._columns = {r[1] for r in self.conn.execute("PRAGMA table_info(jobs)")}

    # --- Serialisierung -------------------------------------------------
    @staticmethod
    def _encode(data: dict[str, Any]) -> dict[str, Any]:
        out = dict(data)
        for f in _JSON_FIELDS:
            if f in out and not isinstance(out[f], (str, type(None))):
                out[f] = json.dumps(out[f], ensure_ascii=False)
        return out

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for f in _JSON_FIELDS:
            if d.get(f):
                try:
                    d[f] = json.loads(d[f])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    # --- CRUD -----------------------------------------------------------
    def create(self, input_type: str, input_value: str, language: str = "de") -> dict[str, Any]:
        job_id = new_id()
        ts = now_iso()
        self.conn.execute(
            "INSERT INTO jobs (job_id, created_at, last_update, input_type, input_value, "
            "language, status) VALUES (?,?,?,?,?,?,?)",
            (job_id, ts, ts, input_type, input_value, language, Status.NEW.value),
        )
        self.conn.commit()
        return self.get(job_id)

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._decode(row) if row else None

    def update(self, job_id: str, **fields: Any) -> dict[str, Any]:
        # Nur echte Spalten schreiben; unbekannte Keys (z. B. transiente Payload-Pfade)
        # werden ignoriert, damit Handler robust bleiben.
        fields = {k: v for k, v in fields.items() if k in self._columns}
        if not fields:
            return self.get(job_id)
        fields = self._encode(fields)
        fields["last_update"] = now_iso()
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE jobs SET {cols} WHERE job_id=?", (*fields.values(), job_id))
        self.conn.commit()
        return self.get(job_id)

    def list(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY created_at", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        return [self._decode(r) for r in rows]

    def pending(self) -> list[dict[str, Any]]:
        """Jobs, die noch weiterverarbeitet werden können (nicht terminal)."""
        terminal = (
            Status.BLOCKED.value, Status.FAILED_TERMINAL.value,
            Status.PUBLISHED.value, Status.OPTIMIZED.value, Status.REVIEW_REQUIRED.value,
        )
        q = "SELECT * FROM jobs WHERE status NOT IN ({}) ORDER BY created_at".format(
            ",".join("?" * len(terminal))
        )
        return [self._decode(r) for r in self.conn.execute(q, terminal).fetchall()]

    # --- Whitelist ------------------------------------------------------
    def add_whitelist(self, channel_id: str, owner: str = "", license_type: str = "OWN",
                      notes: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO whitelist (channel_id, owner, license_type, valid_from, notes) "
            "VALUES (?,?,?,?,?)",
            (channel_id, owner, license_type, now_iso(), notes),
        )
        self.conn.commit()

    def is_whitelisted(self, channel_id: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM whitelist WHERE channel_id=?", (channel_id,)
        ).fetchone()
        return dict(row) if row else None

    # --- Log ------------------------------------------------------------
    def log(self, job_id: Optional[str], module: str, message: str, level: str = "INFO") -> None:
        self.conn.execute(
            "INSERT INTO log (ts, job_id, module, level, message) VALUES (?,?,?,?,?)",
            (now_iso(), job_id, module, level, message),
        )
        self.conn.commit()

    def logs(self, job_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM log WHERE job_id=? ORDER BY id", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self.conn.close()
