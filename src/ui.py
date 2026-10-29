"""Gemeinsame Oberflächen-Bausteine für alle Seiten."""
from __future__ import annotations

from datetime import date

import folium
import streamlit as st
from streamlit_folium import st_folium

from . import geocoding, map_utils
from .database import SchonVorhanden, SpeicherFehler
from .models import (ARTEN, HOEHE_QUELLEN, art_label, bereinigen, datum_text, dauer_text, ersatz_name,
                     hoehe_text, moegliche_duplikate, neue_id, partner_liste, pruefen)
from .photo_storage import ERLAUBTE_ENDUNGEN, MAX_UPLOAD_MB, FotoFehler, aufbereiten

SS = st.session_state
SEITE_TOUR = "app_pages/tour.py"
SEITE_NEU = "app_pages/neue_tour.py"

FADENKREUZ_CSS = """<style>
.st-key-{key}{{position:relative}}
.st-key-{key}::after{{content:"";position:absolute;left:50%;top:50%;width:48px;height:48px;
transform:translate(-50%,-50%);pointer-events:none;z-index:5;border:2px solid #c62828;border-radius:50%;
background:linear-gradient(#c62828,#c62828) center/2px 100% no-repeat,
linear-gradient(#c62828,#c62828) center/100% 2px no-repeat;box-shadow:0 0 0 2px rgba(255,255,255,.9)}}
</style>"""


# --------------------------------------------------------------------------------------------
# Daten der Sitzung (einmal laden, nach Änderungen neu laden)
# --------------------------------------------------------------------------------------------

def touren(sp) -> list[dict]:
    if "mm_touren" not in SS:
        SS["mm_touren"] = sp.list_tours()
    return SS["mm_touren"]


def alle_fotos(sp) -> list[dict]:
    if "mm_fotos" not in SS:
        SS["mm_fotos"] = sp.list_photos()
    return SS["mm_fotos"]


def fotos_von(sp, tour_id: str) -> list[dict]:
    return [f for f in alle_fotos(sp) if f["tour_id"] == tour_id]


def neu_laden() -> None:
    SS.pop("mm_touren", None)
    SS.pop("mm_fotos", None)


def meldung(text: str, art: str = "success") -> None:
    """Meldung, die auch nach einem Seitenwechsel noch einmal angezeigt wird."""
    SS["mm_meldung"] = (art, text)


def meldung_zeigen() -> None:
    if "mm_meldung" in SS:
        art, text = SS.pop("mm_meldung")
        getattr(st, art)(text, icon=":material/check_circle:" if art == "success" else None)


def tour_oeffnen(tour_id: str, bearbeiten: bool = False) -> None:
    SS["mm_tour_id"] = tour_id
    SS["mm_bearbeiten"] = bearbeiten
    st.switch_page(SEITE_TOUR)


def titelbild(tour: dict, fotos: list[dict]) -> dict | None:
    if not fotos:
        return None
    return next((f for f in fotos if f["id"] == tour.get("titelbild_id")), fotos[0])


# --------------------------------------------------------------------------------------------
# Positionswahl mit Fadenkreuz
# --------------------------------------------------------------------------------------------

def _ansicht(prefix: str, start: tuple[float, float] | None) -> dict:
    schluessel = f"{prefix}_ansicht"
    if schluessel not in SS:
        if start:
            SS[schluessel] = {"center": tuple(start), "zoom": 14}
        else:
            letzte = (SS.get("mm_touren") or [None])[0]
            mitte = (letzte["lat"], letzte["lon"]) if letzte else map_utils.STANDARD_MITTE
            SS[schluessel] = {"center": mitte, "zoom": 11 if letzte else map_utils.STANDARD_ZOOM}
        SS[f"{prefix}_kartenstart"] = SS[schluessel]["center"]
    return SS[schluessel]


