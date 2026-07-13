"""Pipeline-Stufen. Jede Funktion ist ein idempotenter Worker:
liest den Job, produziert Output, gibt Feld-Updates zurück.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import CONFIG
from . import ffmpeg_render as ff
from . import subtitles as subs
from .llm import get_llm
from .models import ContentType, RightsStatus, Status
from .providers.publishing import get_publisher
from .providers.transcription import fetch_metadata, get_transcriber, load_transcript_file
from .providers.tts import get_tts
from .providers.visuals import get_visuals


# ---------------------------------------------------------------------------
# 1. Rights & Compliance (Gate #1 — hart, fail closed)
# ---------------------------------------------------------------------------
def _load_banned() -> list[str]:
    path = CONFIG.data_dir / "banned_terms.txt"
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line.lower())
    return terms


def _load_whitelist() -> set[str]:
    import json
    path = CONFIG.data_dir / "whitelist.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c["channel_id"] for c in data.get("channels", [])}


def _extract_channel(url_or_value: str) -> str:
    """Sehr defensiv: nur explizit mitgegebene channel_id wird akzeptiert.
    Format: 'https://youtu.be/xyz|channel_id=UC_XXX' oder '...?channel_id=UC_XXX'.
    Ohne belegbare Kanal-ID gilt die Quelle als unbekannt (=> BLOCKED)."""
    m = re.search(r"channel_id=([A-Za-z0-9_\-]+)", url_or_value)
    return m.group(1) if m else ""


def rights_check(job: dict[str, Any]) -> dict[str, Any]:
    banned = _load_banned()
    haystack = f"{job.get('input_value','')} {job.get('topic','')}".lower()
    hit = next((t for t in banned if t in haystack), None)
    if hit:
        return {"status": Status.BLOCKED.value, "rights_status": RightsStatus.BLOCKED.value,
                "reason_if_blocked": f"Verbotsliste-Treffer: '{hit}'"}

    if job["input_type"] == "LINK":
        # Explizite channel_id im Link ist ein bewusster Owner-/Test-Override; sonst
        # echte Kanal-ID aus den Video-Metadaten (yt-dlp).
        channel = _extract_channel(job["input_value"])
        if not channel:
            channel = fetch_metadata(job["input_value"]).get("channel_id", "")
        whitelist = _load_whitelist()
        if not channel:
            return {"status": Status.BLOCKED.value, "rights_status": RightsStatus.BLOCKED.value,
                    "reason_if_blocked": "Quelle/Kanal nicht belegbar (fail closed)."}
        if channel not in whitelist:
            return {"status": Status.BLOCKED.value, "rights_status": RightsStatus.BLOCKED.value,
                    "reason_if_blocked": f"Kanal '{channel}' nicht in Whitelist."}
        return {"status": Status.PLANNING.value, "rights_status": RightsStatus.APPROVED.value,
                "source_channel_id": channel, "license_ref": f"WHITELIST:{channel}"}

    # PROMPT: eigene Produktion aus lizenziertem/generiertem Material
    return {"status": Status.PLANNING.value, "rights_status": RightsStatus.APPROVED.value}


# ---------------------------------------------------------------------------
# 2. Content Understanding & Planning
# ---------------------------------------------------------------------------
def planning(job: dict[str, Any]) -> dict[str, Any]:
    llm = get_llm()
    if job["input_type"] == "LINK":
        transcript = job.get("transcript_json") or []
        if not transcript:
            # Kein Transkript mitgegeben -> echte Aufnahme (Download + Whisper).
            work = CONFIG.assets_dir / job["job_id"]
            transcript = get_transcriber().transcribe(job["input_value"], work_dir=work)
        seg = llm.segment_transcript(transcript, job.get("language", "de"))
        analysis = {
            "topic": seg.get("topic", "Clip"),
            "subject": seg.get("topic", "Clip"),
            "content_type": seg.get("content_type", "NEWS"),
            "language": job.get("language", "de"),
            "item_count": max(2, len(seg.get("segments", [])) or 3),
            "tone": "schnell, spannend",
            "audience": "TikTok",
            "_link_segment": seg,
        }
    else:
        analysis = llm.analyze(job["input_value"], job.get("language", "de"))

    outline = [{"scene_id": 1, "role": "HOOK"}]
    outline += [{"scene_id": i + 2, "role": "BODY"} for i in range(analysis["item_count"])]
    outline.append({"scene_id": analysis["item_count"] + 2, "role": "CTA"})

    result = {
        "status": Status.SCRIPTED.value,  # naechster Worker ist Script
        "topic": analysis["topic"],
        "content_type": analysis["content_type"],
        "scenes_json": outline,
        "_analysis": analysis,  # transient, in script verwendet
    }
    if job["input_type"] == "LINK":
        result["transcript_json"] = transcript  # aufgezeichnetes Transkript sichern
    return result


# ---------------------------------------------------------------------------
# 3. Script Engine
# ---------------------------------------------------------------------------
def script(job: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    llm = get_llm()
    scenes = llm.write_script(analysis)
    meta = llm.write_metadata(analysis, scenes)
    return {
        "status": Status.SCRIPTED.value,  # naechster Worker: voiceover
        "script_json": scenes,
        "caption": meta["caption"],
        "hashtags": meta["hashtags"],
        "cover_frame_ref": meta.get("cover_hint", ""),
    }


# ---------------------------------------------------------------------------
# 4. Voiceover Engine (Timing + Audio pro Szene)
# ---------------------------------------------------------------------------
def _scene_duration(text: str, hint: float) -> float:
    words = max(1, len(text.split()))
    est = words / CONFIG.words_per_second
    dur = max(CONFIG.min_scene_s, min(est, CONFIG.max_scene_s), hint)
    return round(dur, 2)


def voiceover(job: dict[str, Any]) -> dict[str, Any]:
    """Erzeugt pro Szene echtes Voiceover; die Szenendauer folgt der Sprechlänge."""
    tts = get_tts()
    scenes = job["script_json"]
    lang = job.get("language", "de")
    assets_dir = CONFIG.assets_dir / job["job_id"]
    assets_dir.mkdir(parents=True, exist_ok=True)

    for s in scenes:
        est = _scene_duration(s.get("voiceover_text", ""), s.get("duration_hint", 3.0))
        audio_path = assets_dir / f"scene_{s['scene_id']:02d}.m4a"
        actual = tts.synthesize(s.get("voiceover_text", ""), audio_path, est, voice=lang)
        s["audio_path"] = str(audio_path)
        s["duration"] = actual

    # Gesamtlänge ins erlaubte Fenster bringen, ohne Sprache zu zerschneiden:
    total = sum(s["duration"] for s in scenes)
    if total > CONFIG.max_duration_s:
        factor = CONFIG.max_duration_s / total
        for s in scenes:
            new = round(s["duration"] * factor, 2)
            sped = Path(s["audio_path"]).with_suffix(".fit.m4a")
            ff.speed_audio(Path(s["audio_path"]), s["duration"] / new, sped)
            s["audio_path"] = str(sped)
            s["duration"] = new
    elif total < CONFIG.min_duration_s and scenes:
        # letzte Szene bis zur Mindestlänge auffüllen (stille Verlängerung)
        extra = round(CONFIG.min_duration_s - total, 2)
        last = scenes[-1]
        new = round(last["duration"] + extra, 2)
        ff.fit_audio(Path(last["audio_path"]), new, Path(last["audio_path"]).with_suffix(".pad.m4a"))
        last["audio_path"] = str(Path(last["audio_path"]).with_suffix(".pad.m4a"))
        last["duration"] = new

    return {
        "status": Status.VOICEOVER_DONE.value,  # naechster: visuals
        "script_json": scenes,
        "voiceover_url": str(assets_dir),
    }


# ---------------------------------------------------------------------------
# 5. Visual Engine
# ---------------------------------------------------------------------------
def visuals(job: dict[str, Any]) -> dict[str, Any]:
    vis = get_visuals()
    scenes = job["script_json"]
    assets_dir = CONFIG.assets_dir / job["job_id"]
    assets_dir.mkdir(parents=True, exist_ok=True)
    seed = job.get("topic", job["job_id"])

    media_assets = []
    for s in scenes:
        img_path = assets_dir / f"scene_{s['scene_id']:02d}.png"
        asset = vis.render_scene(s, seed, img_path)
        s["image_path"] = str(img_path)
        media_assets.append(asset)

    return {
        "status": Status.VISUALS_DONE.value,  # naechster: assembly
        "script_json": scenes,
        "media_assets": media_assets,
    }


# ---------------------------------------------------------------------------
# 6+7. Assembly + Subtitles (Render)
# ---------------------------------------------------------------------------
def assembly(job: dict[str, Any]) -> dict[str, Any]:
    scenes = job["script_json"]
    assets_dir = CONFIG.assets_dir / job["job_id"]
    work = assets_dir / "clips"
    work.mkdir(parents=True, exist_ok=True)

    # pro-Szene-Clips
    clips = []
    t = 0.0
    timed = []
    for s in scenes:
        clip = work / f"clip_{s['scene_id']:02d}.mp4"
        ff.scene_clip(Path(s["image_path"]), Path(s["audio_path"]), s["duration"], clip)
        clips.append(clip)
        timed.append({"subtitle_text": s.get("subtitle_text", ""),
                      "start": round(t, 2), "end": round(t + s["duration"], 2)})
        t += s["duration"]

    # zusammenfuegen
    silent_video = assets_dir / "assembled.mp4"
    ff.concat_clips(clips, silent_video)

    # Untertitel bauen + brennen
    ass_file = assets_dir / "subs.ass"
    subs.build_ass(timed, ass_file)
    subs.build_srt(timed, assets_dir / "subs.srt")

    final = CONFIG.output_dir / f"video_{job['job_id']}.mp4"
    ff.burn_subtitles(silent_video, ass_file, final)

    # Cover-Frame
    cover = CONFIG.output_dir / f"cover_{job['job_id']}.jpg"
    ff.extract_cover(final, cover, at=min(1.0, t / 2))

    return {
        "status": Status.QUALITY_CHECK.value,
        "render_status": "DONE",
        "video_url": str(final),
        "cover_frame_ref": str(cover),
    }


# ---------------------------------------------------------------------------
# 8. Quality Gate (Gate #2)
# ---------------------------------------------------------------------------
def quality_check(job: dict[str, Any]) -> dict[str, Any]:
    scenes = job["script_json"]
    roles = {s.get("role") for s in scenes}
    total = sum(s.get("duration", 0) for s in scenes)

    struktur = 100 if {"HOOK", "BODY", "CTA"} <= roles and len(scenes) >= 3 else 60
    audio = 95 if get_tts().real else 80
    untertitel = 90 if all(s.get("subtitle_text") for s in scenes) else 60
    visual = 90 if all(s.get("image_path") for s in scenes) else 40
    compliance = 100 if job.get("rights_status") == RightsStatus.APPROVED.value else 0
    dur_ok = CONFIG.min_duration_s <= total <= CONFIG.max_duration_s
    verstaendlichkeit = 85 if dur_ok else 55

    breakdown = {
        "struktur": struktur, "audio": audio, "untertitel": untertitel,
        "visual": visual, "compliance": compliance,
        "verstaendlichkeit": verstaendlichkeit, "dauer_s": round(total, 1),
    }
    score = round(
        0.25 * struktur + 0.20 * audio + 0.20 * untertitel +
        0.15 * visual + 0.10 * compliance + 0.10 * verstaendlichkeit
    )
    if compliance == 0:  # hartes Veto
        score = 0

    # Routing
    if score == 0:
        return {"status": Status.BLOCKED.value, "quality_score": 0,
                "quality_breakdown": breakdown,
                "reason_if_blocked": "Compliance-Veto im Quality-Gate."}
    if score >= CONFIG.auto_publish_threshold:
        mode = CONFIG.publish_mode if CONFIG.publish_mode != "dry_run" else "direct_post"
        return {"status": Status.READY_TO_PUBLISH.value, "quality_score": score,
                "quality_breakdown": breakdown, "publish_mode": mode}
    if score >= CONFIG.review_threshold:
        # 60-79 => als Draft veroeffentlichen (menschlicher Review moeglich)
        return {"status": Status.READY_TO_PUBLISH.value, "quality_score": score,
                "quality_breakdown": breakdown, "publish_mode": "draft"}
    return {"status": Status.REVIEW_REQUIRED.value, "quality_score": score,
            "quality_breakdown": breakdown,
            "reason_if_blocked": "Quality-Score unter Review-Schwelle."}


# ---------------------------------------------------------------------------
# 9. Publishing
# ---------------------------------------------------------------------------
def publish(job: dict[str, Any]) -> dict[str, Any]:
    publisher = get_publisher()
    result = publisher.publish(job, Path(job["video_url"]))
    result["status"] = (Status.PUBLISHED.value
                        if result.get("publish_status") == "PUBLISHED"
                        else Status.PUBLISHING.value)
    return result


# ---------------------------------------------------------------------------
# 10. Analytics & Optimization (simuliert deterministisch)
# ---------------------------------------------------------------------------
def analytics(job: dict[str, Any]) -> dict[str, Any]:
    q = job.get("quality_score", 70)
    base = q * 50
    views = int(base + (hash(job["job_id"]) % 500))
    watchtime = int(views * (q / 100) * 12)
    avg = round(watchtime / max(views, 1), 2)
    engagement = round((q / 100) * 0.12, 4)
    return {
        "status": Status.OPTIMIZED.value,
        "views": views, "watchtime": watchtime, "avg_view_duration": avg,
        "saves": int(views * 0.03), "shares": int(views * 0.02),
        "follows": int(views * 0.01), "clicks": int(views * 0.015),
        "engagement_score": engagement,
    }
