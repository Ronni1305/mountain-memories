"""Fotos prüfen und für die Ablage aufbereiten.

Jedes Foto wird als JPEG in zwei Größen gespeichert: ein großes Bild (längste Seite höchstens
2400 px) und ein Vorschaubild (480 px). Beim Neu-Kodieren fallen alle EXIF-Metadaten weg –
auch GPS-Koordinaten, die sonst den genauen Aufnahmeort verraten würden.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ERLAUBTE_ENDUNGEN = ["jpg", "jpeg", "png", "webp"]
ERLAUBTE_FORMATE = {"JPEG", "MPO", "PNG", "WEBP"}
MAX_UPLOAD_MB = 25
MAX_KANTE = 2400
THUMB_KANTE = 480


class FotoFehler(ValueError):
    """Verständliche Meldung, warum ein Foto nicht übernommen werden kann."""


@dataclass
class AufbereitetesFoto:
    gross: bytes
    vorschau: bytes
    breite: int
    hoehe: int
    dateiname: str


def _als_jpeg(bild: Image.Image, kante: int, qualitaet: int) -> bytes:
    kopie = bild.copy()
    kopie.thumbnail((kante, kante), Image.Resampling.LANCZOS)
    puffer = io.BytesIO()
    kopie.save(puffer, format="JPEG", quality=qualitaet, optimize=True, progressive=True)
    return puffer.getvalue()


def aufbereiten(daten: bytes, dateiname: str) -> AufbereitetesFoto:
    if len(daten) > MAX_UPLOAD_MB * 1024 * 1024:
        raise FotoFehler(f"„{dateiname}“ ist größer als {MAX_UPLOAD_MB} MB.")
    try:
        bild = Image.open(io.BytesIO(daten))
        if bild.format not in ERLAUBTE_FORMATE:
            raise FotoFehler(f"„{dateiname}“ hat kein erlaubtes Format (JPEG, PNG oder WebP).")
        bild.load()
    except FotoFehler:
        raise
    except Image.DecompressionBombError as exc:
        raise FotoFehler(f"„{dateiname}“ hat zu viele Bildpunkte.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise FotoFehler(f"„{dateiname}“ ist kein lesbares Bild.") from exc

    bild = ImageOps.exif_transpose(bild)  # Hochformat-Fotos vom Handy richtig drehen
    if bild.mode in ("RGBA", "LA", "P"):
        bild = bild.convert("RGBA")
        hintergrund = Image.new("RGB", bild.size, (255, 255, 255))
        hintergrund.paste(bild, mask=bild.getchannel("A"))
        bild = hintergrund
    elif bild.mode != "RGB":
        bild = bild.convert("RGB")

    gross = _als_jpeg(bild, MAX_KANTE, 86)
    breite, hoehe = Image.open(io.BytesIO(gross)).size
    return AufbereitetesFoto(
        gross=gross,
        vorschau=_als_jpeg(bild, THUMB_KANTE, 78),
        breite=breite,
        hoehe=hoehe,
        dateiname=dateiname,
    )


def foto_pfade(user_ordner: str, tour_id: str, foto_id: str) -> tuple[str, str]:
    """Ablagepfade im Speicher: <Benutzer>/<Tour>/<Foto>.jpg und …_vorschau.jpg."""
    basis = f"{user_ordner}/{tour_id}/{foto_id}"
    return f"{basis}.jpg", f"{basis}_vorschau.jpg"
