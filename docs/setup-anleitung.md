# Setup-Anleitung (Schritt für Schritt)

Diese Anleitung bringt dich von „nichts" zu „fertiges faceless TikTok-Video mit
menschlicher Stimme, automatisch gepostet". Drei Teile:

- **Teil 0** – Projekt lokal lauffähig machen
- **Teil 1** – Menschliche Stimme (OpenAI **oder** ElevenLabs)
- **Teil 2** – TikTok Content Posting API (mit Lösung für „ich finde sie nicht")

> Alle Befehle führst du auf **deinem eigenen Rechner/Server** aus — nicht in der
> Cloud-Sandbox, denn deren Netzwerk blockt OpenAI/ElevenLabs/TikTok.

---

## Teil 0 – Projekt lokal einrichten

Voraussetzung: Python 3.11+ und git.

```bash
# 1. Repo holen (Branch mit dem fertigen System)
git clone <DEIN-REPO-URL> AutoContentTikTok
cd AutoContentTikTok
git checkout claude/faceless-tiktok-automation-l3q95y

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. Umgebung prüfen
python -m autocontent doctor
```

Erwartete Ausgabe von `doctor` (ohne Keys):
```
ffmpeg      : ffmpeg version ...
LLM-Provider : template
TTS-Provider : espeak        <-- noch die robotic-Stimme
Publisher    : dry_run
```

Testlauf (noch ohne Keys, erzeugt ein Video in `./output/`):
```bash
python -m autocontent submit --prompt "10 besten Sommerdüfte" --run
```

---

## Teil 1 – Menschliche Stimme

Du brauchst **einen** der beiden Keys. Empfehlung: **OpenAI** (am günstigsten, in 5 Minuten fertig).

### Variante A: OpenAI TTS (empfohlen zum Start)

1. Öffne **https://platform.openai.com/** und melde dich an (oder registriere dich).
   *Wichtig:* Das ist die **API-Plattform**, nicht ChatGPT. Die API hat eine eigene Abrechnung.
2. Falls verlangt: Telefonnummer verifizieren.
3. Guthaben aufladen: oben rechts **Zahnrad (Settings)** → **Billing** →
   **Add payment method** → Karte hinterlegen → **Add to credit balance** (z. B. 5 $).
   Direktlink: https://platform.openai.com/settings/organization/billing/overview
4. Key erstellen: Menü links **API keys** (oder https://platform.openai.com/api-keys) →
   **+ Create new secret key** → Namen vergeben → **Create**.
5. Den Key **sofort kopieren** (`sk-...`) — er wird nur **einmal** angezeigt.
6. Auf deinem Rechner setzen und Video bauen:
   ```bash
   export OPENAI_API_KEY=sk-DEIN_KEY
   export OPENAI_TTS_VOICE=onyx     # Auswahl: alloy echo fable onyx nova shimmer
   python -m autocontent doctor     # TTS-Provider muss jetzt "openai" zeigen
   python -m autocontent submit --prompt "10 besten Sommerdüfte" --run
   ```
   Stimmen zum Anhören/Vergleichen: https://platform.openai.com/docs/guides/text-to-speech

Kosten: grob **unter 1 Cent pro Video** (Preise: https://openai.com/api/pricing).

### Variante B: ElevenLabs (natürlichste Stimme, bestes Deutsch)

1. Öffne **https://elevenlabs.io/** → **Sign up**.
2. Für **kommerzielle** Nutzung (TikTok-Posting) brauchst du einen bezahlten Plan:
   **https://elevenlabs.io/pricing** (Starter ~5 $/Mt., Creator ~22 $/Mt.).
   Der Free-Plan ist nur nicht-kommerziell + mit Namensnennung.
3. Stimme wählen: **https://elevenlabs.io/app/voice-library** → eine deutsche/mehrsprachige
   Stimme öffnen → **Voice-ID kopieren** (Button „ID" / „Copy Voice ID").
4. API-Key: rechts oben **Profil** → **API Keys**
   (https://elevenlabs.io/app/settings/api-keys) → **Create API Key** → kopieren.
5. Setzen und bauen:
   ```bash
   export ELEVENLABS_API_KEY=DEIN_KEY
   export ELEVENLABS_VOICE_ID=DIE_KOPIERTE_VOICE_ID
   python -m autocontent doctor     # TTS-Provider = "elevenlabs"
   python -m autocontent submit --prompt "10 besten Sommerdüfte" --run
   ```

> Sobald ein Key gesetzt ist, ersetzt die menschliche Stimme espeak **automatisch**.
> ElevenLabs hat Vorrang vor OpenAI, OpenAI vor espeak.

---

## Teil 2 – TikTok Content Posting API

**Wichtigster Punkt:** „Content Posting API" ist **kein eigener Menüpunkt**. Sie ist ein
**Produkt, das du INNERHALB einer selbst erstellten App hinzufügst** (Button „Add products").
Deshalb findet man sie ohne App nicht. Genau hier hakt es meistens.

### Schritt 2.1 – Als Entwickler registrieren
1. Öffne **https://developers.tiktok.com/** → oben rechts **Log in** → mit deinem
   **TikTok-Konto** anmelden.
2. Beim ersten Mal: Entwickler-Bedingungen akzeptieren, **E-Mail verifizieren**
   (Bestätigungsmail anklicken). Ohne verifizierte E-Mail kannst du keine App anlegen.

### Schritt 2.2 – App erstellen
1. Oben rechts auf deinen Namen → **Manage apps** (Direktlink: https://developers.tiktok.com/apps).
2. Button **Connect an app** / **Create an app**.
3. App-Infos ausfüllen:
   - **App name** (z. B. „AutoContentTikTok")
   - **Category / Description**
   - **Website URL** (irgendeine gültige URL, z. B. deine Domain oder GitHub-Repo-URL)
4. Speichern. Du landest auf der **App-Detailseite**.

### Schritt 2.3 – Produkte hinzufügen (HIER ist die Content Posting API)
1. Auf der App-Detailseite den Abschnitt **„Add products"** suchen (Mitte/oben der Seite).
2. **„Login Kit"** hinzufügen (für die Autorisierung nötig).
3. **„Content Posting API"** hinzufügen. ← **das ist die gesuchte Funktion**
4. Innerhalb der Content Posting API: **„Direct Post"** aktivieren (Schalter/Checkbox).

> **Findest du „Content Posting API" trotzdem nicht in der Produktliste?** Häufige Gründe:
> - Du bist noch **auf der Konto-Übersicht**, nicht in einer **konkreten App** → erst App öffnen.
> - **App-Infos unvollständig** (z. B. Website-URL fehlt) → ausfüllen, Seite neu laden.
> - Das Produkt erscheint **ausgegraut mit „Apply"** → auf Apply klicken und die kurze
>   Freischaltung abwarten.
> - **Region/Konto** erfordert ein Business-/Organisationskonto → im Profil ggf.
>   „Convert to organization" bzw. Verifizierung abschließen.

### Schritt 2.4 – Scopes & Redirect-URI
1. Bei **Login Kit**: **Redirect URI** eintragen. Fürs lokale Testen genügt z. B.
   `https://localhost/callback` (muss exakt mit dem übereinstimmen, was du später setzt).
2. **Scopes** anhaken/anfordern:
   - `video.upload` (Upload in den Entwurf/Inbox)
   - `video.publish` (Direct Post – öffentliches Posten)
3. Ggf. **Domain/URL verifizieren** (TikTok verlangt manchmal eine Bestätigung der
   Redirect-Domain per Datei- oder DNS-Eintrag – der Assistent auf der Seite führt dich durch).

### Schritt 2.5 – Zugangsdaten kopieren
Im Abschnitt **Basic information / Credentials** deiner App findest du:
- **Client key**
- **Client secret**

### Schritt 2.6 – Autorisieren & posten (auf deinem Rechner)
```bash
export TIKTOK_CLIENT_KEY=DEIN_CLIENT_KEY
export TIKTOK_CLIENT_SECRET=DEIN_CLIENT_SECRET
export TIKTOK_REDIRECT_URI=https://localhost/callback   # EXAKT wie in der App

# 1. Autorisierungs-URL erzeugen
python -m autocontent tiktok-auth-url
#    -> URL im Browser öffnen, mit deinem TikTok-Konto bestätigen.
#    -> Du wirst auf deine Redirect-URI umgeleitet: ...?code=XXXX&state=...
#    -> den Wert von 'code' kopieren.

# 2. Code gegen Tokens tauschen
python -m autocontent tiktok-exchange XXXX
#    -> gibt access_token und refresh_token aus.

# 3. Tokens setzen und ab jetzt ECHT posten
export TIKTOK_ACCESS_TOKEN=DEIN_ACCESS_TOKEN
export TIKTOK_REFRESH_TOKEN=DEIN_REFRESH_TOKEN
export PUBLISH_MODE=direct_post        # oder: draft (Upload in die TikTok-Inbox)
python -m autocontent submit --prompt "10 besten Sommerdüfte" --run
```

### Wichtig: Audit-Status
- Solange deine App **nicht von TikTok geprüft** ist (Unaudited/Sandbox), lassen sich
  Direct Posts nur als **`SELF_ONLY` (privat)** an dein eigenes autorisiertes Konto senden.
  Das reicht, um die **komplette Pipeline echt zu testen**.
- Für **öffentliches** Posten reichst du die App bei TikTok zur Prüfung ein und setzt danach:
  ```bash
  export TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE
  ```

---

## Wichtige Links (Kurzliste)

| Zweck | Link |
|-------|------|
| OpenAI API-Key | https://platform.openai.com/api-keys |
| OpenAI Billing | https://platform.openai.com/settings/organization/billing/overview |
| OpenAI Preise | https://openai.com/api/pricing |
| ElevenLabs Sign-up | https://elevenlabs.io/ |
| ElevenLabs API-Keys | https://elevenlabs.io/app/settings/api-keys |
| ElevenLabs Voice Library | https://elevenlabs.io/app/voice-library |
| TikTok Developers | https://developers.tiktok.com/ |
| TikTok „Manage apps" | https://developers.tiktok.com/apps |
| Content Posting API – Doku | https://developers.tiktok.com/doc/content-posting-api-get-started/ |

---

## Fehlerbehebung

| Symptom | Ursache / Lösung |
|---------|------------------|
| `doctor` zeigt weiter `espeak` | Key nicht im selben Terminal gesetzt (`export ...`) oder Tippfehler. |
| „Content Posting API" nicht sichtbar | Erst eine App anlegen und öffnen; App-Infos vollständig; ggf. „Apply". |
| Nach `tiktok-exchange` ein Fehler | `TIKTOK_REDIRECT_URI` muss **exakt** der in der App eingetragenen entsprechen. |
| Direct Post schlägt fehl / nur privat | App noch nicht auditiert → `TIKTOK_PRIVACY_LEVEL=SELF_ONLY` zum Testen. |
| OpenAI „insufficient_quota" | In der API-Plattform Guthaben aufladen (getrennt von ChatGPT Plus). |
