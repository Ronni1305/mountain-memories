import altair as alt
import pandas as pd
import streamlit as st

from src import config, statistics, ui
from src.models import ARTEN, datum_text, dauer_text

sp = config.speicher()
alle = ui.touren(sp)

st.title("Meine Bergstatistik", anchor=False)

if not alle:
    st.info("Sobald Touren gespeichert sind, erscheint hier die Statistik.", icon=":material/bar_chart:")
    st.stop()

jahre = sorted({t["datum"][:4] for t in alle if t.get("datum")}, reverse=True)
jahr = st.segmented_control("Zeitraum", ["Alle Jahre"] + jahre[:6], default="Alle Jahre", key="st_jahr")
auswahl = alle if jahr in (None, "Alle Jahre") else [t for t in alle if (t.get("datum") or "").startswith(jahr)]
k = statistics.kennzahlen(auswahl)


def zahl(n) -> str:
    return f"{n:,}".replace(",", ".")


with st.container(horizontal=True):
    st.metric("Touren gesamt", zahl(k["gesamt"]), border=True, width=160)
    for art, info in ARTEN.items():
        st.metric(f"{info['emoji']} {info['label']}", zahl(k["nach_art"][art]), border=True, width=160)

with st.container(horizontal=True):
    st.metric("Verschiedene Gipfel / Orte", zahl(k["orte_verschieden"]), border=True, width=160)
    if k["hm_summe"] is not None:
        st.metric("Höhenmeter Aufstieg", f"{zahl(k['hm_summe'])} Hm", border=True, width=160,
                  help=f"Summe aus {k['hm_anzahl']} von {k['gesamt']} Touren, bei denen Höhenmeter eingetragen sind.")
    if k["dauer_summe_min"] is not None:
        st.metric("Unterwegs", dauer_text(k["dauer_summe_min"]), border=True, width=160,
                  help=f"Summe aus {k['dauer_anzahl']} von {k['gesamt']} Touren mit eingetragener Dauer.")
    if k["hoechste"]:
        h = k["hoechste"]
        st.metric("Höchster Punkt", f"{zahl(h['hoehe_m'])} m", border=True, width=160,
                  help=f"{h['name']} am {datum_text(h['datum'])}")

if k["hm_summe"] is not None and k["hm_anzahl"] < k["gesamt"]:
    st.caption(f"Höhenmeter und Dauer zählen nur Touren, bei denen sie eingetragen sind "
               f"({k['hm_anzahl']} von {k['gesamt']} mit Höhenmetern).")

if jahr in (None, "Alle Jahre") and k["pro_jahr"]:
    st.subheader("Touren pro Jahr", anchor=False)
    df = pd.DataFrame(k["pro_jahr"])
    farben = alt.Scale(domain=[i["label"] for i in ARTEN.values()], range=[i["farbe"] for i in ARTEN.values()])
    diagramm = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("Jahr:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("sum(Touren):Q", title="Touren", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Tourenart:N", scale=farben, legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["Jahr", "Tourenart", "Touren"],
        )
    )
    st.altair_chart(diagramm, alt="Balkendiagramm: Anzahl der Touren pro Jahr, nach Tourenart gestapelt")


def rangliste(titel: str, eintraege: list[tuple[str, int]], spalte: str) -> None:
    if not eintraege:
        return
    st.subheader(titel, anchor=False)
    st.dataframe(pd.DataFrame(eintraege, columns=[spalte, "Anzahl"]), hide_index=True,
                 alt=titel, column_config={"Anzahl": st.column_config.NumberColumn(width="small")})


rangliste("Am häufigsten besucht", [e for e in k["top_orte"] if e[1] > 1] or k["top_orte"][:5], "Gipfel / Ort")
rangliste("Regionen", k["top_regionen"], "Region")
rangliste("Bergpartner", k["top_partner"], "Name")
