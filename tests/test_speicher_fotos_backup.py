import io
import json
import zipfile

import pytest
from PIL import Image

from src import backup
from src.database import LokalerSpeicher, SchonVorhanden
from src.photo_storage import FotoFehler, aufbereiten

from .conftest import bild_bytes


def test_foto_formate_groesse_und_gps_entfernt():
    exif = Image.Exif()
    exif[0x8825] = {2: (47.0, 10.0, 0.0)}  # GPS-Block
    exif[0x0112] = 6  # Orientierung: um 90° gedreht
    f = aufbereiten(bild_bytes("JPEG", (3000, 2000), exif=exif), "handy.jpg")
    gross = Image.open(io.BytesIO(f.gross))
    assert max(gross.size) == 2400 and gross.size == (1600, 2400)  # gedreht und verkleinert
    assert not gross.getexif().get(0x8825)
    assert max(Image.open(io.BytesIO(f.vorschau)).size) == 480
    assert aufbereiten(bild_bytes("PNG", (50, 40), modus="RGBA", farbe=(1, 2, 3, 0)), "a.png").breite == 50
    assert aufbereiten(bild_bytes("WEBP", (50, 40)), "a.webp").hoehe == 40
    with pytest.raises(FotoFehler):
        aufbereiten(bild_bytes("GIF", (10, 10), modus="P", farbe=1), "a.gif")
    with pytest.raises(FotoFehler):
        aufbereiten(b"kein bild", "x.jpg")


def test_tour_speichern_bearbeiten_doppelt_loeschen(speicher, tour_daten):
    t = speicher.create_tour({**tour_daten, "id": "t1"})
    assert t["name"] == "Wildspitze" and t["dauer_min"] is None
    with pytest.raises(SchonVorhanden):
        speicher.create_tour({**tour_daten, "id": "t1"})  # doppelt abgeschickt
    speicher.update_tour("t1", {"name": "Wildspitze Südgipfel", "hm_auf": 1200})
    t = speicher.get_tour("t1")
    assert t["name"] == "Wildspitze Südgipfel" and t["hm_auf"] == 1200 and t["hoehe_quelle"] == "osm"

    f1 = speicher.add_photo("t1", aufbereiten(bild_bytes(), "a.jpg"), "Gipfelkreuz")
    f2 = speicher.add_photo("t1", aufbereiten(bild_bytes(), "b.jpg"))
    speicher.update_tour("t1", {"titelbild_id": f2["id"]})
    dateien = [speicher.foto_ordner / f[k] for f in (f1, f2) for k in ("pfad", "thumb_pfad")]
    assert all(d.exists() for d in dateien)

    speicher.delete_photo(f2)  # Titelbild gelöscht → Feld leer
    assert speicher.get_tour("t1")["titelbild_id"] is None
    assert not dateien[2].exists()

    speicher.delete_tour("t1")
    assert speicher.get_tour("t1") is None and speicher.list_photos() == []
    assert not any(d.exists() for d in dateien)  # keine verwaisten Dateien


def test_daten_bleiben_nach_neustart(tmp_path, tour_daten):
    LokalerSpeicher(tmp_path).create_tour({**tour_daten, "id": "x"})
    neu = LokalerSpeicher(tmp_path)  # „Neustart“
    speicher_foto = neu.add_photo("x", aufbereiten(bild_bytes(), "a.jpg"))
    assert LokalerSpeicher(tmp_path).list_photos("x")[0]["id"] == speicher_foto["id"]


def test_sicherung_hin_und_zurueck(tmp_path, tour_daten):
    quelle = LokalerSpeicher(tmp_path / "a")
    quelle.create_tour({**tour_daten, "id": "t1", "name": "Großglockner – Stüdlgrat", "bericht": "Schön; „kalt“"})
    quelle.create_tour({**tour_daten, "id": "t2", "art": "klettern", "datum": "2025-01-02", "hoehe_m": None})
    f = quelle.add_photo("t1", aufbereiten(bild_bytes(), "gipfel.jpg"), "Ausblick")
    quelle.update_tour("t1", {"titelbild_id": f["id"]})

    daten, fehler = backup.sicherung_zip(quelle)
    assert fehler == []
    z = zipfile.ZipFile(io.BytesIO(daten))
    inhalt = json.loads(z.read("sicherung.json"))
    assert inhalt["fotos"][0]["datei"].startswith("fotos/2026-07-14_Gro")
    csv_text = z.read("touren.csv").decode("utf-8-sig")
    assert "Großglockner – Stüdlgrat" in csv_text and "46,885240" in csv_text

    ziel = LokalerSpeicher(tmp_path / "b")
    inhalt, zf = backup.sicherung_lesen(daten, "s.zip")
    erg = backup.sicherung_einspielen(ziel, inhalt, zf)
    assert (erg.touren_neu, erg.fotos_neu, erg.fehler) == (2, 1, [])
    t1 = ziel.get_tour("t1")
    assert t1["titelbild_id"] == f["id"] and t1["bericht"] == "Schön; „kalt“" and t1["lat"] == tour_daten["lat"]
    assert ziel.list_photos("t1")[0]["beschriftung"] == "Ausblick"

    erg2 = backup.sicherung_einspielen(ziel, inhalt, zf)  # zweites Einspielen legt nichts doppelt an
    assert (erg2.touren_neu, erg2.touren_vorhanden) == (0, 2) and len(ziel.list_tours()) == 2

    with pytest.raises(ValueError):
        backup.sicherung_lesen(b"{}", "x.json")