@st.fragment
def positions_auswahl(prefix: str, start: tuple[float, float] | None = None) -> None:
    """Karte mit festem Fadenkreuz. Verschieben nur dieses Bausteins lädt nicht die ganze Seite neu."""
    ansicht = _ansicht(prefix, start)

    with st.container(horizontal=True, vertical_alignment="bottom"):
        suche = st.text_input("Ort oder Gipfel suchen", key=f"{prefix}_suche",
                              placeholder="z. B. Wildspitze, Achensee …")
        st.button("Suchen", key=f"{prefix}_suche_los", icon=":material/search:")
    if suche.strip():
        try:
            treffer = geocoding.ort_suchen(suche.strip(), *ansicht["center"])
        except Exception:  # noqa: BLE001
            treffer = None
            st.warning("Die Ortssuche ist gerade nicht erreichbar. Die Karte lässt sich trotzdem verschieben.")
        if treffer == []:
            st.caption("Nichts gefunden – anders schreiben oder die Karte direkt verschieben.")
        elif treffer:
            auswahl = st.selectbox(
                "Suchergebnis", range(len(treffer)), index=None, key=f"{prefix}_treffer_{suche}",
                format_func=lambda i: f"{treffer[i]['name']} – {treffer[i]['zusatz']}",
                placeholder="Ergebnis wählen, um dorthin zu springen",
            )
            if auswahl is not None:
                ziel = (treffer[auswahl]["lat"], treffer[auswahl]["lon"])
                if ansicht["center"] != ziel:
                    SS[f"{prefix}_ansicht"] = ansicht = {"center": ziel, "zoom": 14}

    st.html(FADENKREUZ_CSS.format(key=f"{prefix}_kartenrahmen"))
    karte = map_utils.grundkarte(SS[f"{prefix}_kartenstart"], ansicht["zoom"])
    gruppe = folium.FeatureGroup(name="Gewählte Position")
    pos = SS.get(f"{prefix}_pos")
    if pos:
        folium.CircleMarker(pos, radius=7, color="#fff", weight=2, fill=True, fill_color="#c62828",
                            fill_opacity=1, tooltip="Übernommene Position").add_to(gruppe)
    with st.container(key=f"{prefix}_kartenrahmen"):
        daten = st_folium(karte, key=f"{prefix}_karte", height=420, use_container_width=True,
                          center=ansicht["center"], zoom=ansicht["zoom"], feature_group_to_add=gruppe,
                          returned_objects=["center", "zoom"]) or {}

    # Die aktuelle Kartenmitte nur lesen, nicht an die Karte zurückgeben – sonst würde sie bei
    # jedem Verschieben neu gesetzt. Die Karte bleibt beim Neuzeichnen von selbst, wo sie ist.
    mitte = daten.get("center")
    lat, lon = (mitte["lat"], mitte["lng"]) if mitte else ansicht["center"]
    st.caption(f"Fadenkreuz: {lat:.5f}, {lon:.5f} · Karte verschieben und zoomen, bis das rote Fadenkreuz "
               "auf dem Gipfel oder Tourenort liegt.")
    if st.button("Position übernehmen", key=f"{prefix}_uebernehmen", type="primary",
                 icon=":material/my_location:", width="stretch"):
        SS[f"{prefix}_pos"] = (round(lat, 6), round(lon, 6))
        st.rerun(scope="app")


# --------------------------------------------------------------------------------------------
# Tourenformular (neu und bearbeiten)
# --------------------------------------------------------------------------------------------

def _formular_vorbelegen(prefix: str, tour: dict) -> None:
    """Felder einmalig mit einer gespeicherten Tour füllen."""
    if SS.get(f"{prefix}_geladen") == tour["id"]:
        return
    for k in list(SS.keys()):
        if isinstance(k, str) and k.startswith(f"{prefix}_"):
            del SS[k]
    SS[f"{prefix}_geladen"] = tour["id"]
    SS[f"{prefix}_pos"] = (tour["lat"], tour["lon"])
    SS[f"{prefix}_geo_fuer"] = (tour["lat"], tour["lon"])  # keine automatische Suche beim Öffnen
    SS[f"{prefix}_art"] = tour["art"]
    SS[f"{prefix}_name"] = tour.get("name") or ""
    SS[f"{prefix}_datum"] = date.fromisoformat(tour["datum"][:10])
    SS[f"{prefix}_hoehe"] = tour.get("hoehe_m")
    SS[f"{prefix}_hoehe_auto"] = (tour.get("hoehe_m"), tour.get("hoehe_quelle"))
    SS[f"{prefix}_region"] = tour.get("region") or ""
    d = tour.get("dauer_min")
    SS[f"{prefix}_dauer_h"] = d // 60 if d is not None else None
    SS[f"{prefix}_dauer_m"] = d % 60 if d is not None else None
    for k in ("partner", "ausgangspunkt", "ziel", "schwierigkeit", "wetter", "bericht"):
        SS[f"{prefix}_{k}"] = tour.get(k) or ""
    for k in ("hm_auf", "hm_ab"):
        SS[f"{prefix}_{k}"] = tour.get(k)
    if tour.get("bewertung"):
        SS[f"{prefix}_bewertung"] = tour["bewertung"] - 1


