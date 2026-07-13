"""Kommandozeile für AutoContentTikTok.

Beispiele:
    python -m autocontent submit --prompt "10 Sommerdüfte"
    python -m autocontent submit --link "https://youtu.be/x?channel_id=UC_OWN_DEMO_CHANNEL" --transcript t.json
    python -m autocontent run <job_id>
    python -m autocontent run-all
    python -m autocontent show <job_id>
    python -m autocontent list
    python -m autocontent doctor
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import CONFIG
from .db import JobStore
from .models import InputType
from . import pipeline
from .providers.transcription import load_transcript_file


def _store() -> JobStore:
    CONFIG.ensure_dirs()
    return JobStore(CONFIG.db_path)


def _seed_whitelist(store: JobStore) -> None:
    path = CONFIG.data_dir / "whitelist.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for c in data.get("channels", []):
            store.add_whitelist(c["channel_id"], c.get("owner", ""),
                                c.get("license_type", "OWN"), c.get("notes", ""))


def cmd_submit(args) -> int:
    store = _store()
    _seed_whitelist(store)
    if args.prompt:
        job = store.create(InputType.PROMPT.value, args.prompt, args.language)
    elif args.link:
        job = store.create(InputType.LINK.value, args.link, args.language)
        if args.transcript:
            store.update(job["job_id"], transcript_json=load_transcript_file(args.transcript))
    else:
        print("Fehler: --prompt oder --link erforderlich", file=sys.stderr)
        return 2
    print(f"Job angelegt: {job['job_id']}")
    if args.run:
        job = pipeline.run_job(store, job["job_id"])
        _print_summary(job)
    return 0


def cmd_run(args) -> int:
    store = _store()
    _seed_whitelist(store)
    job = pipeline.run_job(store, args.job_id)
    _print_summary(job)
    return 0


def cmd_run_all(args) -> int:
    store = _store()
    _seed_whitelist(store)
    results = pipeline.run_all(store)
    print(f"{len(results)} Job(s) verarbeitet.")
    for job in results:
        _print_summary(job)
    return 0


def cmd_show(args) -> int:
    store = _store()
    job = store.get(args.job_id)
    if not job:
        print("Job nicht gefunden", file=sys.stderr)
        return 1
    print(json.dumps(job, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_list(args) -> int:
    store = _store()
    for job in store.list(args.status):
        print(f"{job['job_id']}  {job['status']:<18} {job.get('quality_score','-'):>4}  "
              f"{job['input_type']:<6} {(job.get('topic') or job['input_value'])[:40]}")
    return 0


def cmd_doctor(args) -> int:
    """Prüft die Umgebung (ffmpeg, Provider-Auswahl)."""
    from . import ffmpeg_render as ff
    from .providers.publishing import get_publisher
    from .providers.transcription import _ytdlp_available
    import subprocess
    print("== AutoContentTikTok doctor ==")
    try:
        out = subprocess.run([ff.FFMPEG, "-version"], capture_output=True, text=True)
        print("ffmpeg      :", out.stdout.splitlines()[0])
    except Exception as e:  # noqa: BLE001
        print("ffmpeg      : FEHLT", e)
    print("LLM-Provider :", CONFIG.llm_provider)
    print("TTS-Provider :", CONFIG.tts_provider)
    print("Publisher    :", get_publisher().name, f"(Modus={CONFIG.publish_mode})")
    tok = "ja" if (CONFIG.tiktok_access_token or CONFIG.tiktok_refresh_token) else "nein"
    print("TikTok-Creds :", f"Token/Refresh={tok}, ClientKey={'ja' if CONFIG.tiktok_client_key else 'nein'}")
    print("yt-dlp       :", "verfügbar" if _ytdlp_available() else "fehlt")
    print("Output-Dir   :", CONFIG.output_dir)
    return 0


def cmd_tiktok_auth_url(args) -> int:
    from . import tiktok
    try:
        print(tiktok.authorization_url(scopes=args.scopes))
        print("\nÖffne die URL, autorisiere, kopiere den 'code' aus der Redirect-URL und rufe:")
        print("  python -m autocontent tiktok-exchange <code>")
    except tiktok.TikTokError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_tiktok_exchange(args) -> int:
    from . import tiktok
    try:
        data = tiktok.exchange_code(args.code)
    except tiktok.TikTokError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2))
    print("\nSetze für den Betrieb:")
    print(f"  export TIKTOK_ACCESS_TOKEN={data.get('access_token','')}")
    print(f"  export TIKTOK_REFRESH_TOKEN={data.get('refresh_token','')}")
    print("  export PUBLISH_MODE=direct_post   # oder draft")
    return 0


def _print_summary(job: dict) -> None:
    print("-" * 60)
    print(f"Job     : {job['job_id']}")
    print(f"Status  : {job['status']}")
    print(f"Thema   : {job.get('topic')}  ({job.get('content_type')})")
    print(f"Rechte  : {job.get('rights_status')}  {job.get('reason_if_blocked') or ''}")
    if job.get("quality_score") is not None:
        print(f"Quality : {job.get('quality_score')}  {job.get('quality_breakdown')}")
    if job.get("video_url"):
        print(f"Video   : {job['video_url']}")
    if job.get("publish_status") and job.get("publish_status") != "NONE":
        print(f"Publish : {job.get('publish_status')}  post_id={job.get('tiktok_post_id')}")
    if job.get("views"):
        print(f"Metriken: views={job['views']} avg_view={job.get('avg_view_duration')} "
              f"engagement={job.get('engagement_score')}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autocontent",
                                description="Vollautonomes faceless TikTok-System")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("submit", help="Neuen Job anlegen")
    s.add_argument("--prompt", help="Themenwunsch (PROMPT-Input)")
    s.add_argument("--link", help="YouTube-URL (LINK-Input, mit channel_id=...)")
    s.add_argument("--transcript", help="Pfad zu Transkript-JSON (für LINK)")
    s.add_argument("--language", default="de")
    s.add_argument("--run", action="store_true", help="Job direkt verarbeiten")
    s.set_defaults(func=cmd_submit)

    r = sub.add_parser("run", help="Job verarbeiten")
    r.add_argument("job_id")
    r.set_defaults(func=cmd_run)

    ra = sub.add_parser("run-all", help="Alle offenen Jobs verarbeiten")
    ra.set_defaults(func=cmd_run_all)

    sh = sub.add_parser("show", help="Job-Details anzeigen")
    sh.add_argument("job_id")
    sh.set_defaults(func=cmd_show)

    ls = sub.add_parser("list", help="Jobs auflisten")
    ls.add_argument("--status")
    ls.set_defaults(func=cmd_list)

    d = sub.add_parser("doctor", help="Umgebung prüfen")
    d.set_defaults(func=cmd_doctor)

    au = sub.add_parser("tiktok-auth-url", help="OAuth-Autorisierungs-URL ausgeben")
    au.add_argument("--scopes", default="video.publish,video.upload")
    au.set_defaults(func=cmd_tiktok_auth_url)

    ex = sub.add_parser("tiktok-exchange", help="OAuth-Code gegen Tokens tauschen")
    ex.add_argument("code")
    ex.set_defaults(func=cmd_tiktok_exchange)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
