# Technikkonzept — AutoContentTikTok

Vollautonomes, themenoffenes faceless TikTok-System. Dieses Dokument beschreibt die
End-to-End-Architektur, die Module, Konnektoren, Input-zu-Output-Logik, das Datenmodell,
die Qualitäts- und Autonomieregeln, Compliance sowie Fehlerbehandlung.

---

## 1. Zielbild & Leitplanken

Das System erzeugt aus **Prompt-Input** (freier Themenwunsch) oder **Link-Input**
(lizenzierter YouTube-Link) automatisch fertige, veröffentlichte faceless TikTok-Videos.

**Betriebsmodus:** Vollautonomie. Menschliche Eingriffe nur als **Ausnahmeprozess** bei:
- ungeklärten Rechten,
- Datenschutzrisiken,
- API-Fehlern nach erschöpftem Retry,
- Qualitätsproblemen unter Schwellwert,
- Plattform-/Policy-Verstössen.

**Nicht-Ziele (harte Grenzen):**
- Kein 1:1-Repost fremder Inhalte.
- Kein Copyright-Bypass.
- Keine Verarbeitung von Inhalten mit erkennbaren Drittpersonen ohne eindeutig zulässige Quelle.

**Designprinzip Themenoffenheit:** Die Pipeline ist themenunabhängig. Was ein Thema
„Sommerdüfte" von „Fussball-WM" unterscheidet, sind ausschliesslich **Daten** — Prompt,
Stil-Preset, Whitelist, Ton/Stimme — nicht der Code. Neue Nische = neuer Datensatz, nicht neue Architektur.

---

## 2. Architektur & Module

### 2.0 Gesamtfluss

```
                 ┌────────────────────────────────────────────────────────────┐
   PROMPT ──►    │  INPUT-LAYER                                                │
   LINK   ──►    │  normalisiert Input → Job-Datensatz (status=NEW)           │
                 └───────────────┬────────────────────────────────────────────┘
                                 ▼
                 ┌────────────────────────────────────────────────────────────┐
                 │  RIGHTS & COMPLIANCE-CHECK   (Gate #1 — hart)              │
                 │  APPROVED | REVIEW_REQUIRED | BLOCKED                       │
                 └───────────────┬────────────────────────────────────────────┘
                                 ▼ (nur APPROVED)
   CONTENT UNDERSTANDING & PLANNING → SCRIPT ENGINE → VOICEOVER ENGINE
        │                                                     │
        ▼                                                     ▼
   VISUAL ENGINE ───────────────► VIDEO ASSEMBLY ENGINE ◄──── SUBTITLE/OVERLAY ENGINE
                                        │
                                        ▼
                 ┌────────────────────────────────────────────────────────────┐
                 │  QUALITY GATE  (Gate #2 — Score-basiert)                   │
                 │  quality_score ≥ Schwelle → auto-publish, sonst REVIEW     │
                 └───────────────┬────────────────────────────────────────────┘
                                 ▼
   PUBLISHING ENGINE (TikTok) ──► ANALYTICS ENGINE ──► OPTIMIZATION ENGINE ↺ (füttert Planning)
```

Alle Module kommunizieren **entkoppelt** über die zentrale Job-Tabelle (Content-Hub) und
eine Workflow-/Automation-Plattform, die den Status vorantreibt. Jedes Modul ist ein
idempotenter Worker: liest Job im Status *X*, produziert Output, setzt Status *Y*.

---

### 2.1 Input-Layer

| | |
|---|---|
| **Zweck** | Eingaben entgegennehmen, normalisieren, Job anlegen. |
| **Inputs** | `PROMPT` (Text) **oder** `LINK` (YouTube-URL + Metadaten). |
| **Outputs** | Neuer Job-Datensatz mit `input_type`, `input_value`, `language`, `status=NEW`. |
| **Optionen** | Webhook/Form/API-Endpoint, Airtable-/Notion-Formular, Telegram-/Slack-Bot, CSV-Batch-Import. |

