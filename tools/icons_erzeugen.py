"""Erzeugt das App-Symbol „Mountain Memories“ in allen benötigten Größen.

Aufruf:  python tools/icons_erzeugen.py
Ergebnis: assets/*.png (Oberfläche) und static/*.png (Startbildschirm / Manifest)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASIS = Path(__file__).resolve().parent.parent
GROESSE = 1024

HIMMEL_OBEN = (24, 52, 66)
HIMMEL_UNTEN = (70, 134, 126)
SONNE = (244, 196, 104)
HINTERGRAT = (43, 92, 98)
BERG = (18, 40, 50)
SCHNEE = (244, 247, 247)


def motiv(abgerundet: bool, rand: float = 0.0) -> Image.Image:
    """Zeichnet das Symbol; ``rand`` verkleinert das Motiv (für die „maskable“-Variante)."""
    s = GROESSE
    bild = Image.new("RGBA", (s, s))
    zeichnung = ImageDraw.Draw(bild)
    for y in range(s):  # Himmel als senkrechter Verlauf
        t = y / (s - 1)
        farbe = tuple(round(a + (b - a) * t) for a, b in zip(HIMMEL_OBEN, HIMMEL_UNTEN))
        zeichnung.line([(0, y), (s, y)], fill=farbe)

    def p(x, y):  # Koordinaten zum Mittelpunkt hin stauchen
        k = 1 - 2 * rand
        return (s / 2 + (x - s / 2) * k, s / 2 + (y - s / 2) * k + rand * s * 0.25)

    zeichnung.ellipse([p(640, 205), p(830, 395)], fill=SONNE)
    zeichnung.polygon([p(-40, 800), p(250, 520), p(360, 610), p(560, 420), p(1064, 780), p(1064, 1100), p(-40, 1100)],
                      fill=HINTERGRAT)
    zeichnung.polygon([p(40, 1100), p(480, 250), p(980, 1100)], fill=BERG)
    zeichnung.polygon([p(480, 250), p(597, 449), p(552, 425), p(508, 478), p(468, 418), p(425, 462), p(377, 449)],
                      fill=SCHNEE)
    # kleine Gipfelfahne
    zeichnung.line([p(480, 252), p(480, 150)], fill=SCHNEE, width=max(2, round(14 * (1 - 2 * rand))))
    zeichnung.polygon([p(486, 150), p(566, 176), p(486, 202)], fill=SONNE)

    if abgerundet:
        maske = Image.new("L", (s, s), 0)
        ImageDraw.Draw(maske).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=255)
        bild.putalpha(maske)
    return bild


def speichern(bild: Image.Image, groesse: int, *ziele: Path) -> None:
    klein = bild.resize((groesse, groesse), Image.Resampling.LANCZOS)
    for ziel in ziele:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        klein.save(ziel, optimize=True)


def schriftzug(icon: Image.Image, ziel: Path) -> None:
    hoehe, text = 160, "Mountain Memories"
    schrift = None
    for name in ("seguisb.ttf", "segoeui.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            schrift = ImageFont.truetype(name, 76)
            break
        except OSError:
            continue
    schrift = schrift or ImageFont.load_default()
    breite = int(hoehe + 24 + ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=schrift) + 8)
    logo = Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0))
    logo.paste(icon.resize((hoehe, hoehe), Image.Resampling.LANCZOS), (0, 0))
    ImageDraw.Draw(logo).text((hoehe + 24, hoehe / 2), text, font=schrift, fill=HIMMEL_OBEN, anchor="lm")
    logo.save(ziel, optimize=True)


if __name__ == "__main__":
    rund = motiv(abgerundet=True)
    voll = motiv(abgerundet=False)
    a, st = BASIS / "assets", BASIS / "static"
    speichern(rund, 512, a / "app_icon.png")
    speichern(rund, 64, a / "favicon.png", st / "favicon.png")
    speichern(voll, 180, a / "apple-touch-icon.png", st / "apple-touch-icon.png")  # iOS rundet selbst ab
    speichern(rund, 192, a / "icon-192.png", st / "icon-192.png")
    speichern(rund, 512, a / "icon-512.png", st / "icon-512.png")
    speichern(motiv(abgerundet=False, rand=0.1), 512, st / "icon-512-maskable.png")
    schriftzug(rund, a / "logo_wide.png")
    print("Symbole erzeugt in", a, "und", st)
