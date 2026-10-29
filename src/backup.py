"""Export (CSV, JSON), vollständige Sicherung als ZIP und Wiederherstellung.

Aufbau der ZIP-Sicherung::

    mountain-memories-sicherung-2026-10-29.zip
    ├── sicherung.json        alle Touren + Foto-Metadaten, jede Foto-Zeile mit "datei"
    ├── touren.csv            dieselben Touren als Tabelle (öffnet in Excel)
    ├── LIESMICH.txt
    └── fotos/2026-07-14_Wildspitze_1a2b3c4d/01_<foto-id>.jpg ...

Die Wiederherstellung übernimmt die IDs aus der Sicherung. Touren, die es schon gibt,
werden übersprungen – eine Sicherung kann also gefahrlos mehrmals eingespielt werden.
So lassen sich auch Testdaten aus dem lokalen Modus in die Cloud übertragen.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date

from .database import SchonVorhanden, SpeicherFehler
from .models import ARTEN, TOUR_FELDER, art_label, bereinigen, dauer_text, jetzt_iso
from .photo_storage import FotoFehler, aufbereiten

FORMAT = "mountain-memories-sicherung"
VERSION = 1

CSV_SPALTEN = [
    ("datum", "Datum"), ("art", "Tourenart"), ("name", "Name / Gipfel"), ("hoehe_m", "Höhe (m)"),
    ("hoehe_quelle", "Höhe – Quelle"), ("region", "Region"), ("lat", "Breite"), ("lon", "Länge"),
    ("dauer", "Dauer"), ("dauer_min", "Dauer (min)"), ("partner", "Bergpartner"),
    ("ausgangspunkt", "Ausgangspunkt"), ("ziel", "Ziel / Gipfel"), ("hm_auf", "Hm Aufstieg"),
    ("hm_ab", "Hm Abstieg"), ("schwierigkeit", "Schwierigkeit"), ("wetter", "Wetter / Bedingungen"),
    ("bewertung", "Bewertung (1–5)"), ("favorit", "Favorit"), ("bericht", "Bericht"), ("fotos", "Anzahl Fotos"), ("id", "ID"),
]


def _ordnername(tour: dict) -> str:
    name = re.sub(r"[^\w\-]+", "_", tour.get("name") or "Tour", flags=re.UNICODE).strip("_")[:40]
    return f"{tour.get('datum') or 'ohne-datum'}_{name}_{str(tour['id'])[:8]}"


def touren_csv(touren: list[dict], fotos: list[dict]) -> bytes:
    """CSV mit Semikolon und UTF-8-BOM – so zeigt Excel Umlaute korrekt an."""
    anzahl = {}
    for f in fotos:
        anzahl[f["tour_id"]] = anzahl.get(f["tour_id"], 0) + 1
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    schreiber.writerow([titel for _, titel in CSV_SPALTEN])
    for t in touren:
        zeile = []
        for k, _ in CSV_SPALTEN:
            if k == "art":
                wert = art_label(t.get("art"), mit_emoji=False)
            elif k == "dauer":
                wert = dauer_text(t.get("dauer_min")) or ""
            elif k == "favorit":
                wert = "ja" if t.get("favorit") else ""
            elif k == "fotos":
                wert = anzahl.get(t["id"], 0)
            elif k in ("lat", "lon") and t.get(k) is not None:
                wert = f"{t[k]:.6f}".replace(".", ",")
            else:
                wert = t.get(k)
            zeile.append("" if wert is None else wert)
        schreiber.writerow(zeile)
    return puffer.getvalue().encode("utf-8-sig")


def sicherung_json(touren: list[dict], fotos: list[dict], dateien: dict[str, str] | None = None) -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "exportiert_am": jetzt_iso(),
        "anzahl_touren": len(touren),
        "anzahl_fotos": len(fotos),
        "touren": [{k: t.get(k) for k in TOUR_FELDER} for t in touren],
        "fotos": [
            {
                "id": f["id"], "tour_id": f["tour_id"], "dateiname": f.get("dateiname"),
                "beschriftung": f.get("beschriftung"), "created_at": f.get("created_at"),
                **({"datei": dateien[f["id"]]} if dateien and f["id"] in dateien else {}),
            }
            for f in fotos
        ],
    }


LIESMICH = """Mountain Memories – Sicherung
================================

sicherung.json  Alle Touren mit Koordinaten und die Zuordnung der Fotos (Feld "datei").
touren.csv      Die Touren als Tabelle (Excel: Datei öffnen, Trennzeichen Semikolon).
fotos/          Ein Ordner pro Tour (Datum_Name_ID), darin die Fotos in voller Größe.

