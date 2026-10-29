from datetime import date

from src import statistics
from src.models import bereinigen, dauer_text, ersatz_name, hoehe_text, moegliche_duplikate, partner_liste, pruefen


def test_bereinigen_leere_felder_werden_none_nicht_null():
    t = bereinigen({"art": "klettern", "name": "  ", "datum": date(2026, 5, 1), "hm_auf": "", "dauer_min": None,
                    "lat": "47.1", "lon": 11, "bewertung": 9})
    assert t["name"] is None and t["hm_auf"] is None and t["dauer_min"] is None
    assert t["datum"] == "2026-05-01" and t["lat"] == 47.1 and t["bewertung"] is None


def test_hoehe_ohne_wert_hat_keine_quelle():
    assert bereinigen({"hoehe_m": None, "hoehe_quelle": "dem"})["hoehe_quelle"] is None
    assert "hoehe_quelle" not in bereinigen({"name": "x"})  # Teil-Änderung lässt die Quelle in Ruhe


def test_pruefen_ohne_dauer_und_hoehe_ok(tour_daten):
    tour_daten.pop("hoehe_m")
    assert pruefen(bereinigen(tour_daten)) == []


def test_pruefen_ohne_position():
    fehler = pruefen(bereinigen({"art": "wandern", "name": "x", "datum": "2026-01-01"}))
    assert any("Position" in f for f in fehler)


def test_ersatzname_wenn_kein_name():
    assert ersatz_name("klettern", "2026-07-14") == "Klettertour vom 14.07.2026"
    assert ersatz_name("wandern", "2026-07-14", "Sölden") == "Wanderung bei Sölden"


def test_texte():
    assert dauer_text(125) == "2 h 05 min" and dauer_text(60) == "1 h" and dauer_text(None) is None
    assert hoehe_text({"hoehe_m": 2700, "hoehe_quelle": "dem"}) == "ca. 2.700 m"
    assert hoehe_text({"hoehe_m": 3768, "hoehe_quelle": "osm"}) == "3.768 m"
    assert partner_liste("Anna, Ben; Clara und Dörte") == ["Anna", "Ben", "Clara", "Dörte"]


def test_duplikate(tour_daten):
    alt = {**tour_daten, "id": "a"}
    assert moegliche_duplikate({**tour_daten, "id": "b", "name": "wildspitze "}, [alt])
    assert moegliche_duplikate({**tour_daten, "id": "b", "name": "Anders", "lat": 46.8853}, [alt])  # < 150 m
    assert not moegliche_duplikate({**tour_daten, "id": "b", "datum": "2026-07-15"}, [alt])


TOUREN = [
    {"id": "1", "art": "wandern", "name": "Patscherkofel", "datum": "2024-06-01", "hm_auf": 1000, "region": "Tirol", "partner": "Anna"},
    {"id": "2", "art": "wandern", "name": "patscherkofel", "datum": "2025-06-01", "hm_auf": None, "region": "Tirol", "partner": "Anna, Ben", "hoehe_m": 2246},
    {"id": "3", "art": "klettern", "name": "Martinswand", "datum": "2025-08-01", "region": None, "dauer_min": 180},
    {"id": "4", "art": "bergsteigen", "name": "Wildspitze", "datum": "2025-07-14", "hm_auf": 1500, "hoehe_m": 3768, "region": "Tirol"},
]


def test_kennzahlen_fehlende_werte_nicht_als_null():
    k = statistics.kennzahlen(TOUREN)
    assert k["gesamt"] == 4
    assert k["nach_art"] == {"wandern": 2, "klettern": 1, "bergsteigen": 1}
    assert k["hm_summe"] == 2500 and k["hm_anzahl"] == 3 - 1  # nur 2 Touren mit Höhenmetern
    assert k["dauer_summe_min"] == 180 and k["dauer_anzahl"] == 1
    assert k["orte_verschieden"] == 3  # Patscherkofel zweimal (Groß-/Kleinschreibung egal)
    assert k["top_orte"][0] == ("Patscherkofel", 2)
    assert k["hoechste"]["name"] == "Wildspitze"
    assert ("Anna", 2) in k["top_partner"]
    jahre = {(z["Jahr"], z["Tourenart"]): z["Touren"] for z in k["pro_jahr"]}
    assert jahre[("2025", "Wandern")] == 1 and jahre[("2024", "Wandern")] == 1


def test_kennzahlen_ohne_hoehenmeter():
    k = statistics.kennzahlen([{"id": "x", "art": "wandern", "name": "a", "datum": "2025-01-01"}])
    assert k["hm_summe"] is None and k["dauer_summe_min"] is None and k["hoechste"] is None


def test_filter_und_sortierung():
    f = statistics.filtern(TOUREN, arten=["wandern"], von=date(2025, 1, 1))
    assert [t["id"] for t in f] == ["2"]
    assert [t["id"] for t in statistics.filtern(TOUREN, suche="ben")] == ["2"]
    assert [t["id"] for t in statistics.filtern(TOUREN, regionen=["Ohne Region"])] == ["3"]
    assert [t["id"] for t in statistics.filtern(TOUREN, arten=[])] == []
    hoehe = statistics.SORTIERUNGEN["Höhe – höchste zuerst"](TOUREN)
    assert [t["id"] for t in hoehe][:2] == ["4", "2"]
    assert statistics.SORTIERUNGEN["Name A–Z"](TOUREN)[0]["name"] == "Martinswand"


def test_filter_jahr_und_favoriten():
    touren = [dict(t, favorit=(t["id"] == "4")) for t in TOUREN]
    assert [t["id"] for t in statistics.filtern(touren, jahr="2025")] == ["2", "3", "4"]
    assert [t["id"] for t in statistics.filtern(touren, nur_favoriten=True)] == ["4"]
    assert statistics.filtern(touren, jahr="2024", nur_favoriten=True) == []


def test_favorit_wird_wahrheitswert():
    assert bereinigen({"favorit": 1})["favorit"] is True
    assert bereinigen({"favorit": "ja"})["favorit"] is True
    assert bereinigen({"favorit": "0"})["favorit"] is False and bereinigen({"favorit": None})["favorit"] is False
    assert "favorit" not in bereinigen({"name": "x"})  # nur mitschicken, wenn geändert