Der Input-Layer trifft **keine inhaltlichen Entscheidungen**. Er validiert nur Format
(gültige URL? nicht-leerer Prompt?), erkennt die Sprache und legt den Job an.

---

### 2.2 Rights & Compliance-Check (Gate #1)

| | |
|---|---|
| **Zweck** | Rechtsklarheit **vor** jeder Verarbeitung. Harte Blockierung bei Unklarheit. |
| **Inputs** | Job-Datensatz, Channel-Whitelist, Lizenz-Register, Verbots-/Themenliste. |
| **Outputs** | `rights_status` ∈ {APPROVED, REVIEW_REQUIRED, BLOCKED}, `reason_if_blocked`. |

**Regeln PROMPT-Input:**
- Prompt gegen **Verbotsliste** (Themen/Begriffe) prüfen → Treffer = `BLOCKED` oder `REVIEW_REQUIRED`.
- Generierte Visuals stammen aus lizenziertem Stock oder AI-Generierung → grundsätzlich `APPROVED`.

**Regeln LINK-Input:**
- Kanal-ID gegen **Whitelist** (eigene Kanäle + explizit lizenzierte Quellen). Kein Treffer ⇒ `BLOCKED`.
- Lizenz-Flag im Register vorhanden und gültig? Sonst `BLOCKED`.
- Metadaten-Signale (Creative-Commons-Flag, eigener Upload) als Zusatzbeleg, **nie** als alleinige Grundlage.
- Erkennbare Drittpersonen ohne Einwilligung + nicht eindeutig zulässige Quelle ⇒ `BLOCKED`.

**Prinzip:** *Fail closed.* Im Zweifel wird blockiert, nicht durchgewunken. Nur `APPROVED`-Jobs
gehen weiter; `REVIEW_REQUIRED` landet in der menschlichen Warteschlange.

---

### 2.3 Content Understanding & Planning

| | |
|---|---|
| **Zweck** | Thema interpretieren und in eine strukturierte Szenenliste überführen. |
| **Inputs** | Bei PROMPT: Themen-Text. Bei LINK: Transkript mit Timecodes. Plus Optimization-Feedback. |
| **Outputs** | `topic`, Zielgruppe, `content_type` (RANKING\|EXPLAINER\|NEWS\|TIPS\|STORY), Tonalität, Ziel-Länge, `scenes_json` (Outline). |
| **Optionen** | LLM-Service mit strukturiertem JSON-Output (Function/Tool-Calling, JSON-Schema-Zwang). |

Klassifiziert **Content-Typ** und leitet daraus ein **Format-Template** ab (siehe §4).
Das Feedback der Optimization Engine (welche Hooks/Längen performen) fliesst hier als
zusätzlicher Kontext ein — dadurch wird das System über Zeit besser, ohne Code-Änderung.

---

### 2.4 Script Engine

| | |
|---|---|
| **Zweck** | Aus Outline ein sende­fertiges, szenenweises Skript erzeugen. |
| **Inputs** | `scenes_json` (Outline), `content_type`, Tonalität, Sprache. |
| **Outputs** | `script_json`: pro Szene `{ voiceover_text, on_screen_text, subtitle_text, visual_prompt, duration_hint }`. Struktur: **Hook → Hauptteil → CTA**. |
| **Optionen** | LLM-Service, Prompt-Templates pro Content-Typ, harte Constraints (max. Zeichen/Szene). |

Erzwungene Struktur:
- **Szene 1 = Hook** (≤ 3 s, muster­brechend, Neugier/Kontrast/Zahl).
- **Szene 2…n-1 = Hauptteil** (ein Kerngedanke pro Szene).
- **Szene n = CTA** (Follow/Save/Kommentar-Trigger).

Trennung dreier Textspuren pro Szene: **Voiceover** (gesprochen), **On-Screen-Text**
(grosse Kernwörter/Titel), **Subtitle** (Wort-für-Wort-Untertitel). Diese können bewusst
voneinander abweichen.

---

### 2.5 Voiceover Engine

