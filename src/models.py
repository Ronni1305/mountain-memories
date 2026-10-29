"""Tourenarten, Felder und Hilfsfunktionen für eine Tour.

Eine Tour ist überall ein einfaches ``dict`` mit den Schlüsseln aus ``TOUR_FELDER``.
Fehlende Angaben sind ``None`` – niemals 0 –, damit Statistiken nicht verfälscht werden.
"""
from __future__ import annotations

import math
import re
import uuid
from datetime import date, datetime

ARTEN: dict[str, dict[str, str]] = {
    "wandern": {"label": "Wandern", "emoji": "🥾", "farbe": "#2e7d4f"},
    "klettern": {"label": "Klettern", "emoji": "🧗", "farbe": "#c25a12"},
    "bergsteigen": {"label": "Bergsteigen", "emoji": "🏔️", "farbe": "#1f4e8c"},
}

HOEHE_QUELLEN = {
    "osm": "aus OpenStreetMap (Gipfelhöhe)",
    "dem": "aus dem Geländemodell (ca., ±30 m)",
    "manuell": "selbst eingetragen",
}

TOUR_FELDER = [
    "id", "art", "name", "datum", "lat", "lon", "hoehe_m", "hoehe_quelle", "region",
    "dauer_min", "partner", "ausgangspunkt", "ziel", "hm_auf", "hm_ab", "schwierigkeit",
    "wetter", "bericht", "bewertung", "titelbild_id", "created_at", "updated_at",
]
FOTO_FELDER = [
    "id", "tour_id", "pfad", "thumb_pfad", "dateiname", "beschriftung", "breite", "hoehe",
    "bytes", "created_at",
]
GANZZAHL_FELDER = {"hoehe_m", "dauer_min", "hm_auf", "hm_ab", "bewertung"}
TEXT_FELDER = {"name", "region", "partner", "ausgangspunkt", "ziel", "schwierigkeit", "wetter", "bericht"}


def art_label(art: str | None, mit_emoji: bool = True) -> str:
    info = ARTEN.get(art or "")
    if not info:
        return "Unbekannt"
    return f"{info['emoji']} {info['label']}" if mit_emoji else info["label"]


def neue_id() -> str:
    return str(uuid.uuid4())


def jetzt_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def als_datum(wert) -> date | None:
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    try:
        return date.fromisoformat(str(wert)[:10])
    except ValueError:
        return None


def datum_text(wert) -> str:
    d = als_datum(wert)
    return d.strftime("%d.%m.%Y") if d else "–"


def dauer_text(minuten) -> str | None:
    if minuten is None:
        return None
    h, m = divmod(int(minuten), 60)
    if h and m:
        return f"{h} h {m:02d} min"
    return f"{h} h" if h else f"{m} min"


def hoehe_text(tour: dict) -> str | None:
    h = tour.get("hoehe_m")
    if h is None:
        return None
    text = f"{int(h):,} m".replace(",", ".")
    return f"ca. {text}" if tour.get("hoehe_quelle") == "dem" else text


def partner_liste(text: str | None) -> list[str]:
    """„Anna, Ben; Clara“ → ["Anna", "Ben", "Clara"] (Komma, Semikolon oder „und“ trennen)."""
    if not text:
        return []
    teile = re.split(r"\s*(?:,|;|\bund\b|&|\n)\s*", text)
    return [t.strip() for t in teile if t and t.strip()]


def name_schluessel(name: str | None) -> str:
    """Vergleichsschlüssel für Gipfel-/Tourennamen (Groß-/Kleinschreibung, Leerzeichen egal)."""
    return re.sub(r"\s+", " ", (name or "").strip()).casefold()


def abstand_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def ersatz_name(art: str, datum, ort: str | None = None) -> str:
    """Name, falls weder erkannt noch eingetragen – die Speicherung soll nie daran scheitern."""
    label = {"wandern": "Wanderung", "klettern": "Klettertour", "bergsteigen": "Bergtour"}.get(art, "Tour")
    return f"{label} bei {ort}" if ort else f"{label} vom {datum_text(datum)}"


def bereinigen(daten: dict) -> dict:
    """Bringt Formular- oder Importdaten in eine einheitliche Form (leere Texte → None)."""
    tour = {k: daten.get(k) for k in TOUR_FELDER if k in daten}
    for k in TEXT_FELDER & tour.keys():
        v = tour[k]
        tour[k] = v.strip() if isinstance(v, str) and v.strip() else None
    for k in GANZZAHL_FELDER & tour.keys():
        v = tour[k]
        if v is None or v == "":
            tour[k] = None
        else:
            try:
                tour[k] = int(round(float(v)))
            except (TypeError, ValueError):
                tour[k] = None
    for k in ("lat", "lon"):
        if k in tour and tour[k] is not None:
            tour[k] = float(tour[k])
    if "datum" in tour:
        d = als_datum(tour["datum"])
        tour["datum"] = d.isoformat() if d else None
    if tour.get("bewertung") is not None and not 1 <= tour["bewertung"] <= 5:
        tour["bewertung"] = None
    if "hoehe_m" in tour and tour["hoehe_m"] is None:
        tour["hoehe_quelle"] = None
    return tour


def pruefen(tour: dict) -> list[str]:
    """Liefert verständliche Fehlermeldungen; leere Liste = in Ordnung."""
    fehler = []
    if tour.get("art") not in ARTEN:
        fehler.append("Bitte eine Tourenart wählen.")
    if not tour.get("datum"):
        fehler.append("Bitte ein Datum angeben.")
    lat, lon = tour.get("lat"), tour.get("lon")
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        fehler.append("Bitte die Position auf der Karte übernehmen.")
    if not tour.get("name"):
        fehler.append("Bitte einen Namen eintragen.")
    h = tour.get("hoehe_m")
    if h is not None and not -450 <= h <= 8900:
        fehler.append("Die Höhe muss zwischen -450 und 8.900 m liegen.")
    for k, label in (("hm_auf", "Aufstieg"), ("hm_ab", "Abstieg")):
        v = tour.get(k)
        if v is not None and not 0 <= v <= 10000:
            fehler.append(f"Höhenmeter im {label} müssen zwischen 0 und 10.000 liegen.")
    d = tour.get("dauer_min")
    if d is not None and not 0 < d <= 60 * 24 * 30:
        fehler.append("Die Dauer ist nicht plausibel.")
    return fehler


def moegliche_duplikate(neu: dict, touren: list[dict]) -> list[dict]:
    """Touren am selben Tag mit gleichem Namen oder (fast) gleicher Position."""
    treffer = []
    for t in touren:
        if t.get("id") == neu.get("id") or t.get("datum") != neu.get("datum"):
            continue
        gleicher_name = name_schluessel(t.get("name")) == name_schluessel(neu.get("name"))
        nah = (
            None not in (t.get("lat"), t.get("lon"), neu.get("lat"), neu.get("lon"))
            and abstand_m(t["lat"], t["lon"], neu["lat"], neu["lon"]) < 150
        )
        if gleicher_name or nah:
            treffer.append(t)
    return treffer
