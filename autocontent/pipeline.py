"""Orchestrator: treibt Jobs zustandsbasiert durch die Pipeline.

Jeder Status wird auf einen Handler abgebildet, der Feld-Updates zurückgibt. Handler
sind idempotent; Fehler führen zu Retry mit Exponential Backoff, danach zur Eskalation.
"""
from __future__ import annotations

import time
import traceback
from typing import Any, Callable

from .config import CONFIG
from .db import JobStore
from .models import Status
from . import stages


def _handle_planning(job: dict[str, Any]) -> dict[str, Any]:
    """PLANNING: Themenanalyse + Skript + Metadaten (eng gekoppelt)."""
    plan = stages.planning(job)
    analysis = plan.pop("_analysis")
    working = {**job, **plan}
    scr = stages.script(working, analysis)
    return {**plan, **scr}


# Status -> Handler (Handler produziert Updates inkl. Folge-Status)
HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    Status.NEW.value: stages.rights_check,
    Status.RIGHTS_CHECK.value: stages.rights_check,
    Status.PLANNING.value: _handle_planning,
    Status.SCRIPTED.value: stages.voiceover,
    Status.VOICEOVER_DONE.value: stages.visuals,
    Status.VISUALS_DONE.value: stages.assembly,
    Status.RENDERING.value: stages.assembly,
    Status.QUALITY_CHECK.value: stages.quality_check,
    Status.READY_TO_PUBLISH.value: stages.publish,
    Status.PUBLISHED.value: stages.analytics,
    Status.ANALYTICS.value: stages.analytics,
}

TERMINAL = {
    Status.BLOCKED.value, Status.FAILED_TERMINAL.value, Status.OPTIMIZED.value,
    Status.REVIEW_REQUIRED.value, Status.ESCALATED.value,
}


def _strip_transient(updates: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in updates.items() if not k.startswith("_")}


def step(store: JobStore, job: dict[str, Any]) -> dict[str, Any]:
    """Führt genau einen Pipeline-Schritt aus (mit Retry/Backoff)."""
    status = job["status"]
    handler = HANDLERS.get(status)
    if handler is None:
        return job

    for attempt in range(CONFIG.max_retries):
        try:
            updates = _strip_transient(handler(job))
            store.log(job["job_id"], status, f"OK -> {updates.get('status')}")
            return store.update(job["job_id"], error_code=None, **updates)
        except Exception as exc:  # noqa: BLE001
            wait = 2 ** (attempt + 1)
            store.log(job["job_id"], status,
                      f"Fehler (Versuch {attempt+1}): {exc}", level="ERROR")
            job = store.update(job["job_id"], retry_count=job.get("retry_count", 0) + 1,
                               error_code=str(exc)[:200], status=Status.FAILED_RETRYABLE.value)
            if attempt < CONFIG.max_retries - 1:
                time.sleep(min(wait, 0.2))  # kurze Backoffs im Betrieb/Test
                job["status"] = status  # erneut versuchen
            else:
                store.log(job["job_id"], status,
                          f"Retries erschöpft -> ESCALATED\n{traceback.format_exc()[-500:]}",
                          level="ERROR")
                return store.update(job["job_id"], status=Status.ESCALATED.value,
                                    reason_if_blocked=f"{status}: {str(exc)[:180]}")
    return store.get(job["job_id"])


def run_job(store: JobStore, job_id: str, max_steps: int = 40) -> dict[str, Any]:
    """Verarbeitet einen Job bis zu einem terminalen Zustand."""
    job = store.get(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} nicht gefunden")
    steps = 0
    while job["status"] not in TERMINAL and steps < max_steps:
        if job["status"] not in HANDLERS:
            break
        new_job = step(store, job)
        if new_job["status"] == job["status"] and new_job["status"] != Status.FAILED_RETRYABLE.value:
            break  # kein Fortschritt -> Abbruch
        job = new_job
        steps += 1
    return job


def run_all(store: JobStore) -> list[dict[str, Any]]:
    """Verarbeitet alle offenen Jobs bis zum jeweiligen Endzustand."""
    results = []
    for job in store.pending():
        results.append(run_job(store, job["job_id"]))
    return results