def _geodaten_aktualisieren(prefix: str) -> None:
    """Nach dem Übernehmen einer Position Name, Region und Höhe vorschlagen (einmal je Position)."""
    pos = SS.get(f"{prefix}_pos")
    if not pos or SS.get(f"{prefix}_geo_fuer") == pos:
        return
    with st.spinner("Suche Gipfelnamen und Höhe …"):
        info = geocoding.ort_bestimmen(*pos)
    SS[f"{prefix}_geo"] = info
    SS[f"{prefix}_geo_fuer"] = pos

    # Nur Felder überschreiben, die leer sind oder zuvor automatisch gefüllt wurden.
    v = info.vorschlag
    if v and SS.get(f"{prefix}_name", "") in ("", SS.get(f"{prefix}_name_auto")):
        SS[f"{prefix}_name"] = SS[f"{prefix}_name_auto"] = v.name
    if info.region and SS.get(f"{prefix}_region", "") in ("", SS.get(f"{prefix}_region_auto")):
        SS[f"{prefix}_region"] = SS[f"{prefix}_region_auto"] = info.region
    if v and v.hoehe_m is not None:
        hoehe, quelle = v.hoehe_m, "osm"
    elif info.gelaendehoehe_m is not None:
        hoehe, quelle = info.gelaendehoehe_m, "dem"
    else:
        hoehe, quelle = None, None
    alt_auto = SS.get(f"{prefix}_hoehe_auto", (None, None))[0]
    if SS.get(f"{prefix}_hoehe") in (None, alt_auto):
        SS[f"{prefix}_hoehe"] = hoehe
        SS[f"{prefix}_hoehe_auto"] = (hoehe, quelle)


def _name_uebernehmen(prefix: str, name: str, hoehe: int | None) -> None:
    SS[f"{prefix}_name"] = name
    if hoehe is not None:
        SS[f"{prefix}_hoehe"] = hoehe
        SS[f"{prefix}_hoehe_auto"] = (hoehe, "osm")


def _ort_vorschlaege(prefix: str) -> None:
    info = SS.get(f"{prefix}_geo")
    if not info:
        return
    for h in info.hinweise:
        st.caption(f":material/info: {h}")
    if info.kandidaten:
        st.caption("In der Nähe gefunden – antippen zum Übernehmen:")
        with st.container(horizontal=True):
            for i, k in enumerate(info.kandidaten[:5]):
                hoehe = f", {k.hoehe_m} m" if k.hoehe_m else ""
                st.button(f"{k.name} ({k.typ}{hoehe}, {k.abstand_m / 1000:.1f} km)".replace(".", ","),
                          key=f"{prefix}_kand_{i}", on_click=_name_uebernehmen,
                          args=(prefix, k.name, k.hoehe_m), type="tertiary")
    elif not info.hinweise:
        st.caption("Kein Gipfel oder keine Hütte in der Nähe gefunden – bitte den Namen selbst eintragen.")
    if info.ort and not info.vorschlag:
        st.caption(f"Nächster Ort: {info.ort}")


