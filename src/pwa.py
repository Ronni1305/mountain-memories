"""Startbildschirm-Symbol und Web-App-Manifest.

Streamlit erlaubt keine eigenen Einträge im ``<head>`` der Seite. Deshalb fügt ein kleines Skript
beim Laden Verweise auf das Manifest und das Apple-Touch-Icon hinzu. Die Dateien liefert Streamlit
aus dem Ordner ``static/`` unter ``app/static/…`` aus (``server.enableStaticServing``).

Einschränkungen (ehrlich): Es gibt keinen Offline-Modus und keinen Service Worker. Auf Streamlit
Community Cloud läuft die App in einem eingebetteten Rahmen; dort kann der Browser beim
„Zum Startbildschirm hinzufügen“ trotzdem das allgemeine Streamlit-Symbol verwenden.
"""
import streamlit as st

_SKRIPT = """
<script>
(function () {
  const d = document;
  if (d.getElementById("mm-manifest")) return;
  const basis = new URL("./app/static/", window.location.href).href;
  const neu = (tag, attrs) => { const e = d.createElement(tag); Object.assign(e, attrs); d.head.appendChild(e); };
  neu("link", {id: "mm-manifest", rel: "manifest", href: basis + "manifest.json"});
  neu("link", {rel: "apple-touch-icon", href: basis + "apple-touch-icon.png"});
  neu("meta", {name: "apple-mobile-web-app-title", content: "Tourenbuch"});
  neu("meta", {name: "apple-mobile-web-app-capable", content: "yes"});
  neu("meta", {name: "mobile-web-app-capable", content: "yes"});
  neu("meta", {name: "theme-color", content: "#1f3d4a"});
})();
</script>
"""


def einbinden() -> None:
    st.html(_SKRIPT, unsafe_allow_javascript=True)
