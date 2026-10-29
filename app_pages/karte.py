from datetime import date

import streamlit as st
from streamlit_folium import st_folium

from src import config, map_utils, statistics, ui
from src.models import ARTEN, als_datum, art_label, datum_text

sp = config.speicher()
alle = ui.touren(sp)

st.title("Meine Tourenkarte", anchor=False)
ui.meldung_zeigen()

if not alle:
    st.info("Noch keine Touren gespeichert. Leg los mit deiner ersten Tour!", icon=":material/hiking:")
    if st.button("Neue Tour erfassen", type="primary", icon=":material/add_location_alt:", width="stretch"):
        st.switch_page(ui.SEITE_NEU)
    st.stop()

daten = [als_datum(t.get("datum")) for t in alle if t.get("datum")]
erstes = min(daten) if daten else date.today()
regionen_alle = sorted({t.get("region") or "Ohne Region" for t in alle})

with st.expander("Filter", icon=":material/filter_alt:"):
    arten = st.pills("Tourenarten", list(ARTEN), selection_mode="multi", default=list(ARTEN),
                     format_func=art_label, key="ka_arten")
    zeitraum = st.date_input("Zeitraum", value=(erstes, date.today()), min_value=erstes,
                             max_value=date.today(), format="DD.MM.YYYY", key="ka_zeitraum")
    regionen = st.multiselect("Regionen", regionen_alle, key="ka_regionen", placeholder="Alle Regionen")
    nur_favoriten = st.toggle("Nur Favoriten", key="ka_favoriten")

von, bis = (zeitraum + (None, None))[:2] if isinstance(zeitraum, tuple) else (None, None)
gefiltert = statistics.filtern(alle, arten=arten, von=von, bis=bis, regionen=regionen,
                               nur_favoriten=nur_favoriten)

anzahl = len(gefiltert)
st.caption(f"{anzahl} von {len(alle)} Touren angezeigt · Symbol antippen für Details"
           if anzahl != len(alle) else f"{anzahl} Touren · Symbol antippen für Details")

karte = map_utils.tourenkarte(gefiltert)
ergebnis = st_folium(karte, key="ka_karte", height=470, use_container_width=True,
                     returned_objects=["last_object_clicked"]) or {}
st.html(map_utils.legende_html())

klick = ergebnis.get("last_object_clicked")
if klick:
    treffer = map_utils.touren_am_punkt(gefiltert, klick["lat"], klick["lng"])
    if treffer:
        with st.container(border=True):
            if len(treffer) > 1:
                st.caption(f"{len(treffer)} Touren an dieser Stelle")
                wahl = st.selectbox("Tour wählen", range(len(treffer)), key=f"ka_wahl_{klick['lat']}_{klick['lng']}",
                                    format_func=lambda i: f"{datum_text(treffer[i]['datum'])} – {treffer[i]['name']}")
                tour = treffer[wahl]
            else:
                tour = treffer[0]
            ui.tour_details(sp, tour, key="ka", kompakt=True)

if st.button("Neue Tour erfassen", type="primary", icon=":material/add_location_alt:", width="stretch",
             key="ka_neu"):
    st.switch_page(ui.SEITE_NEU)