def _formular_felder(prefix: str) -> None:
    st.segmented_control("Tourenart", list(ARTEN), key=f"{prefix}_art", format_func=art_label,
                         width="stretch")
    st.text_input("Name der Tour, des Gipfels oder Ortes", key=f"{prefix}_name",
                  placeholder="wird nach dem Übernehmen der Position vorgeschlagen")
    _ort_vorschlaege(prefix)
    st.date_input("Datum", key=f"{prefix}_datum", format="DD.MM.YYYY", max_value=date.today())

    auto_hoehe, auto_quelle = SS.get(f"{prefix}_hoehe_auto", (None, None))
    st.number_input("Höhe (m)", key=f"{prefix}_hoehe", min_value=-450, max_value=8900, step=10,
                    value=None, placeholder="unbekannt")
    aktuell = SS.get(f"{prefix}_hoehe")
    if aktuell is not None:
        quelle = auto_quelle if aktuell == auto_hoehe and auto_quelle else "manuell"
        st.caption(f"Höhe {HOEHE_QUELLEN[quelle]}")

    with st.expander("Weitere Angaben", icon=":material/tune:"):
        st.caption("Alle Felder sind freiwillig.")
        c1, c2 = st.columns(2)
        c1.number_input("Dauer – Stunden", key=f"{prefix}_dauer_h", min_value=0, max_value=720, step=1,
                        value=None, placeholder="h")
        c2.number_input("Minuten", key=f"{prefix}_dauer_m", min_value=0, max_value=59, step=5,
                        value=None, placeholder="min")
        st.text_input("Bergpartner", key=f"{prefix}_partner", placeholder="Namen mit Komma trennen")
        st.text_input("Ausgangspunkt", key=f"{prefix}_ausgangspunkt")
        st.text_input("Tourenziel / erreichte Gipfel", key=f"{prefix}_ziel")
        c1, c2 = st.columns(2)
        c1.number_input("Höhenmeter Aufstieg", key=f"{prefix}_hm_auf", min_value=0, max_value=10000,
                        step=50, value=None, placeholder="–")
        c2.number_input("Höhenmeter Abstieg", key=f"{prefix}_hm_ab", min_value=0, max_value=10000,
                        step=50, value=None, placeholder="–")
        st.text_input("Schwierigkeit", key=f"{prefix}_schwierigkeit",
                      placeholder="z. B. T3, UIAA 4+, 6a, WS, PD …")
        st.text_input("Wetter und Bedingungen", key=f"{prefix}_wetter")
        st.text_input("Region", key=f"{prefix}_region", help="Wird automatisch ermittelt und für den Kartenfilter genutzt.")
        st.text_area("Tourenbericht / persönlicher Kommentar", key=f"{prefix}_bericht", height=140)
        st.caption("Persönliche Bewertung")
        st.feedback("stars", key=f"{prefix}_bewertung")


def _formular_daten(prefix: str) -> dict:
    h, m = SS.get(f"{prefix}_dauer_h"), SS.get(f"{prefix}_dauer_m")
    dauer = None if h is None and m is None else (h or 0) * 60 + (m or 0)
    hoehe = SS.get(f"{prefix}_hoehe")
    auto_hoehe, auto_quelle = SS.get(f"{prefix}_hoehe_auto", (None, None))
    pos = SS.get(f"{prefix}_pos") or (None, None)
    bewertung = SS.get(f"{prefix}_bewertung")
    return bereinigen({
        "art": SS.get(f"{prefix}_art"),
        "name": SS.get(f"{prefix}_name"),
        "datum": SS.get(f"{prefix}_datum"),
        "lat": pos[0], "lon": pos[1],
        "hoehe_m": hoehe,
        "hoehe_quelle": None if hoehe is None else (auto_quelle if hoehe == auto_hoehe and auto_quelle else "manuell"),
        "region": SS.get(f"{prefix}_region"),
        "dauer_min": dauer or None,
        "partner": ", ".join(partner_liste(SS.get(f"{prefix}_partner"))),
        **{k: SS.get(f"{prefix}_{k}") for k in ("ausgangspunkt", "ziel", "hm_auf", "hm_ab", "schwierigkeit",
                                                  "wetter", "bericht")},
        "bewertung": None if bewertung is None else bewertung + 1,
    })


