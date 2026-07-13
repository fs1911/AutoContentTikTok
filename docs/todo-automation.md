# To-do-Liste — Automation (abhakbar, pro Modul)

Konkrete Bau-Schritte, direkt aus dem [Technikkonzept](technikkonzept.md) abgeleitet.
Reihenfolge folgt dem 30-Tage-Plan.

## 0. Fundament
- [ ] Content-Hub/DB provisionieren, Tabelle `jobs` + Nebentabellen anlegen ([Schema](datenmodell.md))
- [ ] Automation-Plattform aufsetzen (Trigger, Scheduler, Zustandsverwaltung)
- [ ] Adapter-Interface je Konnektor definieren (LLM, TTS, Stock/AI, Render, Transkription, TikTok)
- [ ] Strukturiertes Logging + Monitoring-Dashboard + Budget-Alerts

## 1. Input-Layer
- [ ] Endpoint/Form/Bot für PROMPT und LINK
- [ ] Format-Validierung (URL gültig? Prompt nicht leer?) + Spracherkennung
- [ ] Job-Anlage mit `status=NEW`

## 2. Rights & Compliance-Gate #1 (hart)
- [ ] Channel-**Whitelist** + Lizenz-Register anbinden
- [ ] **Verbotsliste** (Themen/Begriffe) pflegen und prüfen
- [ ] Drittpersonen-/Datenschutz-Regel implementieren
- [ ] `rights_status` setzen; nur `APPROVED` weiterleiten (fail closed)

## 3. Content Understanding & Planning
- [ ] LLM-Adapter mit erzwungenem JSON-Output
- [ ] `content_type`-Klassifikation → Format-Template-Wahl
- [ ] Outline/`scenes_json` erzeugen (Hook / Kern / CTA)
- [ ] Optimization-Feedback als Kontext einspeisen

## 4. Script Engine
- [ ] Prompt-Templates je Content-Typ (RANKING/EXPLAINER/NEWS/TIPS/STORY)
- [ ] `script_json` mit 3 Textspuren + `visual_prompt` + `duration_hint` je Szene
- [ ] harte Constraints (Zeichen/Szene, Struktur erzwungen)

## 5. Voiceover Engine
- [ ] TTS-Adapter (Multi-Voice/Language, SSML)
- [ ] Wort-Level-Timecodes ausgeben
- [ ] Lautheit auf ≈ −14 LUFS normalisieren

## 6. Visual Engine
- [ ] Stock-Adapter (Suche nach `visual_prompt`)
- [ ] AI-Visual-Adapter als Fallback
- [ ] `license_ref` je Asset zwingend setzen (kein Asset ohne Lizenz)
- [ ] LINK: Quell-Segmente als Visual-Quelle bereitstellen

## 7. Video Assembly Engine
- [ ] Deklaratives Renderer-JSON aus `script_json` + Assets + Timecodes bauen
- [ ] 9:16, 1080×1920, Codec/Bitrate/fps-Spec durchsetzen
- [ ] Musik-Layer + Übergänge; `render_status` führen

## 8. Subtitle & Overlay Engine
- [ ] Karaoke-Untertitel aus Timecodes (Wort-Highlight)
- [ ] On-Screen-Text/Titel/Zwischentitel platzieren
- [ ] Safe-Area + Zeilenlänge + Kontrast durchsetzen
- [ ] (optional) mehrsprachige Untertitel

## 9. Quality Gate #2
- [ ] Teilscores berechnen (struktur/audio/untertitel/visual/compliance/verständlichkeit)
- [ ] `quality_score` gewichten; compliance = hartes Veto
- [ ] Routing: ≥80 Direct Post · 60–79 Draft/Review · <60 Regenerierung→Eskalation

## 10. Publishing Engine
- [ ] Offizielle TikTok Content Posting API anbinden (OAuth, Rate-Limits)
- [ ] Direct-Post- **und** Draft-Modus
- [ ] Caption + Hashtags (breit/nischig/trend) + Cover-Frame
- [ ] Postingfrequenz/Zeitfenster steuern; `tiktok_post_id` speichern

## 11. Link-to-Video-Spezifika
- [ ] Transkriptions-Adapter (Timecodes)
- [ ] Segmentierung + Priorisierung starker Momente
- [ ] Transformation: eigener Hook, Reframe 9:16, eigene Untertitel
- [ ] Eigenständigkeits-Check (kein 1:1-Repost)

## 12. Analytics & Optimization
- [ ] Metrik-Abruf je Post → `metrics_history`
- [ ] `engagement_score` aggregieren
- [ ] Präferenzen (Hooks/Längen/Postzeiten/Themen) zurück an Planning
- [ ] A/B-Test-Auswertung (Hook/Caption/Cover) → Gewinner gewichten

## 13. Fehlerbehandlung & Eskalation (querschnittlich)
- [ ] Retry mit Exponential Backoff (2s/4s/8s/16s) + max. Versuche
- [ ] Fallback-Provider je Adapter
- [ ] Zustände `FAILED_RETRYABLE` / `FAILED_TERMINAL` / `ESCALATED`
- [ ] Menschliche Review-Queue für `REVIEW_REQUIRED`
- [ ] Compliance-Fehler: kein Retry, sofort Block/Eskalation
