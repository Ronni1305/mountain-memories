"""Gipfelnamen, Region und Höhe zu einer Position ermitteln.

Verwendete freie Dienste (ohne Schlüssel, alle mit OpenStreetMap-Daten bzw. Geländemodell):

* Photon (komoot) – Gipfel, Hütten, Sättel und Klettergebiete in der Nähe, Region
* Nominatim (OpenStreetMap) – die in OSM eingetragene Gipfelhöhe (``ele``)
* Open-Meteo Elevation – Geländehöhe aus dem Copernicus-Höhenmodell (90 m Raster)
  als Ersatz, wenn kein Gipfel mit Höhe gefunden wird

Alle Anfragen haben kurze Zeitlimits und werden zwischengespeichert. Fällt ein Dienst aus,
liefern die Funktionen einfach weniger Ergebnisse – die App bleibt bedienbar.

Wichtig: Ein Name wird nur dann automatisch vorgeschlagen, wenn ein Gipfel oder eine Hütte
höchstens ``AUTO_RADIUS_M`` entfernt ist. Gemeinden und Straßen werden nie als Gipfelname
übernommen, sondern nur als Hinweis „in der Nähe von …“ angezeigt.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests
import streamlit as st

from .models import abstand_m

USER_AGENT = "MountainMemories/1.0 (privates Tourenbuch; Streamlit-App)"
ZEITLIMIT = 8
SUCHRADIUS_KM = 2.0
AUTO_RADIUS_M = 300

PHOTON = "https://photon.komoot.io"
NOMINATIM = "https://nominatim.openstreetmap.org"
OPEN_METEO = "https://api.open-meteo.com/v1/elevation"

ORT_TYPEN = {
    "natural:peak": "Gipfel",
    "natural:volcano": "Gipfel",
    "natural:saddle": "Sattel / Joch",
    "tourism:alpine_hut": "Hütte",
    "tourism:wilderness_hut": "Hütte",
    "sport:climbing": "Klettergebiet",
    "natural:cliff": "Felswand",
}


@dataclass
class Kandidat:
    name: str
    typ: str
    abstand_m: float
    lat: float
    lon: float
    osm_id: str | None = None
    hoehe_m: int | None = None


@dataclass
class OrtsInfo:
    kandidaten: list[Kandidat] = field(default_factory=list)
    vorschlag: Kandidat | None = None
    region: str | None = None
    ort: str | None = None
    gelaendehoehe_m: int | None = None
    hinweise: list[str] = field(default_factory=list)


def _get(url: str, params) -> dict | list | None:
    antwort = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=ZEITLIMIT)
    antwort.raise_for_status()
    return antwort.json()


# --------------------------------------------------------------------------------------------
# Auswertung der Antworten (ohne Netz, getestet in tests/test_geocoding.py)
# --------------------------------------------------------------------------------------------

def kandidaten_aus_photon(antwort: dict, lat: float, lon: float, radius_m: float) -> list[Kandidat]:
    ergebnis: dict[str, Kandidat] = {}
    for f in (antwort or {}).get("features", []):
        p = f.get("properties", {})
        name = (p.get("name") or "").strip()
        typ = ORT_TYPEN.get(f"{p.get('osm_key')}:{p.get('osm_value')}")
        try:
            k_lon, k_lat = f["geometry"]["coordinates"][:2]
        except (KeyError, TypeError, ValueError):
            continue
        if not name or not typ:
            continue
        d = abstand_m(lat, lon, k_lat, k_lon)
        if d > radius_m:
            continue
        osm_id = f"{p.get('osm_type', '')}{p.get('osm_id', '')}" if p.get("osm_id") else None
        schluessel = f"{name.casefold()}|{typ}"
        if schluessel not in ergebnis or d < ergebnis[schluessel].abstand_m:
            ergebnis[schluessel] = Kandidat(name, typ, d, k_lat, k_lon, osm_id)
    # Gipfel zuerst, dann nach Entfernung
    return sorted(ergebnis.values(), key=lambda k: (k.typ != "Gipfel", k.abstand_m))


def region_aus_photon(antwort: dict) -> tuple[str | None, str | None]:
    """(Region, nächstgelegener Ort) aus einer Photon-Reverse-Antwort."""
    features = (antwort or {}).get("features") or []
    if not features:
        return None, None
    p = features[0].get("properties", {})
    ort = p.get("city") or p.get("town") or p.get("village") or p.get("locality") or p.get("district")
    teile = [p.get("county"), p.get("state")]
    if p.get("countrycode") not in (None, "AT", "DE", "CH", "IT"):
        teile.append(p.get("country"))
    region = ", ".join(t for t in teile if t) or p.get("country")
    return region, ort


def hoehen_aus_nominatim(antwort: list) -> dict[str, int]:
    hoehen = {}
    for eintrag in antwort or []:
        ele = (eintrag.get("extratags") or {}).get("ele")
        try:
            wert = int(round(float(str(ele).replace(",", ".").split()[0].rstrip("m"))))
        except (TypeError, ValueError, IndexError):
            continue
        if -450 <= wert <= 8900:
            hoehen[f"{eintrag.get('osm_type', '')[:1].upper()}{eintrag.get('osm_id')}"] = wert
    return hoehen


def vorschlag_waehlen(kandidaten: list[Kandidat], auto_radius_m: float = AUTO_RADIUS_M) -> Kandidat | None:
    nahe = [k for k in kandidaten if k.abstand_m <= auto_radius_m and k.typ in ("Gipfel", "Hütte", "Sattel / Joch", "Klettergebiet")]
    return min(nahe, key=lambda k: (k.typ != "Gipfel", k.abstand_m)) if nahe else None


# --------------------------------------------------------------------------------------------
# Netzabfragen (zwischengespeichert)
# --------------------------------------------------------------------------------------------

@st.cache_data(ttl=7 * 24 * 3600, max_entries=500, show_spinner=False)
def _photon_umgebung(lat: float, lon: float) -> dict:
    params = [("lat", lat), ("lon", lon), ("radius", SUCHRADIUS_KM), ("limit", 15), ("lang", "de")]
    params += [("osm_tag", t) for t in ORT_TYPEN]
    return _get(f"{PHOTON}/reverse", params)


@st.cache_data(ttl=7 * 24 * 3600, max_entries=500, show_spinner=False)
def _photon_region(lat: float, lon: float) -> dict:
    return _get(f"{PHOTON}/reverse", {"lat": lat, "lon": lon, "limit": 1, "lang": "de"})


@st.cache_data(ttl=30 * 24 * 3600, max_entries=500, show_spinner=False)
def _nominatim_hoehen(osm_ids: tuple[str, ...]) -> list:
    return _get(f"{NOMINATIM}/lookup", {"osm_ids": ",".join(osm_ids), "format": "jsonv2", "extratags": 1})


@st.cache_data(ttl=30 * 24 * 3600, max_entries=1000, show_spinner=False)
def gelaendehoehe(lat: float, lon: float) -> int | None:
    daten = _get(OPEN_METEO, {"latitude": lat, "longitude": lon})
    werte = (daten or {}).get("elevation") or []
    if not werte or werte[0] is None:
        return None
    return int(round(float(werte[0]) / 10.0) * 10)  # auf 10 m gerundet – genauer ist das Modell nicht


def ort_bestimmen(lat: float, lon: float) -> OrtsInfo:
    """Fragt alle Dienste ab. Wirft nie eine Ausnahme; Ausfälle stehen in ``hinweise``."""
    lat, lon = round(lat, 5), round(lon, 5)
    info = OrtsInfo()
    try:
        info.kandidaten = kandidaten_aus_photon(_photon_umgebung(lat, lon), lat, lon, SUCHRADIUS_KM * 1000)[:6]
    except Exception:  # noqa: BLE001
        info.hinweise.append("Die Gipfelsuche ist gerade nicht erreichbar – bitte den Namen selbst eintragen.")
    ids = tuple(k.osm_id for k in info.kandidaten if k.osm_id and k.osm_id[0] in "NWR")
    if ids:
        try:
            hoehen = hoehen_aus_nominatim(_nominatim_hoehen(ids))
            for k in info.kandidaten:
                k.hoehe_m = hoehen.get(k.osm_id)
        except Exception:  # noqa: BLE001
            pass
    info.vorschlag = vorschlag_waehlen(info.kandidaten)
    try:
        info.region, info.ort = region_aus_photon(_photon_region(lat, lon))
    except Exception:  # noqa: BLE001
        pass
    try:
        info.gelaendehoehe_m = gelaendehoehe(lat, lon)
    except Exception:  # noqa: BLE001
        info.hinweise.append("Die automatische Höhe ist gerade nicht verfügbar – bei Bedarf selbst eintragen.")
    return info


@st.cache_data(ttl=24 * 3600, max_entries=300, show_spinner=False)
def ort_suchen(text: str, nahe_lat: float | None = None, nahe_lon: float | None = None) -> list[dict]:
    """Freitextsuche („Wildspitze“, „Innsbruck“) zum schnellen Hinspringen auf der Karte."""
    params = {"q": text, "limit": 6, "lang": "de"}
    if nahe_lat is not None and nahe_lon is not None:
        params.update(lat=nahe_lat, lon=nahe_lon)
    treffer = []
    for f in (_get(f"{PHOTON}/api/", params) or {}).get("features", []):
        p = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"][:2]
        zusatz = ", ".join(x for x in (p.get("city") or p.get("county"), p.get("state"), p.get("country")) if x)
        treffer.append({"name": p.get("name") or zusatz, "zusatz": zusatz, "lat": lat, "lon": lon,
                        "art": SUCH_ARTEN.get(p.get("osm_value"))})
    return treffer


# Art des Treffers, damit gleichnamige Treffer unterscheidbar sind („Wildspitze“ als Gipfel,
# Bergstation und Sessellift).
SUCH_ARTEN = {
    "peak": "Gipfel", "volcano": "Gipfel", "saddle": "Sattel", "mountain_pass": "Pass", "ridge": "Grat",
    "alpine_hut": "Hütte", "wilderness_hut": "Hütte", "hut": "Hütte", "glacier": "Gletscher",
    "station": "Station", "chair_lift": "Sessellift", "cable_car": "Seilbahn", "gondola": "Gondelbahn",
    "drag_lift": "Schlepplift", "restaurant": "Restaurant", "hotel": "Hotel", "parking": "Parkplatz",
    "city": "Stadt", "town": "Ort", "village": "Ort", "hamlet": "Weiler", "locality": "Flur",
    "lake": "See", "water": "See", "reservoir": "Stausee", "valley": "Tal", "climbing": "Klettergebiet",
    "crag": "Klettergebiet", "cliff": "Felswand", "waterfall": "Wasserfall",
}


def treffer_text(i: int, t: dict) -> str:
    """Eindeutige Beschriftung – die Auswahlliste unterscheidet Einträge nur am Text."""
    art = f" ({t['art']})" if t.get("art") else ""
    return f"{i + 1}. {t['name']}{art} – {t['zusatz']}"
