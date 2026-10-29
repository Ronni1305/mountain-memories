"""Betriebsart, Secrets und Anmeldung.

* Sind in ``.streamlit/secrets.toml`` (bzw. den Secrets von Streamlit Cloud) Supabase-
  Zugangsdaten hinterlegt, läuft die App im Cloud-Modus mit Login.
* Sonst läuft sie im lokalen Testmodus ohne Login. Auf Streamlit Community Cloud ist der
  lokale Modus gesperrt, weil die Daten dort bei einem Neustart verloren gingen und ohne
  Login für alle sichtbar wären.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from .database import AnmeldungAbgelaufen, LokalerSpeicher, SupabaseSpeicher

PROJEKT = Path(__file__).resolve().parent.parent
LOKALER_ORDNER = Path(os.environ.get("MM_DATEN_ORDNER") or PROJEKT / "daten")  # Tests nutzen einen eigenen Ordner


def supabase_zugang() -> dict | None:
    try:
        abschnitt = st.secrets.get("supabase")
    except Exception:  # noqa: BLE001 – keine secrets.toml vorhanden
        return None
    if not abschnitt or not abschnitt.get("url") or not abschnitt.get("anon_key"):
        return None
    return {"url": str(abschnitt["url"]).rstrip("/"), "key": str(abschnitt["anon_key"])}


def laeuft_in_streamlit_cloud() -> bool:
    return Path("/mount/src").exists() or os.environ.get("HOSTNAME", "") == "streamlit"


@st.cache_resource
def _lokaler_speicher() -> LokalerSpeicher:
    return LokalerSpeicher(LOKALER_ORDNER)


def _neuer_client(zugang: dict):
    from supabase import ClientOptions, create_client

    # Ein eigener Client je Browsersitzung: die Anmeldung gehört zur Sitzung, nicht zum Server.
    return create_client(zugang["url"], zugang["key"],
                         options=ClientOptions(auto_refresh_token=True, persist_session=True))


def anmelden(zugang: dict, email: str, passwort: str) -> str | None:
    """Gibt bei Erfolg None zurück, sonst eine verständliche Fehlermeldung."""
    try:
        client = _neuer_client(zugang)
        antwort = client.auth.sign_in_with_password({"email": email.strip(), "password": passwort})
    except Exception as exc:  # noqa: BLE001
        text = str(exc).lower()
        if "invalid login" in text or "invalid credentials" in text:
            return "E-Mail-Adresse oder Passwort stimmen nicht."
        if "email not confirmed" in text:
            return "Die E-Mail-Adresse ist noch nicht bestätigt (siehe Anleitung im README)."
        if "rate limit" in text or "too many" in text:
            return "Zu viele Versuche. Bitte ein paar Minuten warten."
        if "email logins are disabled" in text or "provider is disabled" in text:
            return ("Die Anmeldung mit E-Mail ist in Supabase ausgeschaltet "
                    "(Authentication → Sign In / Providers → Email einschalten).")
        if "api key" in text or "apikey" in text:
            return "Der Supabase-Schlüssel in den Secrets stimmt nicht (anon_key prüfen)."
        return ("Die Anmeldung ist gerade nicht möglich. Bitte Internetverbindung prüfen und erneut versuchen."
                f"\n\nTechnischer Hinweis: {str(exc)[:300]}")
    if not antwort or not antwort.user:
        return "E-Mail-Adresse oder Passwort stimmen nicht."
    st.session_state["mm_client"] = client
    st.session_state["mm_user"] = {"id": antwort.user.id, "email": antwort.user.email}
    st.session_state["mm_url_cache"] = {}
    return None


def abmelden() -> None:
    client = st.session_state.get("mm_client")
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:  # noqa: BLE001
            pass
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def angemeldet() -> bool:
    return "mm_client" in st.session_state


def speicher():
    """Der Speicher für diese Sitzung (lokal oder Supabase)."""
    if supabase_zugang():
        if not angemeldet():
            raise AnmeldungAbgelaufen("Bitte anmelden.")
        return SupabaseSpeicher(st.session_state["mm_client"], st.session_state["mm_user"]["id"],
                                st.session_state.setdefault("mm_url_cache", {}))
    return _lokaler_speicher()


def modus_text() -> str:
    if supabase_zugang():
        return "Cloud (Supabase)"
    return "Lokaler Testmodus"