| | |
|---|---|
| **Zweck** | Natürlich klingendes Voiceover erzeugen. |
| **Inputs** | `voiceover_text` je Szene, Stimm-Preset, Sprache, Sprechtempo. |
| **Outputs** | `voiceover_url` (pro Szene oder Gesamtspur) + **Wort-Timecodes** für Untertitel-Sync. |
| **Optionen** | TTS-Service mit Multi-Voice/Multi-Language, SSML für Pausen/Betonung, Timestamp-Output. |

Anforderungen: konsistente Lautheit (Ziel −14 LUFS integrated), Wort-Level-Timestamps
(für Karaoke-Untertitel), konfigurierbares Tempo je Nische (News schneller, Story langsamer).

---

### 2.6 Visual Engine

| | |
|---|---|
| **Zweck** | Passende Visuals je Szene beschaffen oder generieren. |
| **Inputs** | `visual_prompt` je Szene, Stil-Preset, Aspect Ratio 9:16. |
| **Outputs** | `media_assets`: Liste `{ scene_id, asset_url, type, license_ref, source }`. |
| **Optionen** | (a) **Stock-Service** (lizenzierte Clips/Bilder), (b) **AI-Visual-Service** (Text-to-Image/Video), (c) bei LINK: Segmente des Quellvideos. |

Strategie „Stock-first, AI-fallback": zuerst passendes lizenziertes Stock-Material suchen;
kein Treffer ⇒ AI-generieren. Jedes Asset trägt eine **`license_ref`** — ohne gültige
Lizenzreferenz kein Asset im Video (auditierbar).

---

### 2.7 Video Assembly Engine

| | |
|---|---|
| **Zweck** | Alle Assets zu einem vertikalen Video rendern. |
| **Inputs** | `script_json`, `voiceover_url` (+ Timecodes), `media_assets`, Musik, Template. |
| **Outputs** | `video_url` (9:16, MP4, H.264, Ziel-Bitrate), `render_status`. |
| **Optionen** | **Template-basierter Rendering-Service, gesteuert über JSON** (Szenen, Text, Medien, Timing, Übergänge, Musik). |

Der Renderer ist rein deklarativ: ein **JSON beschreibt das komplette Video** (Szene→Medium→
Text-Overlay→Timing→Transition→Audiospur). Dadurch ist Rendering reproduzierbar,
versionierbar und A/B-testbar. Output-Spec: 1080×1920, 9:16, 24–30 fps, Dauer im
erlaubten Fenster (§6).

---

### 2.8 Subtitle & Text Overlay Engine

| | |
|---|---|
| **Zweck** | Automatische Untertitel + Text-Overlays. |
| **Inputs** | `subtitle_text` + Wort-Timecodes (aus Voiceover), On-Screen-Texte, Titel/Zwischentitel. |
| **Outputs** | Untertitel-Spur (in Renderer-JSON eingebettet), Highlight-Keywords. |
| **Optionen** | Karaoke-Style (Wort-Highlight im Takt), mehrsprachig optional, Safe-Area-Beachtung. |

Regeln: max. Zeilenlänge, hoher Kontrast, Safe-Area unten (TikTok-UI verdeckt untere ~15 %),
wichtige Wörter farblich/grösser hervorgehoben.

---

### 2.9 Publishing Engine

| | |
|---|---|
| **Zweck** | TikTok-Metadaten erzeugen und Video veröffentlichen. |
| **Inputs** | `video_url`, `topic`, `content_type`, Performance-Feedback. |
| **Outputs** | Caption, Hashtags, Cover-Frame; `publish_status`, `tiktok_post_id`, `scheduled_time`. |
| **Optionen** | **Offizielle TikTok Content Posting API** — Direct Post **oder** Draft/Inbox-Modell. |

Zwei Modi:
- **Direct Post** — vollautonom, sofort live (Standard bei `quality_score` ≥ Auto-Publish-Schwelle).
- **Draft/Upload** — Video landet im TikTok-Postfach für optionalen manuellen Review (bei `REVIEW_REQUIRED`).

Steuert Postingfrequenz, Zeitfenster (aus Analytics gelernt) und A/B-Tests von Hook/Caption/Cover.

