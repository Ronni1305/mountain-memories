import streamlit as st

from src import config, statistics, ui
from src.models import ARTEN, art_label, datum_text, hoehe_text, partner_liste

SEITENGROESSE = 20

sp = config.speicher()
alle = ui.touren(sp)

st.title("Meine Touren", anchor=False)
ui.meldung_zeigen()

if not alle:
    st.info("Noch keine Touren gespeichert.", icon=":material/hiking:")
    if st.button("Neue Tour erfassen", type="primary", icon=":material/add_location_alt:", width="stretch"):
        st.switch_page(ui.SEITE_NEU)
    st.stop()

suche = st.text_input("Suchen", placeholder="Gipfel, Ort, Tourenname oder Bergpartner",
                      key="mt_suche", icon=":material/search:")
with st.container(horizontal=True, vertical_alignment="bottom"):
    arten = st.pills("Tourenarten", list(ARTEN), selection_mode="multi", default=list(ARTEN),
                     format_func=art_label, key="mt_arten")
    sortierung = st.selectbox("Sortieren", list(statistics.SORTIERUNGEN), key="mt_sort", width=240)

jahre = sorted({t["datum"][:4] for t in alle if t.get("datum")}, reverse=True)
with st.container(horizontal=True, vertical_alignment="bottom"):
    jahr = st.selectbox("Jahr", ["Alle Jahre"] + jahre, key="mt_jahr", width=180)
    nur_favoriten = st.toggle("Nur Favoriten", key="mt_favoriten")

liste = statistics.SORTIERUNGEN[sortierung](statistics.filtern(
    alle, arten=arten, suche=suche, jahr=None if jahr == "Alle Jahre" else jahr, nur_favoriten=nur_favoriten))
st.caption(f"{len(liste)} von {len(alle)} Touren")

anzeigen = st.session_state.setdefault("mt_anzahl", SEITENGROESSE)
sichtbar = liste[:anzeigen]

fotos = ui.alle_fotos(sp)
fotos_je_tour = {}
for f in fotos:
    fotos_je_tour.setdefault(f["tour_id"], []).append(f)
titelbilder = {t["id"]: ui.titelbild(t, fotos_je_tour.get(t["id"], [])) for t in sichtbar}
quellen = sp.photo_sources([f for f in titelbilder.values() if f], vorschau=True)

for t in sichtbar:
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        bild = titelbilder.get(t["id"])
        if bild and bild["id"] in quellen:
            st.image(quellen[bild["id"]], width=96, alt=f"Titelbild {t['name']}")
        else:
            st.markdown(f"## {ARTEN[t['art']]['emoji']}", width=96, text_alignment="center")
        with st.container(gap="xxsmall"):
            st.markdown(f"**{t['name']}**" + (" ❤️" if t.get("favorit") else ""))
            teile = [datum_text(t["datum"]), art_label(t["art"], mit_emoji=False)]
            if hoehe_text(t):
                teile.append(hoehe_text(t))
            st.caption(" · ".join(teile))
            partner = partner_liste(t.get("partner"))
            if partner:
                st.caption(f":material/group: {', '.join(partner)}")
        if st.button("Öffnen", key=f"mt_oeffnen_{t['id']}", icon=":material/chevron_right:"):
            ui.tour_oeffnen(t["id"])

if len(liste) > anzeigen:
    if st.button(f"Weitere Touren anzeigen ({len(liste) - anzeigen})", width="stretch"):
        st.session_state["mt_anzahl"] = anzeigen + SEITENGROESSE
        st.rerun()
