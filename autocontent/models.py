"""Domänenmodell: Enums und Datenklassen. Spiegelt docs/datenmodell.md wider."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


class InputType(str, Enum):
    PROMPT = "PROMPT"
    LINK = "LINK"


class ContentType(str, Enum):
    RANKING = "RANKING"
    EXPLAINER = "EXPLAINER"
    NEWS = "NEWS"
    TIPS = "TIPS"
    STORY = "STORY"


class RightsStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class Status(str, Enum):
    NEW = "NEW"
    RIGHTS_CHECK = "RIGHTS_CHECK"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    PLANNING = "PLANNING"
    SCRIPTED = "SCRIPTED"
    VOICEOVER_DONE = "VOICEOVER_DONE"
    VISUALS_DONE = "VISUALS_DONE"
    RENDERING = "RENDERING"
    RENDERED = "RENDERED"
    QUALITY_CHECK = "QUALITY_CHECK"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    ANALYTICS = "ANALYTICS"
    OPTIMIZED = "OPTIMIZED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    ESCALATED = "ESCALATED"


class SceneRole(str, Enum):
    HOOK = "HOOK"
    BODY = "BODY"
    CTA = "CTA"


@dataclass
class Scene:
    scene_id: int
    role: str
    voiceover_text: str = ""
    on_screen_text: str = ""
    subtitle_text: str = ""
    visual_prompt: str = ""
    duration_hint: float = 3.0
    # Produktionsergebnisse
    audio_path: str = ""
    image_path: str = ""
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Scene":
        allowed = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in allowed})


def _dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _loads(value: Optional[str]) -> Any:
    if not value:
        return None
    return json.loads(value)
