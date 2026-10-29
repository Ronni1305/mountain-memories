"""Mountain Memories – Mein persönliches Tourenbuch.

Start:  streamlit run streamlit_app.py
"""
import logging

import streamlit as st

from src import config, pwa, ui
from src.database import AnmeldungAbgelaufen, SpeicherFehler

st.set_page_config(page_title="Mountain Memories", page_icon="assets/favicon.png", layout="centered")
st.logo("assets/logo_wide.png", icon_image="assets/app_icon.png", size="large")
pwa.einbinden()

zugang = config.supabase_zugang()

if not zugang and config.laeuft_in_streamlit_cloud():
    st.error(
        "Die Datenbank ist noch nicht eingerichtet. Bitte die Supabase-Zugangsdaten in den Secrets der App "
        "hinterlegen (siehe README, Abschnitt „Streamlit Community Cloud“). Ohne Datenbank würden Touren "
        "bei einem Neustart verloren gehen.",
        title="Noch nicht bereit",
    )
    st.stop()


def anmeldeseite():
    st.title("Mountain Memories", anchor=False)
    st.caption("Mein persönliches Tourenbuch")
    with st.form("anmeldung"):
        email = st.text_input("E-Mail-Adresse", autocomplete="email")
        passwort = st.text_input("Passwort", type="password", autocomplete="current-password")
        los = st.form_submit_button("Anmelden", type="primary", icon=":material/login:", width="stretch")
    if los:
        if not email or not passwort:
            st.warning("Bitte E-Mail-Adresse und Passwort eingeben.")
        else:
            with st.spinner("Anmeldung …"):
                fehler = config.anmelden(zugang, email, passwort)
            if fehler:
                st.error(fehler)
            else:
                st.rerun()


if zugang and not config.angemeldet():
    st.navigation([st.Page(anmeldeseite, title="Anmelden", icon=":material/login:")], position="hidden").run()
    st.stop()

seiten = [
    st.Page("app_pages/karte.py", title="Karte", icon=":material/map:", default=True),
    st.Page("app_pages/neue_tour.py", title="Neue Tour", icon=":material/add_location_alt:"),
    st.Page("app_pages/meine_touren.py", title="Meine Touren", icon=":material/list:"),
    st.Page("app_pages/statistik.py", title="Statistik", icon=":material/bar_chart:"),
    st.Page("app_pages/einstellungen.py", title="Einstellungen", icon=":material/settings:"),
    st.Page("app_pages/tour.py", title="Tour", icon=":material/landscape:", visibility="hidden"),
]
seite = st.navigation(seiten, position="top")

if not zugang:
    st.caption(":material/computer: Lokaler Testmodus – die Daten liegen nur auf diesem Computer im Ordner „daten“.")

try:
    seite.run()
except AnmeldungAbgelaufen as exc:
    config.abmelden()
    st.warning(str(exc))
    st.button("Zur Anmeldung", on_click=lambda: None)
except SpeicherFehler as exc:
    st.error(str(exc), icon=":material/cloud_off:")
    if st.button("Erneut versuchen", icon=":material/refresh:"):
        ui.neu_laden()
        st.rerun()
except Exception:  # noqa: BLE001 – nie einen technischen Fehlertext zeigen
    logging.getLogger("mountain_memories").exception("Unerwarteter Fehler")
    st.error("Hier ist leider etwas schiefgelaufen. Bitte die Seite neu laden. Deine gespeicherten Touren "
             "sind davon nicht betroffen.", icon=":material/error:")
    if st.button("Neu laden", icon=":material/refresh:"):
        ui.neu_laden()
        st.rerun()
