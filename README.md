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

## Lauffähiges System (Quickstart)

Das Repo enthält **nicht nur ein Konzept, sondern eine funktionierende Implementierung**.
Sie läuft **vollständig offline** (deterministisches Template-LLM, PIL-Visuals, stiller
Voiceover-Bett, gebündelte ffmpeg-Binary, Dry-Run-Publishing) und schaltet automatisch auf
echte Dienste um, sobald API-Keys gesetzt sind.

```bash
pip install -r requirements.txt

# Umgebung prüfen (ffmpeg, gewählte Provider)
python -m autocontent doctor

# Prompt-to-Video: erzeugt ein echtes 1080x1920-MP4 in ./output/
python -m autocontent submit --prompt "10 Sommerdüfte" --run

# Link-to-Video (nur Whitelist-Kanäle; Transkript als JSON):
python -m autocontent submit \
  --link "https://youtu.be/x?channel_id=UC_OWN_DEMO_CHANNEL" \
  --transcript transcript.json --run

python -m autocontent list          # alle Jobs
python -m autocontent show <job_id> # Job-Details (JSON)
python -m autocontent run-all       # alle offenen Jobs verarbeiten
```

Ergebnis pro Job in `./output/`: `video_<id>.mp4` (9:16, H.264/AAC, gebrannte Untertitel),
`cover_<id>.jpg`, `publish_<id>.json` (Publish-Payload), plus `subs.ass`/`subs.srt` und alle
Szenen-Assets unter `output/assets/<id>/`. Der Job-Zustand liegt in `output/autocontent.db`.

**Was echte Keys aktivieren** (Auswahl automatisch, siehe `.env.example`):
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY` → echtes LLM · `ELEVENLABS_API_KEY`/`OPENAI_API_KEY`
→ echtes Voiceover · `OPENAI_API_KEY` oder `faster-whisper` → echte YouTube-Transkription ·
TikTok-Credentials + `PUBLISH_MODE=direct_post|draft` → echte Veröffentlichung.

### Echtes TikTok-Publishing (OAuth-Flow)

```bash
# 1. App-Daten setzen (TikTok Developer Portal):
export TIKTOK_CLIENT_KEY=... TIKTOK_CLIENT_SECRET=... TIKTOK_REDIRECT_URI=https://app/cb

# 2. Autorisierungs-URL erzeugen, im Browser bestätigen, 'code' aus der Redirect-URL kopieren:
python -m autocontent tiktok-auth-url

# 3. Code gegen Tokens tauschen (gibt ACCESS/REFRESH-Token aus):
python -m autocontent tiktok-exchange <code>

# 4. Tokens + Modus setzen -> ab jetzt postet die Pipeline echt:
export TIKTOK_ACCESS_TOKEN=... TIKTOK_REFRESH_TOKEN=... PUBLISH_MODE=direct_post
```

Der Publisher führt dann den vollständigen Weg aus: `init` (Direct Post bzw. Inbox/Draft) →
**gechunkter Upload** (`Content-Range`) → **Status-Polling**. Access-Tokens werden bei
Bedarf automatisch per Refresh-Token erneuert. Standard bleibt `SELF_ONLY` (privat) —
für öffentliches Posten `TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE` (setzt einen von TikTok
freigegebenen App-Status voraus).

### Echte YouTube-Aufnahme (Link-Input ohne mitgegebenes Transkript)

Wird `--transcript` weggelassen, lädt das System via **yt-dlp** die echten Kanal-Metadaten
(für den Rechte-Check gegen die Whitelist) und die Audiospur und transkribiert sie
(OpenAI Whisper API oder lokal via `faster-whisper`). Ohne Netz/Key degradiert der Schritt
sauber und der Rechte-Check bleibt **fail-closed**.

### Tests

```bash
python -m unittest tests.test_units          # schnelle Logik-Tests
python -m unittest tests.test_e2e            # echter End-to-End-Render (~25s)
```

### Architektur im Code

| Konzept-Modul | Code |
|---------------|------|
| Input-Layer / CLI | `autocontent/cli.py`, `autocontent/db.py` |
| Rights & Compliance (Gate #1) | `autocontent/stages.py:rights_check`, `data/banned_terms.txt`, `data/whitelist.json` |
| Understanding & Planning / Script | `autocontent/llm.py`, `autocontent/stages.py` |
| Voiceover Engine (TTS) | `autocontent/providers/tts.py` |
| Visual Engine | `autocontent/providers/visuals.py` |
| Video Assembly + Subtitles | `autocontent/ffmpeg_render.py`, `autocontent/subtitles.py` |
| Quality Gate (#2) | `autocontent/stages.py:quality_check` |
| Publishing Engine | `autocontent/providers/publishing.py`, `autocontent/tiktok.py` (OAuth + Upload) |
| Link-Ingestion (YouTube) | `autocontent/providers/transcription.py` (yt-dlp + Whisper) |
| Analytics & Optimization | `autocontent/stages.py:analytics` |
| Orchestrierung / Statuslogik | `autocontent/pipeline.py` |

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
