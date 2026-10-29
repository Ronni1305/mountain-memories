"""Dauerhafte Speicherung von Touren und Fotos.

Zwei gleichwertige Speicher mit derselben Schnittstelle:

* ``LokalerSpeicher`` – SQLite-Datei und Fotoordner unter ``daten/``. Nur zum Ausprobieren auf
  dem eigenen Rechner gedacht; auf Streamlit Community Cloud würden diese Dateien bei einem
  Neustart verloren gehen und sind dort deshalb gesperrt (siehe ``config.py``).
* ``SupabaseSpeicher`` – PostgreSQL-Tabellen mit Row Level Security und ein privater
  Foto-Bucket. Alle Zugriffe laufen mit der Sitzung der angemeldeten Benutzerin, die Datenbank
  selbst verhindert also, dass jemand anderes Touren oder Fotos liest.

Löschstrategie: Beim Löschen einer Tour werden zuerst die Bilddateien entfernt, danach die
Tour; die Foto-Einträge fallen über ``ON DELETE CASCADE`` mit weg. Schlägt das Entfernen der
Dateien fehl, bleibt die Tour bestehen – so entstehen keine verwaisten Bilddateien.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .models import FOTO_FELDER, TOUR_FELDER, bereinigen, jetzt_iso, neue_id
from .photo_storage import AufbereitetesFoto, foto_pfade

BUCKET = "fotos"
SIGNIERT_SEKUNDEN = 3600


class SpeicherFehler(Exception):
    """Fehler mit einer Meldung, die man der Benutzerin zeigen kann."""


class SchonVorhanden(SpeicherFehler):
    """Eine Tour oder ein Foto mit dieser ID gibt es bereits (z. B. doppelt abgeschickt)."""


class AnmeldungAbgelaufen(SpeicherFehler):
    pass


# --------------------------------------------------------------------------------------------
# Lokaler Speicher
# --------------------------------------------------------------------------------------------

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS tours (
    id TEXT PRIMARY KEY,
    art TEXT NOT NULL CHECK (art IN ('wandern','klettern','bergsteigen')),
    name TEXT NOT NULL,
    datum TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    hoehe_m INTEGER,
    hoehe_quelle TEXT,
    region TEXT,
    dauer_min INTEGER,
    partner TEXT,
    ausgangspunkt TEXT,
    ziel TEXT,
    hm_auf INTEGER,
    hm_ab INTEGER,
    schwierigkeit TEXT,
    wetter TEXT,
    bericht TEXT,
    bewertung INTEGER,
    titelbild_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,
    tour_id TEXT NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    pfad TEXT NOT NULL,
    thumb_pfad TEXT NOT NULL,
    dateiname TEXT,
    beschriftung TEXT,
    breite INTEGER,
    hoehe INTEGER,
    bytes INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS photos_tour ON photos(tour_id);
"""