def _fotos_hochladen(sp, tour_id: str, dateien, beschriftungen: dict[int, str]) -> tuple[list[dict], list[str]]:
    gespeichert, fehler = [], []
    if not dateien:
        return gespeichert, fehler
    balken = st.progress(0.0, text="Fotos werden gespeichert …")
    for i, datei in enumerate(dateien):
        balken.progress(i / len(dateien), text=f"Foto {i + 1} von {len(dateien)}: {datei.name}")
        try:
            foto = aufbereiten(datei.getvalue(), datei.name)
            gespeichert.append(sp.add_photo(tour_id, foto, beschriftungen.get(i)))
        except (FotoFehler, SpeicherFehler) as exc:
            fehler.append(str(exc))
    balken.empty()
    return gespeichert, fehler


def _foto_auswahl(prefix: str, token: str):
    dateien = st.file_uploader(
        "Fotos hinzufügen", type=ERLAUBTE_ENDUNGEN, accept_multiple_files=True,
        key=f"{prefix}_fotos_{token}", max_upload_size=MAX_UPLOAD_MB,
        help=f"JPEG, PNG oder WebP, je Foto höchstens {MAX_UPLOAD_MB} MB. Mehrere Fotos auf einmal auswählen ist möglich. "
             "Ortsangaben (GPS) in den Fotos werden beim Speichern entfernt.",
    ) or []
    beschriftungen, titel = {}, None
    if dateien:
        with st.container(horizontal=True):
            for i, d in enumerate(dateien):
                with st.container(width=170):
                    st.image(d, width=160, alt=d.name)
                    beschriftungen[i] = st.text_input("Bildunterschrift", key=f"{prefix}_cap_{token}_{i}",
                                                      label_visibility="collapsed", placeholder="Bildunterschrift")
        if len(dateien) > 1:
            titel = st.selectbox("Titelbild", range(len(dateien)), format_func=lambda i: dateien[i].name,
                                 key=f"{prefix}_titel_{token}")
        else:
            titel = 0
    return dateien, beschriftungen, titel


def neue_tour_formular(sp) -> None:
    prefix = "nt"
    SS.setdefault(f"{prefix}_token", neue_id())
    SS.setdefault(f"{prefix}_datum", date.today())
    token = SS[f"{prefix}_token"]

    with st.container(border=True):
        st.subheader("1 · Position", anchor=False)
        positions_auswahl(prefix)
        pos = SS.get(f"{prefix}_pos")
        if pos:
            st.success(f"Position übernommen: {pos[0]:.5f}, {pos[1]:.5f}. Zum Korrigieren die Karte neu "
                       "ausrichten und erneut übernehmen.", icon=":material/check:")

    _geodaten_aktualisieren(prefix)

    with st.container(border=True):
        st.subheader("2 · Angaben", anchor=False)
        _formular_felder(prefix)

    with st.container(border=True):
        st.subheader("3 · Fotos", anchor=False)
        dateien, beschriftungen, titel = _foto_auswahl(prefix, token)

    daten = _formular_daten(prefix)
    if not daten.get("name") and daten.get("art"):
        info = SS.get(f"{prefix}_geo")
        daten["name"] = ersatz_name(daten["art"], daten.get("datum"), getattr(info, "ort", None))
        st.caption(f"Ohne Namen wird die Tour als „{daten['name']}“ gespeichert.")
    daten["id"] = token
    fehler = pruefen(daten)
    doppelt = moegliche_duplikate(daten, touren(sp)) if not fehler else []
    trotzdem = True
    if doppelt:
        st.warning("Am selben Tag gibt es schon eine ähnliche Tour: "
                   + ", ".join(f"„{t['name']}“" for t in doppelt), icon=":material/content_copy:")
        trotzdem = st.checkbox("Trotzdem als eigene Tour speichern", key=f"{prefix}_doppelt_ok_{token}")

    if st.button("Tour speichern", type="primary", icon=":material/save:", width="stretch",
                 key=f"{prefix}_speichern", disabled=not trotzdem):
        if fehler:
            for f in fehler:
                st.error(f)
            return
        try:
            with st.spinner("Tour wird gespeichert …"):
                sp.create_tour(daten)
        except SchonVorhanden:
            pass  # bereits gespeichert (z. B. doppelt getippt) – einfach weitermachen
        except SpeicherFehler as exc:
            st.error(f"{exc} Deine Eingaben bleiben erhalten.")
            return
        gespeichert, foto_fehler = _fotos_hochladen(sp, token, dateien, beschriftungen)
        if gespeichert and titel is not None and titel < len(dateien):
            # Titelbild = gewähltes Foto, falls es gespeichert wurde, sonst das erste gespeicherte
            namen = [d.name for d in dateien]
            gewaehlt = next((g for g in gespeichert if g["dateiname"] == namen[titel]), gespeichert[0])
            sp.update_tour(token, {"titelbild_id": gewaehlt["id"]})
        neu_laden()
        text = f"„{daten['name']}“ wurde gespeichert"
        text += f" – mit {len(gespeichert)} Foto{'s' if len(gespeichert) != 1 else ''}." if gespeichert else "."
        meldung(text)
        if foto_fehler:
            SS["mm_foto_fehler"] = foto_fehler
        for k in [k for k in SS.keys() if isinstance(k, str) and k.startswith(f"{prefix}_")]:
            del SS[k]
        SS["mm_zuletzt_gespeichert"] = token
        st.rerun()


