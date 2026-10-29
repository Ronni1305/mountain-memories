"""Filter und persönliche Bergstatistik.

Fehlende Angaben zählen nie als 0: Summen und Durchschnitte werden nur über Touren gebildet,
bei denen der Wert eingetragen ist, und die Anzahl dieser Touren wird mitgeliefert.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from .models import ARTEN, als_datum, name_schluessel, partner_liste


def filtern(touren: list[dict], arten=None, von: date | None = None, bis: date | None = None,
            regionen=None, suche: str | None = None) -> list[dict]:
    such = (suche or "").strip().casefold()
    ergebnis = []
    for t in touren:
        if arten is not None and t.get("art") not in arten:
            continue
        d = als_datum(t.get("datum"))
        if von and (not d or d < von):
            continue
        if bis and (not d or d > bis):
            continue
        if regionen and (t.get("region") or "Ohne Region") not in regionen:
            continue
        if such:
            text = " ".join(str(t.get(k) or "") for k in ("name", "ziel", "region", "ausgangspunkt", "partner"))
            if such not in text.casefold():
                continue
        ergebnis.append(t)
    return ergebnis


SORTIERUNGEN = {
    "Datum – neueste zuerst": lambda ts: sorted(ts, key=lambda t: (t.get("datum") or "", t.get("created_at") or ""), reverse=True),
    "Datum – älteste zuerst": lambda ts: sorted(ts, key=lambda t: (t.get("datum") or "9999", t.get("created_at") or "")),
    "Name A–Z": lambda ts: sorted(ts, key=lambda t: name_schluessel(t.get("name"))),
    "Höhe – höchste zuerst": lambda ts: sorted(ts, key=lambda t: (t.get("hoehe_m") is None, -(t.get("hoehe_m") or 0))),
}


def kennzahlen(touren: list[dict]) -> dict:
    nach_art = Counter(t.get("art") for t in touren)
    jahre = Counter()
    for t in touren:
        d = als_datum(t.get("datum"))
        if d:
            jahre[(d.year, t.get("art"))] += 1

    hm = [t["hm_auf"] for t in touren if t.get("hm_auf") is not None]
    dauer = [t["dauer_min"] for t in touren if t.get("dauer_min") is not None]
    mit_hoehe = [t for t in touren if t.get("hoehe_m") is not None]

    namen = Counter()
    anzeige = {}
    for t in touren:
        s = name_schluessel(t.get("name"))
        if s:
            namen[s] += 1
            anzeige.setdefault(s, t.get("name").strip())
    regionen = Counter(t["region"] for t in touren if t.get("region"))
    partner = Counter(p for t in touren for p in partner_liste(t.get("partner")))

    return {
        "gesamt": len(touren),
        "nach_art": {art: nach_art.get(art, 0) for art in ARTEN},
        "pro_jahr": [
            {"Jahr": str(j), "Tourenart": ARTEN.get(a, {}).get("label", "Unbekannt"), "Touren": n}
            for (j, a), n in sorted(jahre.items(), key=lambda x: (x[0][0], str(x[0][1])))
        ],
        "hm_summe": sum(hm) if hm else None,
        "hm_anzahl": len(hm),
        "dauer_summe_min": sum(dauer) if dauer else None,
        "dauer_anzahl": len(dauer),
        "hoechste": max(mit_hoehe, key=lambda t: t["hoehe_m"]) if mit_hoehe else None,
        "orte_verschieden": len(namen),
        "top_orte": [(anzeige[s], n) for s, n in namen.most_common(10)],
        "top_regionen": regionen.most_common(10),
        "top_partner": partner.most_common(10),
    }
