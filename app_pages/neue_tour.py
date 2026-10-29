import streamlit as st

from src import config, ui

sp = config.speicher()
ui.touren(sp)  # für den Doppelt-Check und den Kartenausschnitt

st.title("Neue Tour erfassen", anchor=False)
ui.meldung_zeigen()
ui.foto_fehler_zeigen()

zuletzt = st.session_state.get("mm_zuletzt_gespeichert")
if zuletzt:
    with st.container(horizontal=True):
        if st.button("Gespeicherte Tour ansehen", icon=":material/visibility:"):
            st.session_state.pop("mm_zuletzt_gespeichert", None)
            ui.tour_oeffnen(zuletzt)
        if st.button("Zur Karte", icon=":material/map:"):
            st.session_state.pop("mm_zuletzt_gespeichert", None)
            st.switch_page("app_pages/karte.py")

ui.neue_tour_formular(sp)
