"""LLM-Schicht: Themenanalyse, Skript, Metadaten, Transkript-Segmentierung.

- TemplateLLM: deterministischer, themenoffener Offline-Generator (kein Key nötig).
- RemoteLLM:  echte Anthropic-/OpenAI-Anbindung via stdlib urllib (Key nötig).

Beide erfüllen dasselbe Interface, sodass die Pipeline anbieterunabhängig bleibt.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Optional

from .config import CONFIG

# ---------------------------------------------------------------------------
# Hilfen für Themenanalyse
# ---------------------------------------------------------------------------
_NUMBER_WORDS = {
    "ein": 1, "eine": 1, "eins": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
}
_STOPWORDS = {
    "top", "die", "der", "das", "beste", "besten", "typische", "typischen", "häufigsten",
    "wichtigsten", "gründe", "gründe,", "warum", "fehler", "tipps", "tricks", "fakten",
    "über", "für", "und", "mit", "von", "in", "auf", "zum", "zur",
}


def _detect_number(text: str, default: int) -> int:
    m = re.search(r"\b(\d{1,2})\b", text)
    if m:
        n = int(m.group(1))
        return max(2, min(n, 12))
    for word, val in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text.lower()):
            return max(2, min(val, 12))
    return default


def _detect_content_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("fehler", "tipp", "trick", "vermeide", "solltest")):
        return "TIPS"
    if any(k in t for k in ("grund", "gründe", "warum", "weil", "erklär", "erklärt")):
        return "EXPLAINER"
    if any(k in t for k in ("moment", "news", "heute", "aktuell", "highlight", "wm", "spiel")):
        return "NEWS"
    if any(k in t for k in ("story", "geschichte", "erzähl")):
        return "STORY"
    if any(k in t for k in ("top", "beste", "ranking", "platz")) or re.search(r"\d", t):
        return "RANKING"
    return "EXPLAINER"


def _extract_subject(text: str) -> str:
    """Grober Themenkern ohne führende Zahl/Stopwörter — nur für Templates."""
    words = re.sub(r"[^\wäöüÄÖÜß\s]", " ", text).split()
    kept = [w for w in words if not w.isdigit() and w.lower() not in _STOPWORDS]
    subject = " ".join(kept).strip()
    return subject or text.strip()


def _item_label(content_type: str, idx: int, total: int) -> str:
    if content_type == "RANKING":
        return f"Platz {total - idx + 1}"
    if content_type == "TIPS":
        return f"Punkt {idx}"
    if content_type == "EXPLAINER":
        return f"Grund {idx}"
    if content_type == "NEWS":
        return f"Moment {idx}"
    return f"Teil {idx}"


class BaseLLM:
    name = "base"

    def analyze(self, prompt: str, language: str = "de") -> dict[str, Any]:
        raise NotImplementedError

    def write_script(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def write_metadata(self, analysis: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    def segment_transcript(self, transcript: list[dict[str, Any]], language: str = "de") -> dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Offline-Generator
# ---------------------------------------------------------------------------
class TemplateLLM(BaseLLM):
    name = "template"

    def analyze(self, prompt: str, language: str = "de") -> dict[str, Any]:
        ctype = _detect_content_type(prompt)
        default_n = {"RANKING": 5, "TIPS": 5, "EXPLAINER": 3, "NEWS": 5, "STORY": 4}[ctype]
        n = _detect_number(prompt, default_n)
        subject = _extract_subject(prompt)
        tone = {
            "RANKING": "energetisch, unterhaltsam",
            "TIPS": "hilfreich, direkt",
            "EXPLAINER": "erklärend, klar",
            "NEWS": "schnell, spannend",
            "STORY": "erzählerisch, fesselnd",
        }[ctype]
        return {
            "topic": prompt.strip(),
            "subject": subject,
            "content_type": ctype,
            "language": language,
            "audience": "TikTok, breite Zielgruppe",
            "tone": tone,
            "item_count": n,
        }

    def write_script(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        ctype = analysis["content_type"]
        n = analysis["item_count"]
        subject = analysis["subject"]
        scenes: list[dict[str, Any]] = []

        # Szene 1 — Hook
        hook_vo = {
            "RANKING": f"Das sind die {n} wichtigsten {subject} – Platz 1 überrascht dich.",
            "TIPS": f"{n} Dinge zu {subject}, die die meisten falsch machen.",
            "EXPLAINER": f"{n} Gründe, warum es bei {subject} wirklich schiefgeht.",
            "NEWS": f"Die {n} stärksten Momente rund um {subject}.",
            "STORY": f"Die Geschichte von {subject}, die kaum jemand kennt.",
        }[ctype]
        scenes.append({
            "scene_id": 1, "role": "HOOK", "voiceover_text": hook_vo,
            "on_screen_text": subject.upper()[:40],
            "subtitle_text": hook_vo,
            "visual_prompt": f"vertical cinematic establishing shot about {subject}, bold, high contrast",
            "duration_hint": 2.6,
        })

        # Szenen 2..n+1 — Hauptteil
        for i in range(1, n + 1):
            label = _item_label(ctype, i, n)
            body_vo = {
                "RANKING": f"{label}: ein {subject}, den du kennen solltest.",
                "TIPS": f"{label}: der Fehler bei {subject}, der am meisten kostet.",
                "EXPLAINER": f"{label}: warum {subject} hier oft scheitert.",
                "NEWS": f"{label}: ein Highlight rund um {subject}, das bleibt.",
                "STORY": f"{label}: der Wendepunkt in der Geschichte von {subject}.",
            }[ctype]
            scenes.append({
                "scene_id": i + 1, "role": "BODY", "voiceover_text": body_vo,
                "on_screen_text": label,
                "subtitle_text": body_vo,
                "visual_prompt": f"vertical shot illustrating {subject}, item {i}, clean modern look",
                "duration_hint": 3.4,
            })

        # Letzte Szene — CTA
        cta_vo = "Folge für mehr – und speicher dir das für später."
        scenes.append({
            "scene_id": n + 2, "role": "CTA", "voiceover_text": cta_vo,
            "on_screen_text": "FOLGEN ✅",
            "subtitle_text": cta_vo,
            "visual_prompt": "vertical clean call to action background, bold arrow up",
            "duration_hint": 2.2,
        })
        return scenes

    def write_metadata(self, analysis: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
        subject = analysis["subject"]
        topic = analysis["topic"]
        base_tags = ["#foryou", "#fyp", "#viral", "#lernen"]
        subj_tag = "#" + re.sub(r"[^\wäöüß]", "", subject.lower())[:20]
        caption = f"{topic} – welches Item fehlt? 👇 {subj_tag}"
        return {
            "caption": caption[:150],
            "hashtags": [subj_tag] + base_tags,
            "cover_hint": scenes[0]["on_screen_text"] if scenes else topic,
        }

    def segment_transcript(self, transcript: list[dict[str, Any]], language: str = "de") -> dict[str, Any]:
        """Zerlegt ein Transkript (Segmente mit start/end/text) in ein Short-Segment.

        Offline heuristisch: wählt das Segmentfenster mit den meisten 'Signalwörtern'.
        """
        signals = ("weil", "deshalb", "wichtig", "nie", "immer", "geheimnis", "fehler",
                   "beste", "unglaublich", "achtung", "tipp")
        if not transcript:
            return {"topic": "Clip", "content_type": "EXPLAINER", "start": 0.0, "end": 0.0,
                    "segments": []}

        def score(seg: dict[str, Any]) -> int:
            text = seg.get("text", "").lower()
            return sum(text.count(s) for s in signals) + min(len(text) // 40, 3)

        best_start = max(range(len(transcript)), key=lambda i: score(transcript[i]))
        window = transcript[best_start:best_start + 6]
        start = window[0].get("start", 0.0)
        end = window[-1].get("end", start + 30)
        return {
            "topic": "Highlight-Clip",
            "content_type": "NEWS",
            "language": language,
            "start": start,
            "end": min(end, start + 60),
            "segments": window,
        }


# ---------------------------------------------------------------------------
# Echte Anbindung (Anthropic / OpenAI) über stdlib
# ---------------------------------------------------------------------------
class RemoteLLM(BaseLLM):
    def __init__(self, provider: str):
        self.provider = provider
        self.name = provider
        self._fallback = TemplateLLM()

    def _call(self, system: str, user: str) -> Optional[str]:
        try:
            if self.provider == "anthropic":
                return self._call_anthropic(system, user)
            return self._call_openai(system, user)
        except Exception:
            return None

    def _call_anthropic(self, system: str, user: str) -> str:
        body = json.dumps({
            "model": CONFIG.anthropic_model,
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": CONFIG.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data["content"][0]["text"]

    def _call_openai(self, system: str, user: str) -> str:
        body = json.dumps({
            "model": CONFIG.openai_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions", data=body,
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {CONFIG.openai_api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_json(text: Optional[str]) -> Optional[Any]:
        if not text:
            return None
        m = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

    def analyze(self, prompt: str, language: str = "de") -> dict[str, Any]:
        system = ("Du bist ein TikTok-Content-Stratege. Antworte NUR mit JSON: "
                  '{"topic","subject","content_type"(RANKING|EXPLAINER|NEWS|TIPS|STORY),'
                  '"language","audience","tone","item_count"(int 2-12)}.')
        out = self._extract_json(self._call(system, f"Thema/Prompt: {prompt}\nSprache: {language}"))
        if isinstance(out, dict) and out.get("content_type"):
            out.setdefault("language", language)
            out.setdefault("subject", _extract_subject(prompt))
            out.setdefault("item_count", _detect_number(prompt, 5))
            out.setdefault("topic", prompt.strip())
            return out
        return self._fallback.analyze(prompt, language)

    def write_script(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        system = ("Schreibe ein faceless-TikTok-Skript. Antworte NUR mit JSON-Array von Szenen. "
                  "Jede Szene: {scene_id, role(HOOK|BODY|CTA), voiceover_text, on_screen_text, "
                  "subtitle_text, visual_prompt, duration_hint}. Struktur: Szene1=HOOK, "
                  "dann BODY je Item, letzte=CTA. Deutsch, kurze knackige Sätze.")
        out = self._extract_json(self._call(system, json.dumps(analysis, ensure_ascii=False)))
        if isinstance(out, list) and out:
            return out
        return self._fallback.write_script(analysis)

    def write_metadata(self, analysis: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
        system = ('Erzeuge TikTok-Metadaten. NUR JSON: {"caption","hashtags"(array),"cover_hint"}.')
        payload = {"analysis": analysis, "first_scene": scenes[0] if scenes else {}}
        out = self._extract_json(self._call(system, json.dumps(payload, ensure_ascii=False)))
        if isinstance(out, dict) and out.get("caption"):
            out.setdefault("hashtags", ["#foryou"])
            out.setdefault("cover_hint", analysis.get("topic", ""))
            return out
        return self._fallback.write_metadata(analysis, scenes)

    def segment_transcript(self, transcript: list[dict[str, Any]], language: str = "de") -> dict[str, Any]:
        return self._fallback.segment_transcript(transcript, language)


def get_llm() -> BaseLLM:
    provider = CONFIG.llm_provider
    if provider == "template":
        return TemplateLLM()
    return RemoteLLM(provider)
