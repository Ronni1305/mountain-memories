"""Karten mit Folium: topografische Grundkarte, Tourensymbole und Legende.

Kartenquellen und Nutzungsbedingungen (geprüft für eine private, wenig genutzte App):

* OpenTopoMap – frei nutzbar mit Namensnennung (CC-BY-SA), keine Massenabrufe.
  Höhenlinien, Gipfel, Wege; Standardkarte.
* OpenStreetMap Standard – frei nutzbar mit Namensnennung nach der OSM Tile Usage Policy
  (geringe Last, eindeutige App-Kennung durch den Browser).
* basemap.at Orthofoto – Luftbild für Österreich, Open Government Data (CC BY 4.0).
"""
from __future__ import annotations

import folium
from folium.plugins import LocateControl, MarkerCluster

from .models import ARTEN, art_label, datum_text, hoehe_text

STANDARD_MITTE = (47.10, 11.30)  # Tirol
STANDARD_ZOOM = 8

KARTEN = [
    {
        "name": "Topografische Karte",
        "tiles": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "attr": 'Kartendaten: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, '
                'SRTM | Darstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
        "max_zoom": 17,
    },
    {
        "name": "Straßenkarte",
        "tiles": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attr": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende',
        "max_zoom": 19,
    },
    {
        "name": "Luftbild (nur Österreich)",
        "tiles": "https://mapsneu.wien.gv.at/basemap/bmaporthofoto30cm/normal/google3857/{z}/{y}/{x}.jpeg",
        "attr": 'Luftbild: <a href="https://basemap.at">basemap.at</a> (CC BY 4.0)',
        "max_zoom": 19,
    },
]

# Weiße Symbole (24 × 24) auf farbigem Grund – auch auf kleinen Displays gut unterscheidbar.
SYMBOLE = {
    "wandern": (
        '<circle cx="13.5" cy="4" r="2.2" fill="#fff"/>'
        '<path d="M12.5 7.5 10.5 14 8 20.5M10.5 14l3 3v4M12 8.5l3.2 3.2M16.5 10.5l1.2 10.5" '
        'stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        '<rect x="7" y="7.5" width="3.6" height="5.5" rx="1.2" fill="#fff" transform="rotate(16 8.8 10.2)"/>'
    ),
    "klettern": (
        # Karabiner
        '<path d="M9.5 3.5h4.2a4.3 4.3 0 0 1 4.3 4.3v8.4a4.3 4.3 0 0 1-4.3 4.3h-3.4a4.3 4.3 0 0 1-4.3-4.3V8.2" '
        'stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
        '<path d="M6 9.5 9.6 3.6" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>'
        '<rect x="13.3" y="9" width="2.4" height="6" rx="1" fill="#fff"/>'
    ),
    "bergsteigen": (
        '<path d="M1.8 20.5 9.4 8.2l3.4 5.2 2.6-3.3 6.8 10.4Z" fill="#fff"/>'
        '<path d="M9.4 8.2V2.4" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>'
        '<path d="M9.4 2.4l4.4 1.5-4.4 1.6Z" fill="#fff"/>'
    ),
}
# Zusätzlich zur Farbe unterschiedliche Formen (Kreis, abgerundetes Quadrat, Raute-Rand),
# damit die Arten auch bei Farbschwäche unterscheidbar bleiben.
FORMEN = {"wandern": "50%", "klettern": "22%", "bergsteigen": "50% 50% 50% 6%"}


HERZ_HTML = ('<span style="position:absolute;top:-7px;right:-7px;font-size:14px;line-height:1;'
             'filter:drop-shadow(0 0 1px #fff) drop-shadow(0 0 1px #fff)">❤️</span>')


def symbol_html(art: str, groesse: int = 34, favorit: bool = False) -> str:
    farbe = ARTEN.get(art, {}).get("farbe", "#555")
    innen = int(groesse * 0.62)
    return (
        f'<div style="position:relative;width:{groesse}px;height:{groesse}px;border-radius:{FORMEN.get(art, "50%")};'
        f'background:{farbe};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);'
        f'display:flex;align-items:center;justify-content:center;">'
        f'<svg width="{innen}" height="{innen}" viewBox="0 0 24 24" aria-hidden="true">{SYMBOLE.get(art, "")}</svg>'
        f'{HERZ_HTML if favorit else ""}</div>'
    )


def legende_html() -> str:
    teile = [
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;white-space:nowrap">'
        f'{symbol_html(art, 24)}<span>{info["label"]}</span></span>'
        for art, info in ARTEN.items()
    ]
    teile.append('<span style="display:inline-flex;align-items:center;gap:6px;white-space:nowrap">'
                 '<span>❤️</span><span>Favorit</span></span>')
    return f'<div style="display:flex;flex-wrap:wrap;row-gap:6px;font-size:0.95rem">{"".join(teile)}</div>'


def grundkarte(mitte=STANDARD_MITTE, zoom=STANDARD_ZOOM, standort_knopf: bool = True) -> folium.Map:
    karte = folium.Map(location=list(mitte), zoom_start=zoom, tiles=None, control_scale=True,
                       max_zoom=19, prefer_canvas=False)
    for i, k in enumerate(KARTEN):
        folium.TileLayer(tiles=k["tiles"], attr=k["attr"], name=k["name"], max_zoom=19,
                         max_native_zoom=k["max_zoom"], show=(i == 0), subdomains="abc").add_to(karte)
    folium.LayerControl(position="topright", collapsed=True).add_to(karte)
    if standort_knopf:
        LocateControl(strings={"title": "Meinen Standort zeigen"}, flyTo=True,
                      locateOptions={"enableHighAccuracy": True, "maxZoom": 15}).add_to(karte)
    return karte


def _tooltip(tour: dict) -> str:
    teile = [tour.get("name") or "Tour", datum_text(tour.get("datum"))]
    if hoehe_text(tour):
        teile.append(hoehe_text(tour))
    return " · ".join(teile)


def tourenkarte(touren: list[dict]) -> folium.Map:
    """Karte mit allen übergebenen Touren als Symbole; Ausschnitt passt sich an."""
    mit_pos = [t for t in touren if t.get("lat") is not None and t.get("lon") is not None]
    karte = grundkarte()
    ziel = MarkerCluster(options={"disableClusteringAtZoom": 12, "maxClusterRadius": 40}) if len(mit_pos) > 60 else karte
    if ziel is not karte:
        ziel.add_to(karte)
    for t in mit_pos:
        folium.Marker(
            location=[t["lat"], t["lon"]],
            icon=folium.DivIcon(html=symbol_html(t.get("art"), favorit=bool(t.get("favorit"))), icon_size=(34, 34), icon_anchor=(17, 17),
                                class_name="mm-symbol"),
            tooltip=f"{art_label(t.get('art'))}: {_tooltip(t)}",
        ).add_to(ziel)
    if len(mit_pos) == 1:
        karte.location = [mit_pos[0]["lat"], mit_pos[0]["lon"]]
        karte.options["zoom"] = 12
    elif mit_pos:
        lats = [t["lat"] for t in mit_pos]
        lons = [t["lon"] for t in mit_pos]
        karte.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(30, 30), max_zoom=13)
    return karte


def touren_am_punkt(touren: list[dict], lat: float, lon: float, toleranz: float = 1e-5) -> list[dict]:
    """Alle Touren an einem angetippten Symbol (derselbe Gipfel kann mehrfach besucht sein)."""
    return [t for t in touren if t.get("lat") is not None
            and abs(t["lat"] - lat) <= toleranz and abs(t["lon"] - lon) <= toleranz]
