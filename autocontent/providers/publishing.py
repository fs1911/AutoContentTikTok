"""Publishing-Engine (TikTok).

- DryRunPublisher: Standard. Schreibt das vollständige Publish-Payload als JSON auf Platte
  (keine externe Veröffentlichung) — sicher und vollständig nachvollziehbar.
- TikTokPublisher:  echte TikTok Content Posting API über autocontent.tiktok.
  * publish_mode 'direct_post' -> Direct Post (privacy_level aus Config)
  * publish_mode 'draft'       -> Upload in die TikTok-Inbox (Creator finalisiert manuell)
  Chunked Upload + Status-Polling inklusive.

Autonomie-Regel: Direct Post nur bei quality_score >= Schwelle UND rights_status APPROVED.
Diese Regel wird in der Pipeline (quality gate) durchgesetzt.
"""
from __future__ import annotations

import json
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
            "video_bytes": video_path.stat().st_size if video_path.exists() else 0,
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
        }


class TikTokPublisher(BasePublisher):
    name = "tiktok"

    def publish(self, job: dict[str, Any], video_path: Path) -> dict[str, Any]:
        from .. import tiktok
        title = _compose_title(job)
        try:
            token = tiktok.resolve_access_token()
            plan = tiktok.plan_chunks(video_path.stat().st_size)
            mode = job.get("publish_mode", "direct_post")

            if mode == "draft":
                init = tiktok.init_inbox_upload(token, plan)
            else:
                init = tiktok.init_direct_post(
                    token, title, plan, privacy_level=CONFIG.tiktok_privacy_level)

            data = init.get("data", {})
            publish_id = data.get("publish_id")
            upload_url = data.get("upload_url")
            if not publish_id or not upload_url:
                return {"publish_status": "FAILED",
                        "error_code": f"init ohne publish_id/upload_url: {init}"}

            tiktok.upload_file(upload_url, video_path, plan)
            status = tiktok.fetch_status(token, publish_id).get("data", {}).get("status", "PROCESSING")

            return {
                "publish_status": "PUBLISHED" if status in ("PUBLISH_COMPLETE",) else "PUBLISHING",
                "tiktok_post_id": publish_id,
            }
        except Exception as exc:  # noqa: BLE001 — Pipeline eskaliert
            return {"publish_status": "FAILED", "error_code": f"tiktok:{str(exc)[:180]}"}


def _compose_title(job: dict[str, Any]) -> str:
    caption = job.get("caption") or job.get("topic") or ""
    tags = " ".join(job.get("hashtags") or [])
    return (f"{caption} {tags}").strip()[:2200]


def get_publisher() -> BasePublisher:
    """Echte API nur bei draft/direct_post UND vorhandenen Credentials; sonst Dry-Run."""
    if CONFIG.publish_mode in ("direct_post", "draft"):
        if CONFIG.tiktok_access_token or CONFIG.tiktok_refresh_token:
            return TikTokPublisher()
    return DryRunPublisher()