def bearbeiten_formular(sp, tour: dict) -> None:
    prefix = "bt"
    _formular_vorbelegen(prefix, tour)

    with st.expander("Position ändern", icon=":material/edit_location_alt:"):
        positions_auswahl(prefix, start=(tour["lat"], tour["lon"]))
    pos = SS.get(f"{prefix}_pos")
    if pos and pos != (tour["lat"], tour["lon"]):
        st.info(f"Neue Position: {pos[0]:.5f}, {pos[1]:.5f} (wird beim Speichern übernommen).")
    _geodaten_aktualisieren(prefix)
    _formular_felder(prefix)

    daten = _formular_daten(prefix)
    daten["id"] = tour["id"]
    if not daten.get("name"):
        daten["name"] = tour["name"]
    fehler = pruefen(daten)
    c1, c2 = st.columns(2)
    if c1.button("Änderungen speichern", type="primary", icon=":material/save:", width="stretch", key=f"{prefix}_speichern"):
        if fehler:
            for f in fehler:
                st.error(f)
        else:
            try:
                sp.update_tour(tour["id"], daten)
            except SpeicherFehler as exc:
                st.error(f"{exc} Deine Eingaben bleiben erhalten.")
            else:
                neu_laden()
                SS.pop(f"{prefix}_geladen", None)
                SS["mm_bearbeiten"] = False
                meldung("Änderungen gespeichert.")
                st.rerun()
    if c2.button("Abbrechen", width="stretch", key=f"{prefix}_abbrechen"):
        SS.pop(f"{prefix}_geladen", None)
        SS["mm_bearbeiten"] = False
        st.rerun()


# --------------------------------------------------------------------------------------------
# Tourenansicht
# --------------------------------------------------------------------------------------------

@st.dialog("Foto", width="large")
def foto_dialog(sp, fotos: list[dict]) -> None:
    schluessel = "mm_foto_index"
    i = SS.get(schluessel, 0) % len(fotos)
    foto = fotos[i]
    quelle = sp.photo_sources([foto], vorschau=False).get(foto["id"])
    if quelle is None:
        st.warning("Das Foto konnte nicht geladen werden.")
    else:
        st.image(quelle, caption=foto.get("beschriftung"), width="stretch",
                 alt=foto.get("beschriftung") or foto.get("dateiname") or "Foto")
    if len(fotos) > 1:
        c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="center")
        if c1.button("Zurück", icon=":material/chevron_left:", width="stretch"):
            SS[schluessel] = i - 1
            st.rerun(scope="fragment")
        c2.caption(f"{i + 1} / {len(fotos)}", text_alignment="center")
        if c3.button("Weiter", icon=":material/chevron_right:", icon_position="right", width="stretch"):
            SS[schluessel] = i + 1
            st.rerun(scope="fragment")


