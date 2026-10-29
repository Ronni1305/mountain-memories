# Mountain Memories – Mein persönliches Tourenbuch

Eine Web-App zum Festhalten von Wanderungen, Klettertouren und Bergbesteigungen – mit
topografischer Karte, automatischer Gipfelerkennung, Fotos, Statistik und Datensicherung.
Gebaut mit Python und Streamlit, gedacht vor allem fürs Smartphone.

![App-Symbol](assets/icon-192.png)

## Inhalt

1. [Überblick: Wie die App aufgebaut ist](#1-überblick)
2. [Lokal ausprobieren (ohne Konto, ohne Internet-Datenbank)](#2-lokal-ausprobieren)
3. [Supabase einrichten (Datenbank und Fotoablage)](#3-supabase-einrichten)
4. [Persönlichen Login anlegen](#4-persönlichen-login-anlegen)
5. [Auf GitHub veröffentlichen](#5-auf-github-veröffentlichen)
6. [Auf Streamlit Community Cloud bereitstellen](#6-streamlit-community-cloud)
7. [Aufs Handy: zum Startbildschirm hinzufügen](#7-aufs-handy)
8. [Datensicherung und Wiederherstellung](#8-datensicherung-und-wiederherstellung)
9. [Secrets und externe Dienste](#9-secrets-und-externe-dienste)
10. [Getestet – und was (noch) nicht geht](#10-getestet-und-einschränkungen)
11. [Projektstruktur](#11-projektstruktur)

---

## 1. Überblick

| Bereich | Was er kann |
|---|---|
| **Karte** | Alle Touren als Symbole (🥾 Wandern grün/rund, 🧗 Klettern orange/eckig, 🏔️ Bergsteigen blau). Antippen zeigt die Tour mit Fotos. Filter nach Art, Zeitraum, Region. |
| **Neue Tour** | Karte unter das feste rote Fadenkreuz schieben → „Position übernehmen“. Gipfelname, Region und Höhe werden vorgeschlagen und sind frei änderbar. |
| **Meine Touren** | Chronologische Liste mit Titelbild, Suche (Gipfel, Ort, Name, Bergpartner) und Sortierung. |
| **Statistik** | Anzahl je Art, Touren pro Jahr, Höhenmeter, häufigste Gipfel, Regionen, Bergpartner. |
| **Einstellungen** | Export (CSV, JSON), vollständige ZIP-Sicherung mit Fotos, Wiederherstellung, Abmelden. |

**Zwei Betriebsarten – gleiche Oberfläche:**

- **Lokaler Testmodus** (ohne Secrets): Touren in einer SQLite-Datei, Fotos im Ordner `daten/`.
  Nur zum Ausprobieren auf dem eigenen Computer. Kein Login.
- **Cloud-Modus** (mit Supabase-Secrets): Touren in PostgreSQL, Fotos in einem privaten
  Speicher. Login mit E-Mail und Passwort. Die Datenbank selbst (Row Level Security) sorgt dafür,
  dass nur die angemeldete Person ihre Touren und Fotos sieht. Fotos werden nur über Links
  angezeigt, die nach einer Stunde ablaufen.

Auf Streamlit Community Cloud ist der lokale Modus gesperrt – dort würden Daten bei einem
Neustart verloren gehen.

Mit einer ZIP-Sicherung lassen sich Testdaten später vom lokalen Modus in die Cloud übertragen.

---

## 2. Lokal ausprobieren

Voraussetzung: Python 3.12 oder neuer ([python.org](https://www.python.org/downloads/)).

**Windows – am einfachsten:** Doppelklick auf `start_lokal.bat`. Beim ersten Start wird alles
eingerichtet (dauert ein paar Minuten), danach öffnet sich die App im Browser unter
<http://localhost:8501>.

**Von Hand (Windows, macOS, Linux):**

```bash
cd Claude-Wandern
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Oben in der App steht dann „Lokaler Testmodus“. Alle Daten liegen in `daten/` (ist in
`.gitignore` eingetragen und wird nie veröffentlicht).

**Am Handy im selben WLAN testen:** Streamlit zeigt beim Start eine „Network URL“
(z. B. `http://192.168.1.20:8501`). Diese am Handy öffnen. Hinweis: „Meinen Standort zeigen“ auf
der Karte funktioniert am Handy erst mit HTTPS, also nach der Veröffentlichung.

**Tests ausführen:** `pip install pytest` und dann `python -m pytest`.

---

## 3. Supabase einrichten

Supabase hat einen kostenlosen Tarif für kleine Projekte (zuletzt bekannt: 500 MB Datenbank,
1 GB Dateien – bitte auf <https://supabase.com/pricing> prüfen). 1 GB reicht für etwa
2.000–3.000 Fotos, weil die App jedes Foto auf höchstens 2.400 Pixel verkleinert. Hinweis:
Kostenlose Projekte werden nach längerer Zeit ohne Nutzung pausiert und lassen sich im
Dashboard mit einem Klick wieder starten – die Daten bleiben erhalten.

1. Auf <https://supabase.com> ein Konto anlegen → **New project**.
   Name z. B. `mountain-memories`, Region **Central EU (Frankfurt)**, ein sicheres
   Datenbank-Passwort vergeben (wird für die App nicht gebraucht, aber gut aufheben).
2. Links **SQL Editor** → **New query** → den gesamten Inhalt von
   [`supabase/schema.sql`](supabase/schema.sql) einfügen → **Run**.
   Das legt die Tabellen, die Zugriffsregeln (Row Level Security) und den privaten
   Foto-Speicher `fotos` an. Das Skript darf mehrmals ausgeführt werden.
3. **Kontrolle:** Links **Table Editor** → `tours` und `photos` zeigen „RLS enabled“.
   Unter **Storage** gibt es den Bucket `fotos` ohne das Kennzeichen „Public“.
4. **Project Settings → API** (bzw. **API Keys**): Notieren
   - **Project URL** (z. B. `https://abcdefgh.supabase.co`)
   - **anon / publishable key** (langer Text)

   ⚠️ Den **service_role / secret key** niemals in die App eintragen – er umgeht alle Zugriffsregeln.

**Lokal mit Supabase testen:** `.streamlit/secrets.toml.example` nach
`.streamlit/secrets.toml` kopieren, URL und Schlüssel eintragen, App neu starten.
Die Datei `secrets.toml` ist in `.gitignore` eingetragen.

---

## 4. Persönlichen Login anlegen

Die App hat bewusst **keine** Registrierung. Das Konto wird einmalig im Supabase-Dashboard angelegt:

1. **Authentication → Sign In / Providers → Email**: „Enable Email provider“ an lassen.
2. **Authentication → Sign In / Providers**: **„Allow new users to sign up“ ausschalten** und
   speichern. Damit kann sich niemand sonst ein Konto anlegen.
3. **Authentication → Users → Add user → Create new user**: E-Mail-Adresse und ein gutes
   Passwort (mind. 12 Zeichen) eintragen, **„Auto Confirm User“ anhaken** → **Create user**.
4. In der App mit dieser E-Mail und dem Passwort anmelden.

**Passwort vergessen?** Im Dashboard unter **Authentication → Users** beim Konto über das
Menü „…“ ein neues Passwort setzen (oder „Send password recovery“).

**Gut zu wissen:** Nach dem Neuladen der Seite oder nach längerer Pause muss man sich erneut
anmelden – die Anmeldung gilt für die geöffnete Browsersitzung.

---

## 5. Auf GitHub veröffentlichen

Der Code darf öffentlich sein – er enthält keine Zugangsdaten und keine Touren.

1. Auf <https://github.com> → **New repository** → Name `mountain-memories`,
   **Public** (für die kostenlose Streamlit Cloud nötig) → **Create repository**
   (ohne README, die gibt es schon).
2. Im Ordner `Claude-Wandern` (Eingabeaufforderung oder Git Bash):

   ```bash
   git init
   git add .
   git status            # Kontrolle: KEIN daten/, KEINE secrets.toml in der Liste!
   git commit -m "Mountain Memories: erste Version"
   git branch -M main
   git remote add origin https://github.com/DEIN-NAME/mountain-memories.git
   git push -u origin main
   ```

Vor jedem `git push` kurz `git status` prüfen: Es dürfen weder `daten/` noch
`.streamlit/secrets.toml` noch Sicherungsdateien auftauchen.

---

## 6. Streamlit Community Cloud

1. Auf <https://share.streamlit.io> mit dem GitHub-Konto anmelden → **Create app** →
   **Deploy a public app from GitHub**.
2. Repository `mountain-memories`, Branch `main`, Main file `streamlit_app.py`.
   Unter **App URL** einen Namen wählen, z. B. `mein-tourenbuch` → `https://mein-tourenbuch.streamlit.app`.
3. **Advanced settings**: Python-Version **3.13** wählen. Bei **Secrets** einfügen
   (mit den Werten aus Schritt 3):

   ```toml
   [supabase]
   url = "https://abcdefgh.supabase.co"
   anon_key = "eyJhbGciOi..."
   ```
4. **Deploy**. Der erste Start dauert einige Minuten.
5. Optional: Falls Streamlit es für die App anbietet, unter **Settings → Sharing**
   „Only specific people can view this app“ wählen und die eigene E-Mail eintragen – ein
   zusätzlicher Schutz vor der Anmeldung in der App. Nötig ist das nicht: Ohne Login sieht
   niemand Touren oder Fotos.

Änderungen am Code: einfach auf GitHub hochladen (`git push`) – die App aktualisiert sich selbst.
Die Touren bleiben dabei erhalten, weil sie in Supabase liegen.

---

## 7. Aufs Handy

- **iPhone (Safari):** App-Adresse öffnen → Teilen-Symbol (Quadrat mit Pfeil) →
  **„Zum Home-Bildschirm“** → **Hinzufügen**.
- **Android (Chrome):** App-Adresse öffnen → Menü **⋮** → **„Zum Startbildschirm hinzufügen“**
  bzw. **„App installieren“**.

Die App bringt ein eigenes Symbol, ein Web-App-Manifest und ein Apple-Touch-Icon mit
(`static/`). **Ehrlicher Hinweis:** Streamlit Community Cloud zeigt jede App innerhalb eines
eigenen Rahmens an. Deshalb kann es sein, dass das Handy beim Hinzufügen das allgemeine
Streamlit-Symbol statt des Berg-Symbols verwendet. Die App funktioniert trotzdem ganz normal.
Einen Offline-Modus gibt es nicht – Karte, Gipfelsuche und Speicherung brauchen Internet.

---

## 8. Datensicherung und Wiederherstellung

Unter **Einstellungen**:

- **Touren als CSV** – Tabelle für Excel (Semikolon, Umlaute korrekt).
- **Touren als JSON** – alle Daten maschinenlesbar, ohne Fotos.
- **Sicherung erstellen** → **Sicherung herunterladen** – eine ZIP-Datei mit
  `sicherung.json` (Touren, Koordinaten, Zuordnung der Fotos), `touren.csv` und dem Ordner
  `fotos/` (ein Unterordner pro Tour, z. B. `2026-07-14_Wildspitze_1a2b3c4d/`).

**Wiederherstellen:** **Einstellungen → Sicherung einspielen** → ZIP-Datei wählen →
**Jetzt einspielen**. Touren, die schon vorhanden sind, werden übersprungen; man kann eine
Sicherung also gefahrlos mehrmals einspielen. Genauso überträgt man Testdaten: lokal sichern,
in der Cloud-App einspielen.

Empfehlung: Alle paar Monate eine ZIP-Sicherung erstellen und auf dem Computer oder in einer
Cloud ablegen.

**Löschstrategie:** Wird eine Tour gelöscht, werden zuerst ihre Fotodateien und dann die Tour
mit allen Foto-Einträgen entfernt. Klappt das Löschen der Dateien nicht, bleibt die Tour
unverändert – so entstehen keine verwaisten Bilder.

---

## 9. Secrets und externe Dienste

**Secrets** (nur im Cloud-Modus nötig):

| Schlüssel | Woher | Hinweis |
|---|---|---|
| `supabase.url` | Supabase → Project Settings → API | Project URL |
| `supabase.anon_key` | Supabase → Project Settings → API | anon / publishable key, **nicht** service_role |

**Externe Dienste** (alle ohne eigenes Konto, ohne Schlüssel):

| Dienst | Wofür | Bedingungen |
|---|---|---|
| [OpenTopoMap](https://opentopomap.org) | Topografische Karte | Frei mit Namensnennung (CC-BY-SA), keine Massenabrufe |
| [OpenStreetMap](https://www.openstreetmap.org) | Straßenkarte | Tile Usage Policy: geringe Last, Namensnennung |
| [basemap.at](https://basemap.at) | Luftbild Österreich | CC BY 4.0 |
| [Photon (komoot)](https://photon.komoot.io) | Gipfel/Hütten in der Nähe, Ortssuche | Faire Nutzung, Ergebnisse werden zwischengespeichert |
| [Nominatim](https://nominatim.org) | Gipfelhöhe aus OpenStreetMap | Höchstens 1 Anfrage/Sekunde – die App fragt nur einmal pro übernommener Position |
| [Open-Meteo Elevation](https://open-meteo.com/en/docs/elevation-api) | Geländehöhe (Copernicus-DEM 90 m) | Kostenlos für nicht-kommerzielle Nutzung |
| [Supabase](https://supabase.com) | Datenbank, Fotos, Login | Kostenloser Tarif |
| [Streamlit Community Cloud](https://streamlit.io/cloud) | Betrieb der App | Kostenlos, Code muss öffentlich auf GitHub liegen |

**So entstehen Name und Höhe:** Liegt ein Gipfel, eine Hütte, ein Joch oder ein Klettergebiet
höchstens 300 m vom Fadenkreuz entfernt, wird sein Name vorgeschlagen. Weiter entfernte Gipfel
erscheinen nur als antippbare Vorschläge; Orte und Straßen werden nie als Gipfelname
eingesetzt. Die Höhe kommt bevorzugt aus der in OpenStreetMap eingetragenen Gipfelhöhe,
sonst aus dem Geländemodell – dann auf 10 m gerundet und als „ca.“ gekennzeichnet. Wer die
Höhe ändert, sieht „selbst eingetragen“.

---

## 10. Getestet und Einschränkungen

**Automatisch getestet** (29 Tests, `python -m pytest`, alle bestanden am 29.10.2026):

- Tour anlegen, ändern, löschen; doppeltes Abschicken legt keine zweite Tour an
- Tour ohne Name, Dauer und Höhe speicherbar (Ersatzname „Wanderung vom …“)
- Gipfelname und Höhe werden vorgeschlagen und lassen sich ändern (Quelle wird dann „selbst eingetragen“)
- Fotos: JPEG/PNG/WebP angenommen, GIF und kaputte Dateien abgelehnt, Handy-Drehung korrigiert,
  GPS-Daten entfernt, Verkleinerung auf 2.400 px
- Gelöschtes Titelbild / gelöschte Tour hinterlässt keine Dateien
- Daten und Fotos sind nach einem Neustart noch da (lokaler Speicher)
- ZIP-Sicherung → Einspielen in leeren Speicher: Touren, Koordinaten, Fotos, Bildunterschriften,
  Titelbild, Umlaute und Sonderzeichen bleiben erhalten; zweites Einspielen legt nichts doppelt an
- Statistik zählt fehlende Höhenmeter/Dauer nicht als 0; Filter und Sortierung
- Gipfelsuche bei ausgefallenem Internet: keine Fehlermeldung, App bleibt bedienbar
- Alle Seiten laufen ohne Fehler; Suche in „Meine Touren“; Bearbeiten speichert
- Cloud-Modus ohne Anmeldung zeigt nur die Anmeldeseite, keine Touren

**Von Hand geprüft:** Server startet, Manifest und Symbole werden ausgeliefert; Live-Abfrage
der Gipfelerkennung (Wildspitze → „Wildspitze, 3.768 m“; Innsbruck → kein Gipfelname, nur
„Nächster Ort“).

**Noch nicht geprüft – bitte selbst testen:**

- Bedienung im echten Browser und am Handy (Verschieben der Karte unter dem Fadenkreuz,
  Antippen der Symbole, Fotoauswahl vom Handy). Die automatischen Tests laufen ohne Browser.
- Der Cloud-Modus mit einem echten Supabase-Projekt (es war kein Konto vorhanden). Bitte nach
  der Einrichtung einmal: Tour mit Fotos anlegen, Seite neu laden, anmelden, Fotos sichtbar?
  Und: In einem privaten Browserfenster ohne Anmeldung darf nichts zu sehen sein.
- Das Startbildschirm-Symbol auf iPhone und Android (siehe Abschnitt 7).

**Bekannte Einschränkungen:**

- Kein Offline-Modus; ohne Internet keine Karte.
- Nach Neuladen der Seite ist eine neue Anmeldung nötig.
- iPhone-Fotos im HEIC-Format: Safari wandelt sie beim Hochladen normalerweise automatisch in
  JPEG um. Falls nicht, in den iPhone-Einstellungen → Kamera → Formate „Maximale Kompatibilität“ wählen.
- Fotos werden auf 2.400 px verkleinert gespeichert – die Originale bitte zusätzlich aufheben.
- Die Region kommt aus OpenStreetMap (z. B. „Bezirk Imst, Tirol“) und ist frei änderbar.

---

## 11. Projektstruktur

```
Claude-Wandern/
├── streamlit_app.py         Startdatei: Navigation, Login, Fehlerbehandlung
├── app_pages/               Die Seiten (Karte, Neue Tour, Meine Touren, Statistik, Einstellungen, Tour)
├── src/
│   ├── models.py            Tourenarten, Felder, Prüfungen, Doppelt-Erkennung
│   ├── database.py          Speicher: lokal (SQLite) und Supabase, Löschstrategie
│   ├── photo_storage.py     Fotos prüfen, drehen, verkleinern, GPS entfernen
│   ├── geocoding.py         Gipfelname, Region, Höhe, Ortssuche
│   ├── map_utils.py         Kartenquellen, Tourensymbole, Legende
│   ├── statistics.py        Filter, Sortierung, Kennzahlen
│   ├── backup.py            CSV, JSON, ZIP-Sicherung, Wiederherstellung
│   ├── config.py            Betriebsart, Secrets, Anmeldung
│   ├── ui.py                Fadenkreuz-Karte, Formular, Tourenansicht, Galerie
│   └── pwa.py               Manifest und Startbildschirm-Symbol
├── supabase/schema.sql      Tabellen, Row Level Security, privater Foto-Speicher
├── assets/                  App-Symbol in mehreren Größen (Oberfläche)
├── static/                  Manifest und Symbole für den Startbildschirm
├── tools/icons_erzeugen.py  Erzeugt alle Symbole neu
├── tests/                   Automatische Tests
├── .streamlit/config.toml   Farben, Upload-Grenze, keine technischen Fehlertexte
├── .streamlit/secrets.toml.example   Vorlage für die Zugangsdaten
├── requirements.txt
└── start_lokal.bat          Start unter Windows per Doppelklick
```
