import streamlit as st

from src import config, ui

sp = config.speicher()
SS = st.session_state

tour_id = SS.get("mm_tour_id") or st.query_params.get("tour")
tour = next((t for t in ui.touren(sp) if t["id"] == tour_id), None) if tour_id else None

if not tour:
    st.info("Diese Tour gibt es nicht (mehr).", icon=":material/search_off:")
    if st.button("Zu meinen Touren", icon=":material/list:"):
        st.switch_page("app_pages/meine_touren.py")
    st.stop()

st.query_params["tour"] = tour["id"]  # Seite lässt sich so auch neu laden
if st.button("Zurück", icon=":material/arrow_back:", type="tertiary"):
    st.query_params.clear()
    st.switch_page("app_pages/meine_touren.py")
ui.meldung_zeigen()
ui.foto_fehler_zeigen()

if SS.get("mm_bearbeiten"):
    st.title("Tour bearbeiten", anchor=False)
    ansicht = st.segmented_control("Bereich", ["Angaben", "Fotos"], default="Angaben", key="tb_bereich",
                                   label_visibility="collapsed", width="stretch")
    if ansicht == "Fotos":
        ui.fotos_verwalten(sp, tour)
        if st.button("Fertig", type="primary", icon=":material/check:", width="stretch"):
            SS["mm_bearbeiten"] = False
            SS.pop("bt_geladen", None)
            st.rerun()
    else:
        ui.bearbeiten_formular(sp, tour)
else:
    ui.tour_details(sp, tour, key="tp")