@st.dialog("Tour löschen?")
def loeschen_dialog(sp, tour: dict, anzahl_fotos: int) -> None:
    st.write(f"„{tour['name']}“ vom {datum_text(tour['datum'])}"
             + (f" und {anzahl_fotos} Foto{'s' if anzahl_fotos != 1 else ''}" if anzahl_fotos else "")
             + " werden endgültig gelöscht. Das lässt sich nicht rückgängig machen.")
    c1, c2 = st.columns(2)
    if c1.button("Endgültig löschen", type="primary", icon=":material/delete:", width="stretch"):
        try:
            sp.delete_tour(tour["id"])
        except SpeicherFehler as exc:
            st.error(str(exc))
            return
        neu_laden()
        SS.pop("mm_tour_id", None)
        SS.pop("mm_karte_auswahl", None)
        meldung(f"„{tour['name']}“ wurde gelöscht.")
        st.switch_page("app_pages/meine_touren.py")
    if c2.button("Abbrechen", width="stretch"):
        st.rerun()


def galerie(sp, fotos: list[dict], key: str) -> None:
    if not fotos:
        st.caption("Noch keine Fotos.")
        return
    quellen = sp.photo_sources(fotos, vorschau=True)
    with st.container(horizontal=True):
        for i, f in enumerate(fotos):
            with st.container(width=158, gap="xsmall"):
                if f["id"] in quellen:
                    st.image(quellen[f["id"]], width=150, alt=f.get("beschriftung") or f.get("dateiname") or "Foto")
                else:
                    st.caption("Bild nicht verfügbar")
                if f.get("beschriftung"):
                    st.caption(f["beschriftung"])
                if st.button("Vergrößern", key=f"{key}_gross_{f['id']}", icon=":material/zoom_in:",
                             type="tertiary"):
                    SS["mm_foto_index"] = i
                    foto_dialog(sp, fotos)


def _kennzahl_zeile(tour: dict) -> None:
    werte = [
        ("Höhe", hoehe_text(tour)),
        ("Dauer", dauer_text(tour.get("dauer_min"))),
        ("Aufstieg", f"{tour['hm_auf']:,} Hm".replace(",", ".") if tour.get("hm_auf") is not None else None),
        ("Abstieg", f"{tour['hm_ab']:,} Hm".replace(",", ".") if tour.get("hm_ab") is not None else None),
    ]
    werte = [(k, v) for k, v in werte if v]
    if werte:
        with st.container(horizontal=True):
            for k, v in werte:
                st.metric(k, v, border=True, width=150)


def tour_details(sp, tour: dict, key: str = "td", kompakt: bool = False) -> None:
    fotos = fotos_von(sp, tour["id"])
    herz = " ❤️" if tour.get("favorit") else ""
    st.subheader(f"{ARTEN[tour['art']]['emoji']} {tour['name']}{herz}", anchor=False)
    teile = [art_label(tour["art"], mit_emoji=False), datum_text(tour["datum"])]
    if tour.get("region"):
        teile.append(tour["region"])
    st.caption(" · ".join(teile))
    _kennzahl_zeile(tour)

    zeilen = [
        ("Bergpartner", ", ".join(partner_liste(tour.get("partner"))) or None),
        ("Ausgangspunkt", tour.get("ausgangspunkt")),
        ("Tourenziel", tour.get("ziel")),
        ("Schwierigkeit", tour.get("schwierigkeit")),
        ("Wetter und Bedingungen", tour.get("wetter")),
        ("Bewertung", "★" * tour["bewertung"] + "☆" * (5 - tour["bewertung"]) if tour.get("bewertung") else None),
    ]
    text = "  \n".join(f"**{k}:** {v}" for k, v in zeilen if v)
    if text:
        st.markdown(text)
    if tour.get("bericht"):
        if kompakt and len(tour["bericht"]) > 300:
            st.markdown(tour["bericht"][:300].rsplit(" ", 1)[0] + " …")
        else:
            st.markdown(tour["bericht"])

    galerie(sp, fotos, key)

    st.caption(f"Position {tour['lat']:.5f}, {tour['lon']:.5f} · "
               f"[auf OpenStreetMap ansehen](https://www.openstreetmap.org/?mlat={tour['lat']:.5f}"
               f"&mlon={tour['lon']:.5f}#map=15/{tour['lat']:.5f}/{tour['lon']:.5f})")
    with st.container(horizontal=True):
        favorit = bool(tour.get("favorit"))
        if st.button("Favorit" if favorit else "Als Favorit merken", key=f"{key}_favorit",
                     icon=":material/favorite:" if favorit else ":material/favorite_border:",
                     help="Favorit wieder entfernen" if favorit else "Besonders schöne Tour markieren"):
            sp.update_tour(tour["id"], {"favorit": not favorit})
            neu_laden()
            st.rerun()
        if kompakt and st.button("Ganze Tour öffnen", key=f"{key}_oeffnen", icon=":material/open_in_full:",
                                 type="primary"):
            tour_oeffnen(tour["id"])
        if st.button("Bearbeiten", key=f"{key}_bearbeiten", icon=":material/edit:"):
            tour_oeffnen(tour["id"], bearbeiten=True)
        if st.button("Löschen", key=f"{key}_loeschen", icon=":material/delete:"):
            loeschen_dialog(sp, tour, len(fotos))