---

### 2.10 Analytics & Optimization Engine

| | |
|---|---|
| **Zweck** | Performance messen und künftige Entscheidungen verbessern. |
| **Inputs** | TikTok-Metriken je Post (Views, Watchtime, Avg View Duration, Saves, Shares, Follows, Klicks). |
| **Outputs** | `engagement_score`, aktualisierte Präferenzen (Hooks, Szenenlängen, Postzeiten, Themen, Formate). |
| **Optionen** | Metrik-Abruf via TikTok-API, Aggregation in DB, Rückspeisung als Kontext in §2.3. |

Optimierungs-Loop: erfolgreiche Muster (Hook-Typ, Länge, Postzeit, Nische) werden gewichtet
und als Kontext an Planning/Script/Publishing zurückgegeben. **Closed loop, ohne Code-Deploy.**

---

## 3. Tools & Konnektoren (Rollen, nicht Zugangsdaten)

| Rolle | Funktion im Fluss | Kernanforderungen |
|-------|-------------------|-------------------|
| **LLM-Service** | Themenanalyse, Skript, Hooks, Captions, Hashtags, Szenenplanung | Strukturierter JSON-Output (Tool-Calling/JSON-Schema), Mehrsprachigkeit, stabile Latenz |
| **Workflow-/Automation-Plattform** | Orchestrierung: Input annehmen, Jobs anstossen, Status führen, Fehler handhaben, Retries | Trigger/Webhooks, Scheduler, Zustandsverwaltung, Retry/Backoff, Branching |
| **Datenbank / Content-Hub** | Jobs, Skripts, Medien-URLs, Status, Metriken zentral verwalten | Tabellen-/DB-System, Query-fähig, Statusfelder, gute Sicht/UI für Review |
| **Transkriptions-Service** | LINK: Audio-Extraktion + Transkript **mit Timecodes** | Wort-/Segment-Level-Timestamps, Sprach­erkennung, robust bei Störgeräuschen |
| **TTS-Service** | Natürliches Voiceover | Multi-Voice/Language, SSML, Timestamp-Output, konsistente Lautheit |
| **Media-/Stock- bzw. AI-Visual-Service** | Lizenzierte Clips/Bilder **oder** generierte Visuals je Szene | API-fähig, Lizenz-Metadaten, 9:16-tauglich, Volumen-tauglich |
| **Video-Rendering-Service** | Template-basiertes Rendern, JSON-gesteuert | Deklaratives JSON-Interface, 9:16-Output, Bitrate/Codec-Kontrolle, Skalierbarkeit |
| **TikTok-Publishing-Schnittstelle** | Upload + Veröffentlichung (Direct Post / Draft) | Offizielle/zertifizierte API, OAuth, Rate-Limit-Handling, Post-ID-Rückgabe |

**Verbindungslogik:** Die Automation-Plattform ist der Dirigent; die DB ist der geteilte
Zustand. Jeder Fachdienst (LLM, TTS, Render, TikTok) wird als **austauschbarer Konnektor**
angebunden (Adapter-Muster) — ein Anbieterwechsel ändert einen Adapter, nicht die Pipeline.

---

## 4. Input-zu-Output-Logik

### 4.1 Prompt-Input — „Theme-to-Video"

