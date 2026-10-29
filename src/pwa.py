"""Startbildschirm-Symbol und Web-App-Manifest.

Streamlit erlaubt keine eigenen Einträge im ``<head>`` der Seite. Deshalb setzt ein kleines Skript
beim Laden Verweise auf das Manifest und das Apple-Touch-Icon. Die Dateien liefert Streamlit
aus dem Ordner ``static/`` unter ``app/static/…`` aus (``server.enableStaticServing``).

Auf Streamlit Community Cloud läuft die App in einem Rahmen (``/~/+/``) innerhalb einer Seite von
Streamlit, die selbst das Streamlit-Symbol und -Manifest anmeldet. Das Handy liest beim
„Zum Startbildschirm hinzufügen“ die äußere Seite. Beide liegen auf derselben Adresse, daher darf
das Skript die Verweise der äußeren Seite durch die eigenen ersetzen. Lokal gibt es keinen Rahmen;
dann wird die eigene Seite ergänzt.

Einschränkung: kein Offline-Modus und kein Service Worker.
"""
import streamlit as st

_SKRIPT = """
<script>
(function () {
  let d = document;
  try { if (window.top.document) d = window.top.document; } catch (e) { /* fremde Seite: eigene nehmen */ }
  if (d.getElementById("mm-manifest")) return;
  const basis = new URL("./app/static/", window.location.href).href;
  const setzen = (tag, sel, attrs) => {
    d.head.querySelectorAll(sel).forEach((e) => e.remove());
    const e = d.createElement(tag); Object.assign(e, attrs); d.head.appendChild(e);
  };
  setzen("link", 'link[rel="manifest"]', {id: "mm-manifest", rel: "manifest", href: basis + "manifest.json"});
  setzen("link", 'link[rel="apple-touch-icon"]', {rel: "apple-touch-icon", href: basis + "apple-touch-icon.png"});
  setzen("meta", 'meta[name="apple-mobile-web-app-title"]', {name: "apple-mobile-web-app-title", content: "Tourenbuch"});
  setzen("meta", 'meta[name="apple-mobile-web-app-capable"]', {name: "apple-mobile-web-app-capable", content: "yes"});
  setzen("meta", 'meta[name="mobile-web-app-capable"]', {name: "mobile-web-app-capable", content: "yes"});
  setzen("meta", 'meta[name="theme-color"]', {name: "theme-color", content: "#1f3d4a"});
})();
</script>
"""


def einbinden() -> None:
    st.html(_SKRIPT, unsafe_allow_javascript=True)