def fotos_verwalten(sp, tour: dict) -> None:
    """Fotos ergänzen, beschriften, Titelbild wählen und löschen."""
    fotos = fotos_von(sp, tour["id"])
    if fotos:
        quellen = sp.photo_sources(fotos, vorschau=True)
        for f in fotos:
            with st.container(border=True, horizontal=True, vertical_alignment="center"):
                if f["id"] in quellen:
                    st.image(quellen[f["id"]], width=110, alt=f.get("dateiname") or "Foto")
                with st.container():
                    neu = st.text_input("Bildunterschrift", value=f.get("beschriftung") or "",
                                        key=f"fv_cap_{f['id']}")
                    with st.container(horizontal=True):
                        if neu != (f.get("beschriftung") or "") and st.button(
                                "Unterschrift speichern", key=f"fv_save_{f['id']}", icon=":material/save:"):
                            sp.update_photo(f["id"], neu)
                            neu_laden()
                            st.rerun()
                        if tour.get("titelbild_id") == f["id"] or (not tour.get("titelbild_id") and f is fotos[0]):
                            st.badge("Titelbild", icon=":material/star:", color="green")
                        elif st.button("Als Titelbild", key=f"fv_titel_{f['id']}", icon=":material/star:"):
                            sp.update_tour(tour["id"], {"titelbild_id": f["id"]})
                            neu_laden()
                            st.rerun()
                        with st.popover("Löschen", icon=":material/delete:"):
                            st.write("Dieses Foto endgültig löschen?")
                            if st.button("Ja, löschen", key=f"fv_del_{f['id']}", type="primary"):
                                try:
                                    sp.delete_photo(f)
                                except SpeicherFehler as exc:
                                    st.error(str(exc))
                                else:
                                    neu_laden()
                                    st.rerun()
    else:
        st.caption("Noch keine Fotos.")

    SS.setdefault("fv_token", neue_id())
    dateien, beschriftungen, _ = _foto_auswahl("fv", SS["fv_token"])
    if dateien and st.button("Fotos speichern", type="primary", icon=":material/upload:", key="fv_hochladen"):
        gespeichert, fehler = _fotos_hochladen(sp, tour["id"], dateien, beschriftungen)
        if gespeichert and not tour.get("titelbild_id") and not fotos:
            sp.update_tour(tour["id"], {"titelbild_id": gespeichert[0]["id"]})
        neu_laden()
        SS["fv_token"] = neue_id()  # Auswahl leeren, damit nichts doppelt hochgeladen wird
        if fehler:
            SS["mm_foto_fehler"] = fehler
        meldung(f"{len(gespeichert)} Foto{'s' if len(gespeichert) != 1 else ''} gespeichert.")
        st.rerun()


def foto_fehler_zeigen() -> None:
    for f in SS.pop("mm_foto_fehler", []):
        st.warning(f, icon=":material/image_not_supported:")