1. **Themenanalyse (§2.3):** LLM bestimmt Zielgruppe, Tonalität, `content_type`, Ziel-Länge, Sprache.
2. **Format-Wahl:** aus `content_type` → Template. Beispiele:
   - RANKING (z. B. „10 Sommerdüfte"): Countdown-Struktur, 1 Item/Szene, Hook nennt Zahl.
   - EXPLAINER (z. B. „3 Gründe, warum Teams scheitern"): These → Begründung → Fazit.
   - NEWS/HIGHLIGHTS (z. B. „Top 7 WM-Momente"): Moment-für-Moment, hohe Schnittfrequenz.
   - TIPS (z. B. „5 Fehler auf Baustellen"): Problem → Konsequenz → Lösung.
3. **Szenenliste:** Scene 1 = Hook, Scene 2…n-1 = Inhalte, Scene n = CTA.
4. **Skript (§2.4):** je Szene `voiceover_text`, `on_screen_text`, `subtitle_text`, `visual_prompt`, `duration_hint`.
5. **Produktion:** Voiceover (§2.5) → Visuals (§2.6) → Assembly (§2.7) → Untertitel (§2.8).
6. **Metadaten:** LLM erzeugt Caption (Hook-Satz + Kontext), Hashtags (Mix aus breit/nischig/trend), Titel-Hook, Cover-Frame-Wahl.

### 4.2 Link-Input — „Link-to-Video"

1. **Rechte-Check (§2.2):** Kanal-Whitelist + Lizenz-Flag + Metadaten. Kein klarer Nachweis ⇒ `BLOCKED`.
2. **Transkription:** Audio extrahieren, Transkript **mit Timecodes** erzeugen.
3. **Segmentierung:** LLM zerlegt Transkript in sinnvolle Short-Form-Segmente (in sich geschlossene Gedanken, 15–60 s).
4. **Priorisierung:** starke Segmente (Hooks, Aha-Momente, Highlights, Zahlen/Kontraste) höher gewichten; Top-Segment(e) auswählen.
5. **Transformation zu eigenständigem Short:**
   - neuer, eigener **Text-Hook** (nicht der Original-Satz),
   - eigene Untertitel im Haus-Stil,
   - Reframing auf 9:16, Zwischentitel/Overlays, ggf. neues Voiceover oder Original-Audio (je Lizenz),
   - eigene Caption/Hashtags.
6. **Eigenständigkeit sicherstellen:** Ergebnis ist **transformierte Kurzform** (Auswahl + Neurahmung + Mehrwert), **kein** 1:1-Ausschnitt. Regelbasierter Check: eigener Hook vorhanden, Reframe erfolgt, Overlay/Untertitel hinzugefügt.

---

## 5. Datenmodell & Statuslogik

Zentrale Tabelle `jobs` — vollständige Feld-Definition in **[datenmodell.md](datenmodell.md)**.
Kernfelder:

| Feld | Werte / Typ |
|------|-------------|
| `job_id` | UUID |
| `input_type` | `PROMPT` \| `LINK` |
| `input_value` | Prompt-Text bzw. YouTube-URL |
| `topic`, `language` | abgeleitetes Thema, Sprachcode |
| `rights_status` | `APPROVED` \| `BLOCKED` \| `REVIEW_REQUIRED` |
| `reason_if_blocked` | Text |
| `script_json`, `scenes_json` | strukturierte Inhalte |
| `voiceover_url`, `media_assets` | Audio-URL, Asset-Liste (mit `license_ref`) |
| `render_status`, `video_url` | Rendering-Status, fertiges Video |
| `quality_score` | 0–100 |
| `publish_status`, `scheduled_time`, `tiktok_post_id` | Veröffentlichung |
| `views`, `watchtime`, `avg_view_duration`, `engagement_score`, `last_update` | Metriken |

**Statuslebenszyklus (`status`-Feld):**

```
NEW → RIGHTS_CHECK → (BLOCKED | REVIEW_REQUIRED) 
                   └─► PLANNING → SCRIPTED → VOICEOVER_DONE → VISUALS_DONE
                        → RENDERING → RENDERED → QUALITY_CHECK
                        → (REVIEW_REQUIRED | READY_TO_PUBLISH)
                        → PUBLISHING → PUBLISHED → ANALYTICS → OPTIMIZED
Fehlerzustände quer: FAILED_RETRYABLE, FAILED_TERMINAL, ESCALATED
```

Ein Job wandert von **neu** (`NEW`) durch die Produktionskette **in Arbeit**
(`PLANNING`…`RENDERED`), passiert die Gates, wird **veröffentlicht** (`PUBLISHED`) und läuft
dann in die **Optimierung** (`ANALYTICS` → `OPTIMIZED`), deren Erkenntnisse §2.3 künftiger
Jobs speisen.

---

## 6. Qualitätsregeln & Autonomie

### 6.1 Publikationsfreigabe ohne Mensch — Mindestanforderungen

| Kriterium | Regel |
|-----------|-------|
| **Struktur** | Hook + Kern + CTA vorhanden (alle drei) |
| **Skriptlänge** | im Zielkorridor je Content-Typ (nicht zu dünn/überladen) |
| **Verständlichkeit** | LLM-Lesbarkeits-/Kohärenz-Check ≥ Schwelle |
| **Audio** | Lautheit ≈ −14 LUFS ±1, keine Clipping-Peaks, Voiceover vollständig |
| **Untertitel** | Sync-Abweichung < 150 ms, Zeilenlänge ok, Safe-Area eingehalten |
| **Videodauer** | **min. 8 s, max. 90 s** (Ziel-Fenster je Nische enger, z. B. 20–45 s) |
| **Visuals** | jede Szene hat mind. ein Asset mit gültiger `license_ref` |
| **Compliance** | keine Treffer auf Verbotsliste, `rights_status = APPROVED` |

### 6.2 Verbotslisten (Auto-Block / Eskalation)

- Themen/Begriffe: Gewalt-/Hass-Kategorien, sensible personenbezogene Daten, medizinische/finanzielle Falschversprechen, geschützte Kategorien, plattform-verbotene Inhalte.
- Treffer ⇒ automatisch `BLOCKED` (hart) oder `REVIEW_REQUIRED` (Graubereich), nie stiller Durchlauf.

### 6.3 Quality Score

Gewichtete Summe (0–100) aus Teilkriterien:

```
quality_score =
    0.25 · struktur_score      (Hook/Kern/CTA vollständig & stark)
  + 0.20 · audio_score         (Lautheit, Klarheit, Vollständigkeit)
  + 0.20 · untertitel_score    (Sync, Lesbarkeit, Safe-Area)
  + 0.15 · visual_score        (Relevanz, Auflösung, Lizenz vorhanden)
  + 0.10 · compliance_score    (0 oder 100 — hartes Veto bei 0)
  + 0.10 · verstaendlichkeit_score
```

**Entscheidungslogik:**
- `compliance_score = 0` ⇒ **immer** `BLOCKED`, unabhängig vom Rest (hartes Veto).
- `quality_score ≥ 80` **und** alle harten Kriterien erfüllt ⇒ **Auto Direct Post**.
- `60 ≤ quality_score < 80` ⇒ **Draft** + `REVIEW_REQUIRED` (menschlicher Blick).
- `quality_score < 60` ⇒ **Auto-Regenerierung** des schwächsten Moduls (1 Versuch), dann Eskalation.

Schwellen sind pro Kanal/Nische konfigurierbar (Daten, nicht Code).

---

## 7. Rechte, Datenschutz & Compliance (Governance)

**Grundsatz:** Verarbeitet werden **nur** Inhalte mit nachweisbaren Rechten:
1. **eigene Produktionen**,
2. **explizit lizenzierte** Inhalte (dokumentiertes Lizenz-Flag im Register),
3. **Stock-Material** im Rahmen der Lizenzbedingungen (mit `license_ref`).

**LINK-Input:**
- Keine fremden Creator-Videos ohne Rechte. Nicht auf Whitelist / ohne Lizenz ⇒ `BLOCKED`.
- Kein Ausspielen von Videos mit erkennbaren Drittpersonen ohne Einwilligung, wenn Quelle nicht eindeutig zulässig.

**Datenschutz:**
- Keine sensiblen personenbezogenen Daten / besonderen Kategorien verarbeiten.
- Heikle Themen ⇒ Block- oder Eskalationsregeln (§6.2).

**Positionierung:** Das System ist ein **Repurposing- und Produktionssystem für eigene/
lizenzierte Inhalte** — **kein Copyright-Bypass**. Jede Asset-Nutzung ist über `license_ref`
und das Lizenz-Register **auditierbar**.

---

## 8. Publishing-Strategie

- **Schnittstelle:** offizielle TikTok Content Posting API bzw. zertifiziertes Tool. Keine inoffiziellen/Scraping-Wege.
- **Direct Post vs. Draft:**
  - Direct Post für `quality_score ≥ 80` & `APPROVED` (vollautonom).
  - Draft/Inbox für `REVIEW_REQUIRED` (optionaler manueller Review vor Livegang).
- **Frequenz & Timing:** gesteuerte Postingfrequenz, gelernte Zeitfenster (aus Analytics), Rate-Limits respektiert.
- **A/B-Tests:** systematische Varianten von **Hook**, **Caption** und **Cover/Thumbnail**; Gewinner fliesst in Optimization zurück.

---

## 9. Fehlerbehandlung & Eskalation

### 9.1 Fehlerklassen & Strategie

| Fall | Strategie |
|------|-----------|
| **API-Fehler (transient)** | Retry mit **Exponential Backoff** (z. B. 2s→4s→8s→16s), max. N Versuche, dann Fallback-Provider (Adapter), dann `ESCALATED`. |
| **Rate-Limit** | Backoff + Queue-Verzögerung, kein Hard-Fail. |
| **Fehlende/fehlerhafte Medien** | Asset neu beschaffen (Stock→AI-Fallback); nach Fehlversuch Szene mit Ersatz-Visual füllen oder Job `FAILED_RETRYABLE`. |
| **Fehlerhafter Render** | 1× Re-Render mit bereinigtem JSON; erneut Fehler ⇒ `ESCALATED`. |
| **Qualitäts-Check nicht bestanden** | schwächstes Modul 1× regenerieren; dann `REVIEW_REQUIRED`. |
| **Compliance-Check nicht bestanden** | **kein Retry** — sofort `BLOCKED` bzw. `ESCALATED` (menschlich). |

### 9.2 Entscheidungsmatrix

- **Auto-Abbruch (`FAILED_TERMINAL`)**: Compliance-Veto, dauerhaft unerfüllbare Rechte, wiederholt korrupter Input.
- **Retry sinnvoll (`FAILED_RETRYABLE`)**: transiente API-/Netz-/Render-Fehler, temporär fehlende Medien.
- **Eskalation an Mensch (`ESCALATED` / `REVIEW_REQUIRED`)**: `REVIEW_REQUIRED`-Rechtefälle, Datenschutz-Graubereich, Quality-Score im Mittelband, Retry erschöpft.

### 9.3 Logging & Monitoring

- Strukturiertes Logging pro Job/Schritt (Zeitstempel, Modul, Status, Fehlercode, Provider).
- Metriken: Durchlaufzeit je Modul, Fehlerraten, Retry-Quote, Kosten je Job, Auto-Publish-Quote.
- Alerts bei Fehlerraten-/Kostenspitzen und wachsender Eskalations-Queue.
- Jeder Job vollständig **nachvollziehbar** (Input → Entscheidungen → Assets → Output → Metriken).

---

## Anhang — Themenoffenheit an Beispielen

| Thema | `content_type` | Hook-Muster | Visual-Quelle |
|-------|----------------|-------------|---------------|
| „10 Sommerdüfte" | RANKING | „Platz 10 riecht wie…" | Stock/AI: Flakons, Sommer-Szenen |
| „Top 7 WM-Momente" | NEWS/HIGHLIGHTS | „Diesen Moment vergisst niemand…" | **nur** lizenzierte/whitelisted Clips |
| „Finanzmärkte heute" | EXPLAINER/NEWS | „Warum der Markt gerade kippt…" | Stock/AI: Charts, Skyline |
| „5 Fehler auf Baustellen" | TIPS | „Fehler #1 kostet dich Tausende…" | Stock/AI: Baustellen-B-Roll |
| „3 Gründe, warum Teams scheitern" | EXPLAINER | „Grund 1 sehen die wenigsten…" | AI/abstrakte Motion-Grafik |

Dieselbe Pipeline, unterschiedliche **Daten** — die Architektur bleibt unverändert.
