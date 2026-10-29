"""Oberflächentests ohne Browser (lokaler Testmodus mit eigenem, leerem Datenordner)."""
import os
import tempfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ORDNER = tempfile.mkdtemp(prefix="mm_test_")
os.environ["MM_DATEN_ORDNER"] = ORDNER
APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")

from src.database import LokalerSpeicher  # noqa: E402
from src.photo_storage import aufbereiten  # noqa: E402

from .conftest import bild_bytes  # noqa: E402


@pytest.fixture(scope="module")
def app_mit_tour():
    sp = LokalerSpeicher(Path(ORDNER))
    sp.create_tour({"id": "t-app", "art": "bergsteigen", "name": "Wildspitze", "datum": "2026-07-14",
                    "lat": 46.88524, "lon": 10.86728, "hoehe_m": 3768, "hoehe_quelle": "osm",
                    "partner": "Anna", "hm_auf": 1500, "region": "Bezirk Imst, Tirol"})
    sp.add_photo("t-app", aufbereiten(bild_bytes(), "gipfel.jpg"), "Gipfelkreuz")
    return sp


def lauf(seite: str | None = None, **zustand) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    for k, v in zustand.items():
        at.session_state[k] = v
    at.run()
    if seite:
        at.switch_page(seite).run()
    return at


@pytest.mark.parametrize("seite", [None, "app_pages/neue_tour.py", "app_pages/meine_touren.py",
                                   "app_pages/statistik.py", "app_pages/einstellungen.py"])
def test_seiten_laufen_ohne_fehler(app_mit_tour, seite):
    at = lauf(seite)
    assert not at.exception
    assert not at.error, [e.value for e in at.error]


def test_meine_touren_zeigt_tour_und_suche(app_mit_tour):
    at = lauf("app_pages/meine_touren.py")
    assert any("Wildspitze" in m.value for m in at.markdown)
    at.text_input(key="mt_suche").set_value("anna").run()
    assert any("1 von 1" in c.value for c in at.caption)
    at.text_input(key="mt_suche").set_value("gibtsnicht").run()
    assert any("0 von 1" in c.value for c in at.caption)


def test_statistik_zahlen(app_mit_tour):
    at = lauf("app_pages/statistik.py")
    werte = {m.label: m.value for m in at.metric}
    assert werte["Touren gesamt"] == "1" and werte["Höhenmeter Aufstieg"] == "1.500 Hm"


def test_tourenansicht_und_bearbeiten(app_mit_tour):
    at = lauf("app_pages/tour.py", mm_tour_id="t-app")
    assert not at.exception
    assert any("Wildspitze" in s.value for s in at.subheader)
    at = lauf("app_pages/tour.py", mm_tour_id="t-app", mm_bearbeiten=True)
    assert not at.exception
    assert at.text_input(key="bt_name").value == "Wildspitze"
    at.text_input(key="bt_name").set_value("Wildspitze (Nordgipfel)")
    at.button(key="bt_speichern").click().run()
    assert not at.exception
    assert app_mit_tour.get_tour("t-app")["name"] == "Wildspitze (Nordgipfel)"


def test_cloud_modus_ohne_anmeldung_zeigt_keine_daten(app_mit_tour):
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["supabase"] = {"url": "https://nicht-vorhanden.invalid", "anon_key": "test"}
    at.run()
    assert not at.exception
    assert at.text_input[0].label == "E-Mail-Adresse"
    assert not any("Wildspitze" in m.value for m in at.markdown)
    at.text_input[0].set_value("a@b.at")
    at.text_input[1].set_value("falsch")
    at.button[0].click().run()
    assert at.error and "mm_client" not in at.session_state