class LokalerSpeicher:
    modus = "lokal"

    def __init__(self, ordner: Path):
        self.ordner = Path(ordner)
        self.foto_ordner = self.ordner / "fotos"
        self.foto_ordner.mkdir(parents=True, exist_ok=True)
        self.db_datei = self.ordner / "tourenbuch.sqlite"
        with self._verbindung() as con:
            con.executescript(_SQLITE_SCHEMA)

    def _verbindung(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_datei, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    # Touren ---------------------------------------------------------------------------------
    def list_tours(self) -> list[dict]:
        with self._verbindung() as con:
            zeilen = con.execute("SELECT * FROM tours ORDER BY datum DESC, created_at DESC").fetchall()
        return [dict(z) for z in zeilen]

    def get_tour(self, tour_id: str) -> dict | None:
        with self._verbindung() as con:
            z = con.execute("SELECT * FROM tours WHERE id = ?", (tour_id,)).fetchone()
        return dict(z) if z else None

    def create_tour(self, tour: dict) -> dict:
        daten = bereinigen(tour)
        daten.setdefault("id", neue_id())
        daten["created_at"] = daten.get("created_at") or jetzt_iso()
        daten["updated_at"] = jetzt_iso()
        spalten = [k for k in TOUR_FELDER if k in daten]
        try:
            with self._verbindung() as con:
                con.execute(
                    f"INSERT INTO tours ({','.join(spalten)}) VALUES ({','.join('?' * len(spalten))})",
                    [daten[k] for k in spalten],
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc) or "PRIMARY" in str(exc):
                raise SchonVorhanden("Diese Tour ist bereits gespeichert.") from exc
            raise SpeicherFehler(f"Die Tour konnte nicht gespeichert werden ({exc}).") from exc
        return self.get_tour(daten["id"])

    def update_tour(self, tour_id: str, aenderungen: dict) -> dict:
        daten = bereinigen(aenderungen)
        daten.pop("id", None)
        daten.pop("created_at", None)
        daten["updated_at"] = jetzt_iso()
        spalten = [k for k in TOUR_FELDER if k in daten]
        with self._verbindung() as con:
            con.execute(
                f"UPDATE tours SET {', '.join(f'{k} = ?' for k in spalten)} WHERE id = ?",
                [daten[k] for k in spalten] + [tour_id],
            )
        return self.get_tour(tour_id)

    def delete_tour(self, tour_id: str) -> None:
        for foto in self.list_photos(tour_id):
            self._dateien_loeschen(foto)
        with self._verbindung() as con:
            con.execute("DELETE FROM tours WHERE id = ?", (tour_id,))
        tour_ordner = self.foto_ordner / tour_id
        if tour_ordner.exists() and not any(tour_ordner.iterdir()):
            tour_ordner.rmdir()

    # Fotos ----------------------------------------------------------------------------------
    def list_photos(self, tour_id: str | None = None) -> list[dict]:
        with self._verbindung() as con:
            if tour_id:
                zeilen = con.execute(
                    "SELECT * FROM photos WHERE tour_id = ? ORDER BY created_at, id", (tour_id,)
                ).fetchall()
            else:
                zeilen = con.execute("SELECT * FROM photos ORDER BY created_at, id").fetchall()
        return [dict(z) for z in zeilen]

    def add_photo(self, tour_id: str, foto: AufbereitetesFoto, beschriftung: str | None = None,
                  foto_id: str | None = None) -> dict:
        foto_id = foto_id or neue_id()
        pfad, thumb = foto_pfade("lokal", tour_id, foto_id)
        ziel_gross, ziel_thumb = self.foto_ordner / pfad, self.foto_ordner / thumb
        ziel_gross.parent.mkdir(parents=True, exist_ok=True)
        ziel_gross.write_bytes(foto.gross)
        ziel_thumb.write_bytes(foto.vorschau)
        zeile = {
            "id": foto_id, "tour_id": tour_id, "pfad": pfad, "thumb_pfad": thumb,
            "dateiname": foto.dateiname, "beschriftung": (beschriftung or "").strip() or None,
            "breite": foto.breite, "hoehe": foto.hoehe, "bytes": len(foto.gross),
            "created_at": jetzt_iso(),
        }
        try:
            with self._verbindung() as con:
                con.execute(
                    f"INSERT INTO photos ({','.join(FOTO_FELDER)}) VALUES ({','.join('?' * len(FOTO_FELDER))})",
                    [zeile[k] for k in FOTO_FELDER],
                )
        except sqlite3.IntegrityError as exc:
            ziel_gross.unlink(missing_ok=True)
            ziel_thumb.unlink(missing_ok=True)
            raise SchonVorhanden("Dieses Foto ist bereits gespeichert.") from exc
        return zeile

    def update_photo(self, foto_id: str, beschriftung: str | None) -> None:
        with self._verbindung() as con:
            con.execute("UPDATE photos SET beschriftung = ? WHERE id = ?",
                        ((beschriftung or "").strip() or None, foto_id))

    def delete_photo(self, foto: dict) -> None:
        self._dateien_loeschen(foto)
        with self._verbindung() as con:
            con.execute("UPDATE tours SET titelbild_id = NULL WHERE titelbild_id = ?", (foto["id"],))
            con.execute("DELETE FROM photos WHERE id = ?", (foto["id"],))

    def _dateien_loeschen(self, foto: dict) -> None:
        for p in (foto["pfad"], foto["thumb_pfad"]):
            (self.foto_ordner / p).unlink(missing_ok=True)

    def photo_sources(self, fotos: list[dict], vorschau: bool = True) -> dict[str, bytes]:
        quellen = {}
        for f in fotos:
            datei = self.foto_ordner / (f["thumb_pfad"] if vorschau else f["pfad"])
            if datei.exists():
                quellen[f["id"]] = datei.read_bytes()
        return quellen

    def photo_bytes(self, foto: dict) -> bytes:
        return (self.foto_ordner / foto["pfad"]).read_bytes()


# --------------------------------------------------------------------------------------------
# Supabase
# --------------------------------------------------------------------------------------------

class SupabaseSpeicher:
    modus = "cloud"

    def __init__(self, client, user_id: str, url_cache: dict | None = None):
        self.c = client
        self.user_id = user_id
        # Signierte Foto-Links je Sitzung zwischenspeichern, damit nicht jede Neudarstellung
        # neue Links anfordert. Die Links laufen nach einer Stunde ab.
        self._urls = url_cache if url_cache is not None else {}

    def _pruefe_sitzung(self) -> None:
        try:
            sitzung = self.c.auth.get_session()  # erneuert ein abgelaufenes Token automatisch
        except Exception as exc:  # noqa: BLE001 – Netzwerk oder ungültiges Refresh-Token
            raise AnmeldungAbgelaufen("Die Anmeldung ist abgelaufen. Bitte neu anmelden.") from exc
        if sitzung is None:
            raise AnmeldungAbgelaufen("Die Anmeldung ist abgelaufen. Bitte neu anmelden.")

    def _ausfuehren(self, anfrage, was: str):
        self._pruefe_sitzung()
        try:
            return anfrage.execute().data
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None)
            if code == "23505":
                raise SchonVorhanden("Dieser Eintrag ist bereits gespeichert.") from exc
            if code in ("42501", "PGRST301"):
                raise AnmeldungAbgelaufen("Keine Berechtigung – bitte neu anmelden.") from exc
            raise SpeicherFehler(f"{was} ist gerade nicht möglich. Bitte später nochmals versuchen.") from exc

    @property
    def _bucket(self):
        return self.c.storage.from_(BUCKET)

    # Touren ---------------------------------------------------------------------------------
    def list_tours(self) -> list[dict]:
        return self._ausfuehren(
            self.c.table("tours").select("*").order("datum", desc=True).order("created_at", desc=True),
            "Das Laden der Touren",
        ) or []

    def get_tour(self, tour_id: str) -> dict | None:
        daten = self._ausfuehren(self.c.table("tours").select("*").eq("id", tour_id).limit(1), "Das Laden der Tour")
        return daten[0] if daten else None

    def create_tour(self, tour: dict) -> dict:
        daten = bereinigen(tour)
        daten.setdefault("id", neue_id())
        daten.pop("updated_at", None)
        if not daten.get("created_at"):
            daten.pop("created_at", None)
        daten["user_id"] = self.user_id
        zeilen = self._ausfuehren(self.c.table("tours").insert(daten), "Das Speichern der Tour")
        return zeilen[0] if zeilen else self.get_tour(daten["id"])

    def update_tour(self, tour_id: str, aenderungen: dict) -> dict:
        daten = bereinigen(aenderungen)
        for k in ("id", "created_at", "updated_at", "user_id"):
            daten.pop(k, None)
        zeilen = self._ausfuehren(self.c.table("tours").update(daten).eq("id", tour_id), "Das Speichern der Änderungen")
        return zeilen[0] if zeilen else self.get_tour(tour_id)

    def delete_tour(self, tour_id: str) -> None:
        fotos = self.list_photos(tour_id)
        if fotos:
            self._dateien_loeschen(fotos)
        self._ausfuehren(self.c.table("tours").delete().eq("id", tour_id), "Das Löschen der Tour")

    # Fotos ----------------------------------------------------------------------------------
    def list_photos(self, tour_id: str | None = None) -> list[dict]:
        anfrage = self.c.table("photos").select("*")
        if tour_id:
            anfrage = anfrage.eq("tour_id", tour_id)
        return self._ausfuehren(anfrage.order("created_at").order("id"), "Das Laden der Fotos") or []

    def add_photo(self, tour_id: str, foto: AufbereitetesFoto, beschriftung: str | None = None,
                  foto_id: str | None = None) -> dict:
        self._pruefe_sitzung()
        foto_id = foto_id or neue_id()
        pfad, thumb = foto_pfade(self.user_id, tour_id, foto_id)
        optionen = {"content-type": "image/jpeg", "upsert": "false"}
        try:
            self._bucket.upload(pfad, foto.gross, optionen)
            self._bucket.upload(thumb, foto.vorschau, optionen)
        except Exception as exc:  # noqa: BLE001
            self._still_entfernen([pfad, thumb])
            if "Duplicate" in str(exc) or "already exists" in str(exc):
                raise SchonVorhanden("Dieses Foto ist bereits gespeichert.") from exc
            raise SpeicherFehler(f"„{foto.dateiname}“ konnte nicht hochgeladen werden.") from exc
        zeile = {
            "id": foto_id, "tour_id": tour_id, "user_id": self.user_id, "pfad": pfad,
            "thumb_pfad": thumb, "dateiname": foto.dateiname,
            "beschriftung": (beschriftung or "").strip() or None,
            "breite": foto.breite, "hoehe": foto.hoehe, "bytes": len(foto.gross),
        }
        try:
            daten = self._ausfuehren(self.c.table("photos").insert(zeile), "Das Speichern des Fotos")
        except SpeicherFehler:
            self._still_entfernen([pfad, thumb])  # keine verwaisten Dateien hinterlassen
            raise
        return daten[0] if daten else zeile

    def update_photo(self, foto_id: str, beschriftung: str | None) -> None:
        self._ausfuehren(
            self.c.table("photos").update({"beschriftung": (beschriftung or "").strip() or None}).eq("id", foto_id),
            "Das Speichern der Bildunterschrift",
        )

    def delete_photo(self, foto: dict) -> None:
        self._dateien_loeschen([foto])
        self._ausfuehren(self.c.table("photos").delete().eq("id", foto["id"]), "Das Löschen des Fotos")

    def _dateien_loeschen(self, fotos: list[dict]) -> None:
        self._pruefe_sitzung()
        pfade = [p for f in fotos for p in (f["pfad"], f["thumb_pfad"])]
        try:
            self._bucket.remove(pfade)
        except Exception as exc:  # noqa: BLE001
            raise SpeicherFehler("Die Fotos konnten nicht gelöscht werden. Es wurde nichts verändert.") from exc
        for p in pfade:
            self._urls.pop(p, None)

    def _still_entfernen(self, pfade: list[str]) -> None:
        try:
            self._bucket.remove(pfade)
        except Exception:  # noqa: BLE001
            pass

    def photo_sources(self, fotos: list[dict], vorschau: bool = True) -> dict[str, str]:
        jetzt = time.time()
        pfade = {f["id"]: (f["thumb_pfad"] if vorschau else f["pfad"]) for f in fotos}
        fehlend = [p for p in pfade.values() if self._urls.get(p, (None, 0))[1] < jetzt + 120]
        if fehlend:
            try:
                self._pruefe_sitzung()
                for eintrag in self._bucket.create_signed_urls(fehlend, SIGNIERT_SEKUNDEN):
                    url = eintrag.get("signedURL") or eintrag.get("signedUrl")
                    if url and not eintrag.get("error"):
                        self._urls[eintrag["path"]] = (url, jetzt + SIGNIERT_SEKUNDEN)
            except AnmeldungAbgelaufen:
                raise
            except Exception:  # noqa: BLE001 – dann fehlen eben einzelne Bilder
                pass
        return {fid: self._urls[p][0] for fid, p in pfade.items() if p in self._urls}

    def photo_bytes(self, foto: dict) -> bytes:
        self._pruefe_sitzung()
        try:
            return self._bucket.download(foto["pfad"])
        except Exception as exc:  # noqa: BLE001
            raise SpeicherFehler(f"Foto „{foto.get('dateiname') or foto['id']}“ konnte nicht geladen werden.") from exc


def als_json(daten) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=2, default=str)