Wiederherstellen: In der App unter „Einstellungen“ → „Sicherung einspielen“ diese ZIP-Datei
auswählen. Bereits vorhandene Touren werden nicht doppelt angelegt.
"""


def sicherung_zip(speicher, fortschritt=None) -> tuple[bytes, list[str]]:
    """Erstellt die ZIP-Sicherung. Gibt (Daten, Liste nicht geladener Fotos) zurück."""
    touren = speicher.list_tours()
    fotos = speicher.list_photos()
    nach_tour = {t["id"]: t for t in touren}
    zaehler: dict[str, int] = {}
    dateien, fehler = {}, []
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for i, f in enumerate(fotos, start=1):
            tour = nach_tour.get(f["tour_id"])
            if not tour:
                continue
            zaehler[tour["id"]] = zaehler.get(tour["id"], 0) + 1
            pfad = f"fotos/{_ordnername(tour)}/{zaehler[tour['id']]:02d}_{f['id']}.jpg"
            try:
                z.writestr(pfad, speicher.photo_bytes(f), compress_type=zipfile.ZIP_STORED)
                dateien[f["id"]] = pfad
            except (SpeicherFehler, OSError):
                fehler.append(f.get("dateiname") or f["id"])
            if fortschritt:
                fortschritt(i / max(len(fotos), 1))
        z.writestr("sicherung.json", json.dumps(sicherung_json(touren, fotos, dateien), ensure_ascii=False, indent=2))
        z.writestr("touren.csv", touren_csv(touren, fotos))
        z.writestr("LIESMICH.txt", LIESMICH)
    return puffer.getvalue(), fehler


def dateiname_heute(endung: str) -> str:
    return f"mountain-memories-sicherung-{date.today().isoformat()}.{endung}"


@dataclass
class ImportErgebnis:
    touren_neu: int = 0
    touren_vorhanden: int = 0
    fotos_neu: int = 0
    fehler: list[str] = field(default_factory=list)


def sicherung_lesen(daten: bytes, dateiname: str) -> tuple[dict, zipfile.ZipFile | None]:
    try:
        if dateiname.lower().endswith(".zip"):
            z = zipfile.ZipFile(io.BytesIO(daten))
            inhalt = json.loads(z.read("sicherung.json").decode("utf-8"))
        else:
            z = None
            inhalt = json.loads(daten.decode("utf-8-sig"))
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Die Datei ist keine gültige Mountain-Memories-Sicherung.") from exc
    if not isinstance(inhalt, dict) or inhalt.get("format") != FORMAT:
        raise ValueError("Die Datei ist keine gültige Mountain-Memories-Sicherung.")
    if int(inhalt.get("version", 0)) > VERSION:
        raise ValueError("Diese Sicherung stammt aus einer neueren App-Version.")
    return inhalt, z


def sicherung_einspielen(speicher, inhalt: dict, z: zipfile.ZipFile | None, fortschritt=None) -> ImportErgebnis:
    erg = ImportErgebnis()
    vorhanden = {t["id"] for t in speicher.list_tours()}
    fotos_je_tour: dict[str, list[dict]] = {}
    for f in inhalt.get("fotos", []):
        fotos_je_tour.setdefault(f.get("tour_id"), []).append(f)
    touren = inhalt.get("touren", [])
    for i, roh in enumerate(touren, start=1):
        tour = bereinigen(roh)
        if not tour.get("id") or tour.get("art") not in ARTEN:
            erg.fehler.append(f"Tour „{roh.get('name')}“ übersprungen (unvollständig).")
            continue
        if tour["id"] in vorhanden:
            erg.touren_vorhanden += 1
            continue
        titelbild = tour.pop("titelbild_id", None)
        try:
            speicher.create_tour(tour)
        except SchonVorhanden:
            erg.touren_vorhanden += 1
            continue
        except SpeicherFehler as exc:
            erg.fehler.append(f"„{tour.get('name')}“: {exc}")
            continue
        erg.touren_neu += 1
        titel_ok = False
        for f in fotos_je_tour.get(tour["id"], []):
            if not z or not f.get("datei"):
                continue
            try:
                foto = aufbereiten(z.read(f["datei"]), f.get("dateiname") or "foto.jpg")
                speicher.add_photo(tour["id"], foto, f.get("beschriftung"), foto_id=f["id"])
                erg.fotos_neu += 1
                titel_ok = titel_ok or f["id"] == titelbild
            except KeyError:
                erg.fehler.append(f"Foto {f.get('dateiname')} fehlt in der ZIP-Datei.")
            except (FotoFehler, SpeicherFehler) as exc:
                erg.fehler.append(str(exc))
        if titel_ok:
            speicher.update_tour(tour["id"], {"titelbild_id": titelbild})
        if fortschritt:
            fortschritt(i / max(len(touren), 1))
    return erg
