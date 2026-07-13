# AutoContentTikTok

Vollautonomes, themenoffenes **faceless TikTok-System**: aus einem Prompt (Themenwunsch)
oder einem lizenzierten YouTube-Link entstehen automatisch fertige, veröffentlichte
9:16-Kurzvideos – ohne Filmen, Sprechen oder manuelles Editieren.

> **Prinzip:** Repurposing- und Produktionssystem für **eigene oder klar lizenzierte**
> Inhalte. **Kein** Copyright-Bypass. Unklare Rechte ⇒ harte Blockierung.

## Zwei Input-Wege, ein Output

| Input | Beispiel | Ergebnis |
|-------|----------|----------|
| **PROMPT** | „10 Sommerdüfte", „Top 7 WM-Momente", „5 Fehler auf Baustellen" | Neues faceless Short mit Voiceover, Visuals, Untertiteln |
| **LINK** | YouTube-URL aus Whitelist-Kanal / lizenzierter Quelle | Transformiertes eigenständiges Short aus starken Segmenten |

## Dokumente

Diese Repository-Dokumentation ist so aufgebaut, dass sich daraus direkt drei Artefakte ableiten lassen:

1. **[Technikkonzept](docs/technikkonzept.md)** — Architektur, Module, Datenmodell, Qualitäts- & Compliance-Regeln, Fehlerbehandlung.
2. **[Umsetzungsplan](docs/umsetzungsplan.md)** — Kostenblöcke, MVP→Growth→Scale, 30-Tage-Plan.
3. **[To-do-Liste Automation](docs/todo-automation.md)** — konkrete, abhakbare Bau-Schritte pro Modul.

Ergänzend:
- **[Datenmodell (Schema)](docs/datenmodell.md)** — Feld-für-Feld-Definition der zentralen Job-Tabelle.
- **[Beispiel-Job (JSON)](examples/job_example.json)** — vollständiger Datensatz eines Prompt-Jobs.

## Themenoffenheit

Die Architektur ist **einmal gebaut, für alle Themen nutzbar** (Düfte, Fussball/WM,
Finanzmärkte, Bau, Allgemeinwissen, Storytelling, Rankings). Themenspezifisch sind nur
**Daten** (Prompt, Whitelist, Stil-Preset), **nicht** die Pipeline.

## Pipeline in einem Bild

```
Input → Rights/Compliance → Understanding & Planning → Script → Voiceover
      → Visuals → Video Assembly → Subtitles/Overlays → Quality Gate
      → Publishing (TikTok) → Analytics → Optimization ↺
```
