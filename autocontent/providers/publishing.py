"""Publishing-Engine (TikTok).

- DryRunPublisher: Standard. Schreibt das vollständige Publish-Payload als JSON auf Platte
  (keine externe Veröffentlichung) — sicher und vollständig nachvollziehbar.
- TikTokPublisher:  echte TikTok Content Posting API (Direct Post / Draft), aktiv sobald
  TIKTOK_ACCESS_TOKEN gesetzt ist.

Autonomie-Regel: Direct Post nur bei quality_score >= Schwelle UND rights_status APPROVED.
Diese Regel wird in der Pipeline (quality gate) durchgesetzt, nicht hier.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from ..config import CONFIG
from ..models import now_iso


class BasePublisher:
    name = "base"

    def publish(self, job: dict[str, Any], video_path: Path) -> dict[str, Any]:
        raise NotImplementedError


class DryRunPublisher(BasePublisher):
    name = "dry_run"

    def publish(self, job: dict[str, Any], video_path: Path) -> dict[str, Any]:
        payload = {
            "endpoint": "TikTok Content Posting API (SIMULIERT)",
            "mode": job.get("publish_mode", "draft"),
            "video_file": str(video_path),
            "caption": job.get("caption"),
            "hashtags": job.get("hashtags"),
            "cover_frame": job.get("cover_frame_ref"),
            "scheduled_time": job.get("scheduled_time"),
            "created": now_iso(),
        }
        out = CONFIG.output_dir / f"publish_{job['job_id']}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "publish_status": "PUBLISHED",
            "tiktok_post_id": f"DRYRUN-{job['job_id'][:8]}",
            "publish_payload": str(out),
        }


class TikTokPublisher(BasePublisher):
    name = "tiktok"
    API = "https://open.tiktokapis.com/v2/post/publish/video/init/"

    def publish(self, job: dict[str, Any], video_path: Path) -> dict[str, Any]:
        try:
            body = json.dumps({
                "post_info": {
                    "title": job.get("caption", ""),
                    "privacy_level": "SELF_ONLY" if job.get("publish_mode") == "draft" else "PUBLIC_TO_EVERYONE",
                },
                "source_info": {"source": "FILE_UPLOAD",
                                "video_size": video_path.stat().st_size},
            }).encode()
            req = urllib.request.Request(
                self.API, data=body,
                headers={"content-type": "application/json; charset=UTF-8",
                         "authorization": f"Bearer {CONFIG.tiktok_access_token}"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            publish_id = data.get("data", {}).get("publish_id", "")
            return {"publish_status": "PUBLISHING", "tiktok_post_id": publish_id}
        except Exception as exc:  # noqa: BLE001 — Fehler wird eskaliert
            return {"publish_status": "FAILED", "error_code": f"tiktok:{exc}"}


def get_publisher() -> BasePublisher:
    if CONFIG.publish_mode == "direct_post" or CONFIG.publish_mode == "draft":
        if CONFIG.tiktok_access_token:
            return TikTokPublisher()
    return DryRunPublisher()
