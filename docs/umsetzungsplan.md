# Umsetzungsplan — Kosten, Stufenmodell, 30-Tage-Plan

---

## 10.1 Kostenblöcke (die wichtigsten Treiber)

| Block | Wovon abhängig | Bemerkung |
|-------|----------------|-----------|
| **LLM-Nutzung** | Tokens je Job (Analyse, Skript, Caption, Segmentierung) | mittlerer Block; skaliert linear mit Videoanzahl |
| **TTS / Voiceover** | Zeichen/Sekunden Audio je Video | pro Video moderat; steigt mit Länge |
| **Video-Rendering** | Renderminuten / Auflösung / Volumen | **oft grösster variabler Block** bei Skalierung |
| **Media / Stock** | Abo oder pro-Asset; AI-Visual pro Generierung | Stock-Abo fix, AI-Generierung variabel |
| **Transkription** | Audiominuten (nur LINK-Input) | nur bei Link-Flow relevant |
| **Automation-Plattform** | Task-/Run-Volumen, Plan-Tier | fixer Sockel + volumenabhängig |
| **Storage / CDN** | gespeicherte Videos/Assets, Traffic | wächst kumulativ; Retention-Policy nötig |
| **TikTok-Publishing** | i. d. R. API-seitig kostenfrei | Aufwand v. a. Rate-Limit-/Compliance-Handling |

**Kostensteuerung:** Kosten je Job loggen (§9.3), Budget-Alerts, Stock-first vor AI-Generierung,
Rendering-Auflösung/Länge deckeln, alte Assets nach Retention löschen.

---

## 10.2 Stufenmodell MVP → Growth → Scale

| Dimension | **MVP** | **Growth** | **Scale** |
|-----------|---------|------------|-----------|
| Kanäle | 1 | 1–2 | mehrere Kanäle/Nischen |
| Frequenz | wenige Videos/Woche | täglich | hohe Frequenz, mehrfach täglich je Kanal |
| Inputs | primär PROMPT | PROMPT + LINK | beides, mehrsprachig |
| Autonomie | Draft-first, manueller Review | Auto-Publish ab Score-Schwelle | voll autonom + Optimization-Loop aktiv |
| Provider | je Rolle einer | Fallback-Adapter je Rolle | Multi-Provider, Kosten-/Latenz-Routing |
| Optimierung | manuell abgelesen | erste Auto-Rückkopplung | kontinuierliche A/B-Tests, gelernte Postzeiten |
| Fokus | Pipeline steht end-to-end | Durchsatz + Qualität stabil | Effizienz, Kosten/Job, Nischen-Skalierung |

---

## 10.3 30-Tage-Plan

### Woche 1 — Architektur, Datenmodell, Basis-Workflows
- Content-Hub/DB anlegen: Tabelle `jobs` + Statusfelder (siehe [datenmodell.md](datenmodell.md)).
- Automation-Plattform aufsetzen; Input-Layer (PROMPT/LINK) → Job-Anlage.
- Konnektoren als Adapter stubben (LLM, TTS, Render, TikTok) mit einheitlichem Interface.
- Rights & Compliance-Gate #1 als hartes Gate implementieren (Whitelist + Verbotsliste).
- Logging/Monitoring-Grundgerüst, Statuslogik durchgängig.

### Woche 2 — Prompt-to-Video-Flow (Ende-zu-Ende)
- Planning + Script Engine mit strukturiertem JSON-Output.
- Voiceover mit Wort-Timecodes; Visual Engine (Stock-first, AI-Fallback).
- Video Assembly über deklaratives Renderer-JSON; Untertitel/Overlay-Engine.
- Publishing (zunächst **Draft-Modus**) + Caption/Hashtags/Cover.
- **Ziel:** ein Prompt erzeugt vollautomatisch ein fertiges Video im TikTok-Postfach.

### Woche 3 — Link-to-Video-Flow + Rechte-Checks
- Transkriptions-Service (Timecodes) anbinden.
- Segmentierung + Priorisierung starker Momente.
- Transformationslogik (eigener Hook, Reframe 9:16, eigene Untertitel) → Eigenständigkeits-Check.
- Rechte-Check für LINK schärfen (Whitelist + Lizenz-Register + Drittpersonen-Regel).
- **Ziel:** aus lizenziertem Link entsteht ein eigenständiges Short, unzulässige Quellen werden `BLOCKED`.

### Woche 4 — Quality-Scoring, Autonomie, erste Optimierung
- Quality Score (§6.3) mit Teilkriterien; Auto-Publish-Schwelle scharfschalten (Direct Post).
- Fehlerbehandlung/Eskalation (Retry/Backoff, Fallback, Review-Queue) vollständig.
- Analytics-Abruf + Aggregation; erste Rückkopplung in Planning (Hooks/Längen/Postzeiten).
- A/B-Test-Grundgerüst (Hook/Caption/Cover).
- **Ziel:** System publiziert autonom ab Score-Schwelle und lernt aus Performance.

---

## Definition of Done je Woche

| Woche | „Fertig", wenn … |
|-------|------------------|
| 1 | ein Job durchläuft alle Status bis vor der Produktion; Gate #1 blockiert korrekt. |
| 2 | Prompt → fertiges Video (Draft) ohne manuellen Eingriff. |
| 3 | lizenzierter Link → eigenständiges Short; fremde Quelle → `BLOCKED`. |
| 4 | Auto-Publish ab Score-Schwelle; Metriken fliessen zurück in Planning. |