def test_gipfelname_automatisch_und_korrigierbar(app_mit_tour, monkeypatch):
    from src import geocoding

    gipfel = geocoding.Kandidat("Habicht", "Gipfel", 40.0, 47.04, 11.29, "N1", 3277)
    monkeypatch.setattr(geocoding, "ort_bestimmen", lambda lat, lon: geocoding.OrtsInfo(
        kandidaten=[gipfel], vorschlag=gipfel, region="Bezirk Innsbruck-Land, Tirol", ort="Neustift",
        gelaendehoehe_m=3230))
    at = lauf("app_pages/neue_tour.py", nt_pos=(47.0401, 11.2902))
    assert at.text_input(key="nt_name").value == "Habicht"
    assert at.number_input(key="nt_hoehe").value == 3277
    assert any("OpenStreetMap" in c.value for c in at.caption)
    at.segmented_control(key="nt_art").set_value("bergsteigen")
    at.text_input(key="nt_name").set_value("Habicht über Mischbachferner")
    at.number_input(key="nt_hoehe").set_value(3280)
    at.button(key="nt_speichern").click().run()
    t = next(t for t in app_mit_tour.list_tours() if t["name"] == "Habicht über Mischbachferner")
    assert (t["hoehe_m"], t["hoehe_quelle"], t["region"]) == (3280, "manuell", "Bezirk Innsbruck-Land, Tirol")


def test_neue_tour_ohne_namen_und_ohne_hoehe_speichern(app_mit_tour):
    at = lauf("app_pages/neue_tour.py", nt_pos=(47.2692, 11.4041), nt_geo_fuer=(47.2692, 11.4041))
    at.segmented_control(key="nt_art").set_value("wandern").run()
    vorher = len(app_mit_tour.list_tours())
    at.button(key="nt_speichern").click().run()
    assert not at.exception
    touren = app_mit_tour.list_tours()
    assert len(touren) == vorher + 1
    neu = next(t for t in touren if t["name"].startswith("Wanderung vom"))
    assert neu["hoehe_m"] is None and neu["dauer_min"] is None
    assert any("gespeichert" in s.value for s in at.success)


def test_favorit_markieren_und_filtern(app_mit_tour):
    at = lauf("app_pages/tour.py", mm_tour_id="t-app")
    at.button(key="tp_favorit").click().run()
    assert not at.exception
    assert app_mit_tour.get_tour("t-app")["favorit"]
    at = lauf("app_pages/meine_touren.py")
    at.toggle(key="mt_favoriten").set_value(True).run()
    assert any("1 von" in c.value for c in at.caption)
    at.selectbox(key="mt_jahr").set_value("2026").run()
    assert not at.exception


def test_foto_hochladen_bietet_galerie_und_foto_laesst_sich_laden(app_mit_tour):
    from src import ui
    import inspect

    assert 'type="image"' in inspect.getsource(ui._foto_auswahl)  # image/* → Handy zeigt die Galerie
    foto = app_mit_tour.list_photos("t-app")[0]
    assert app_mit_tour.photo_bytes(foto)[:2] == b"\xff\xd8"  # JPEG


class _Datei(__import__("io").BytesIO):
    """Ersatz für ein hochgeladenes Foto (AppTest kann keine Dateien hochladen)."""

    def __init__(self, daten: bytes, name: str):
        super().__init__(daten)
        self.name, self.size, self.file_id = name, len(daten), name


def test_einzeln_gesammelte_fotos_werden_gespeichert_und_entfernbar(app_mit_tour):
    fotos = [_Datei(bild_bytes(), "a.jpg"), _Datei(bild_bytes(farbe=(10, 120, 200)), "b.jpg")]
    at = lauf("app_pages/neue_tour.py", nt_token="t-fotos",
              **{"nt_sammlung_t-fotos": fotos, "nt_pos": (47.1, 11.1), "nt_geo_fuer": (47.1, 11.1)})
    assert at.text_input(key="nt_cap_t-fotos_b.jpg")
    at.button(key="nt_weg_t-fotos_b.jpg").click().run()
    assert not at.exception
    at.segmented_control(key="nt_art").set_value("wandern").run()
    at.text_input(key="nt_name").set_value("Fototest").run()
    at.button(key="nt_speichern").click().run()
    assert not at.exception
    assert [f["dateiname"] for f in app_mit_tour.list_photos("t-fotos")] == ["a.jpg"]
