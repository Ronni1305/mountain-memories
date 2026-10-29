import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import LokalerSpeicher  # noqa: E402


@pytest.fixture
def speicher(tmp_path) -> LokalerSpeicher:
    return LokalerSpeicher(tmp_path / "daten")


def bild_bytes(fmt: str = "JPEG", groesse=(3000, 2000), farbe=(120, 160, 200), exif=None, modus="RGB") -> bytes:
    puffer = io.BytesIO()
    bild = Image.new(modus, groesse, farbe)
    kwargs = {"exif": exif} if exif is not None else {}
    bild.save(puffer, format=fmt, **kwargs)
    return puffer.getvalue()


@pytest.fixture
def tour_daten() -> dict:
    return {
        "art": "wandern", "name": "Wildspitze", "datum": "2026-07-14", "lat": 46.88524, "lon": 10.86728,
        "hoehe_m": 3768, "hoehe_quelle": "osm", "region": "Bezirk Imst, Tirol",
    }
