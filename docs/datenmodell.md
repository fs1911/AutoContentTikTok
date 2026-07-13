# Datenmodell — zentrale Job-Tabelle

Einfach, aber robust. Eine zentrale Tabelle `jobs` ist die Single Source of Truth; jedes
Modul liest/schreibt ausschliesslich hier. Optionale Nebentabellen für Assets und Metriken
sind unten skizziert.

## Tabelle `jobs`

| Feld | Typ | Werte / Beschreibung |
|------|-----|----------------------|
| `job_id` | UUID (PK) | Eindeutige Job-ID |
| `created_at` | timestamp | Anlagezeitpunkt |
| `input_type` | enum | `PROMPT` \| `LINK` |
| `input_value` | text | Prompt-Text oder YouTube-URL |
| `topic` | text | abgeleitetes Thema |
| `language` | text | Sprachcode (z. B. `de`, `en`) |
| `content_type` | enum | `RANKING` \| `EXPLAINER` \| `NEWS` \| `TIPS` \| `STORY` |
| `status` | enum | Lebenszyklus (siehe unten) |
| `rights_status` | enum | `APPROVED` \| `BLOCKED` \| `REVIEW_REQUIRED` |
| `reason_if_blocked` | text | Begründung bei Block/Review |
| `source_channel_id` | text | bei LINK: Kanal-ID (Whitelist-Abgleich) |
| `license_ref` | text | Lizenznachweis-Referenz (LINK / Stock) |
| `transcript_json` | json | bei LINK: Transkript mit Timecodes |
| `scenes_json` | json | Outline / Szenenliste |
| `script_json` | json | szenenweises Skript (Voiceover/On-Screen/Subtitle/Visual-Prompt) |
| `voiceover_url` | text | Audio-URL (gesamt oder je Szene) |
| `voiceover_timecodes` | json | Wort-Level-Timestamps |
| `media_assets` | json | Liste `{scene_id, asset_url, type, license_ref, source}` |
| `render_json` | json | deklaratives Renderer-JSON (komplettes Video) |
| `render_status` | enum | `PENDING` \| `RENDERING` \| `DONE` \| `FAILED` |
| `video_url` | text | fertiges 9:16-MP4 |
| `quality_score` | int | 0–100 |
| `quality_breakdown` | json | Teilscores (struktur/audio/untertitel/visual/compliance/verständlichkeit) |
| `publish_status` | enum | `NONE` \| `DRAFT` \| `SCHEDULED` \| `PUBLISHED` \| `FAILED` |
| `publish_mode` | enum | `DIRECT_POST` \| `DRAFT` |
| `scheduled_time` | timestamp | geplanter Postzeitpunkt |
| `tiktok_post_id` | text | ID nach Veröffentlichung |
| `caption` | text | TikTok-Caption |
| `hashtags` | json | Liste Hashtags |
| `cover_frame_ref` | text | gewählter Cover-Frame |
| `views` | int | Metrik |
| `watchtime` | int | Sekunden gesamt |
| `avg_view_duration` | float | Ø Sehdauer |
| `saves` / `shares` / `follows` / `clicks` | int | Engagement-Metriken |
| `engagement_score` | float | aggregierter Score |
| `error_code` | text | letzter Fehler |
| `retry_count` | int | Anzahl Retries |
| `last_update` | timestamp | letzte Änderung |

## `status`-Lebenszyklus

```
NEW
 └─ RIGHTS_CHECK
     ├─ BLOCKED            (terminal)
     ├─ REVIEW_REQUIRED    (menschliche Queue)
     └─ PLANNING
         └─ SCRIPTED
             └─ VOICEOVER_DONE
                 └─ VISUALS_DONE
                     └─ RENDERING → RENDERED
                         └─ QUALITY_CHECK
                             ├─ REVIEW_REQUIRED   (Score 60–79)
                             └─ READY_TO_PUBLISH  (Score ≥ 80)
                                 └─ PUBLISHING → PUBLISHED
                                     └─ ANALYTICS → OPTIMIZED
Querzustände: FAILED_RETRYABLE · FAILED_TERMINAL · ESCALATED
```

## Nebentabellen (optional)

**`assets`** — Entkopplung grosser Asset-Listen:
`asset_id, job_id, scene_id, type (image|clip|audio|music), url, license_ref, source, created_at`

**`metrics_history`** — Zeitreihe statt nur Snapshot:
`metric_id, job_id, captured_at, views, watchtime, avg_view_duration, saves, shares, follows, clicks`

**`whitelist`** — zulässige Quellen für LINK-Input:
`channel_id, owner, license_type, valid_from, valid_to, notes`

## Idempotenz-Regel

Jedes Modul ist ein Worker mit Vertrag: *„lies Job im Status X → produziere Output →
setze Status Y".* Bei Wiederholung desselben Schritts wird derselbe Output erzeugt oder
ein bereits vorhandener übersprungen — so sind Retries gefahrlos.
