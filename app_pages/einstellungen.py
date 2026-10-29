import streamlit as st

from src import backup, config, ui
from src.database import als_json

sp = config.speicher()
SS = st.session_state

st.title("Einstellungen und Datensicherung", anchor=False)
ui.meldung_zeigen()

# Konto -------------------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Konto", anchor=False)
    st.markdown(f"**Speicherort:** {config.modus_text()}")
    if config.supabase_zugang():
        st.markdown(f"**Angemeldet als:** {SS['mm_user']['email']}")
        if st.button("Abmelden", icon=":material/logout:"):
            config.abmelden()
            st.rerun()
    else:
        st.caption("Im lokalen Testmodus gibt es keine Anmeldung. Die Daten liegen auf diesem Computer im Ordner "
                   "„daten“. Für die Nutzung am Handy die Cloud-Variante einrichten (siehe README).")

# Export ------------------------------------------------------------------------------------
touren = ui.touren(sp)
fotos = ui.alle_fotos(sp)
with st.container(border=True):
    st.subheader("Daten exportieren", anchor=False)
    st.caption(f"{len(touren)} Touren und {len(fotos)} Fotos.")
    with st.container(horizontal=True):
        st.download_button("Touren als CSV (Excel)", backup.touren_csv(touren, fotos),
                           file_name=backup.dateiname_heute("csv").replace("sicherung", "touren"),
                           mime="text/csv", icon=":material/table:", on_click="ignore")
        st.download_button("Touren als JSON", als_json(backup.sicherung_json(touren, fotos)).encode("utf-8"),
                           file_name=backup.dateiname_heute("json"), mime="application/json",
                           icon=":material/data_object:", on_click="ignore")

    st.markdown("**Vollständige Sicherung mit allen Fotos**")
    st.caption("Eine ZIP-Datei mit allen Touren, Koordinaten, Fotos und deren Zuordnung. "
               "Am besten regelmäßig erstellen und z. B. auf dem Computer oder in einer Cloud ablegen.")
    if st.button("Sicherung erstellen", icon=":material/backup:"):
        balken = st.progress(0.0, text="Fotos werden zusammengestellt …")
        daten, fehler = backup.sicherung_zip(sp, fortschritt=lambda x: balken.progress(x, text="Fotos werden zusammengestellt …"))
        balken.empty()
        SS["es_zip"] = daten
        if fehler:
            st.warning(f"{len(fehler)} Foto(s) konnten nicht geladen werden: {', '.join(fehler)}")
    if SS.get("es_zip"):
        st.download_button(f"Sicherung herunterladen ({len(SS['es_zip']) / 1_048_576:.1f} MB)", SS["es_zip"],
                           file_name=backup.dateiname_heute("zip"), mime="application/zip",
                           type="primary", icon=":material/download:", on_click="ignore")

# Wiederherstellen --------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Sicherung einspielen", anchor=False)
    st.caption("Eine ZIP-Sicherung (mit Fotos) oder JSON-Datei (ohne Fotos) aus dieser App auswählen. "
               "Touren, die schon vorhanden sind, werden übersprungen – nichts wird doppelt angelegt oder "
               "überschrieben. So lassen sich auch Testdaten vom Computer in die Cloud übertragen.")
    SS.setdefault("es_import_nr", 0)
    datei = st.file_uploader("Sicherungsdatei", type=["zip", "json"], key=f"es_import_{SS['es_import_nr']}",
                             max_upload_size=500)
    if datei:
        try:
            inhalt, zip_datei = backup.sicherung_lesen(datei.getvalue(), datei.name)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.info(f"Sicherung vom {inhalt.get('exportiert_am', '?')[:10]}: {len(inhalt.get('touren', []))} Touren, "
                    f"{len(inhalt.get('fotos', []))} Fotos.")
            if st.button("Jetzt einspielen", type="primary", icon=":material/restore:"):
                balken = st.progress(0.0, text="Touren werden eingespielt …")
                erg = backup.sicherung_einspielen(sp, inhalt, zip_datei,
                                                  fortschritt=lambda x: balken.progress(x, text="Touren werden eingespielt …"))
                balken.empty()
                ui.neu_laden()
                SS["es_import_nr"] += 1
                ui.meldung(f"{erg.touren_neu} Touren und {erg.fotos_neu} Fotos eingespielt, "
                           f"{erg.touren_vorhanden} waren schon vorhanden.")
                if erg.fehler:
                    SS["mm_foto_fehler"] = erg.fehler
                st.rerun()
    ui.foto_fehler_zeigen()

# Startbildschirm ---------------------------------------------------------------------------
with st.expander("App auf den Startbildschirm legen", icon=":material/install_mobile:"):
    st.markdown(
        "**iPhone / iPad (Safari):** App-Adresse öffnen → Teilen-Symbol (Quadrat mit Pfeil) → "
        "„Zum Home-Bildschirm“ → „Hinzufügen“.\n\n"
        "**Android (Chrome):** App-Adresse öffnen → Menü ⋮ → „Zum Startbildschirm hinzufügen“ "
        "bzw. „App installieren“.\n\n"
        "Die App braucht weiterhin Internet – es gibt keinen Offline-Modus."
    )

with st.expander("Über die Karten und Dienste", icon=":material/info:"):
    st.markdown(
        "- Karten: © OpenStreetMap-Mitwirkende, OpenTopoMap (CC-BY-SA), Luftbild basemap.at (CC BY 4.0)\n"
        "- Gipfelnamen: Photon (komoot) und Nominatim mit OpenStreetMap-Daten (ODbL)\n"
        "- Geländehöhe: Open-Meteo, Copernicus-Höhenmodell (90 m) – deshalb als „ca.“ gekennzeichnet\n"
        "- Fotos werden verkleinert (max. 2.400 px) gespeichert; GPS-Daten in den Fotos werden dabei entfernt."
    )
