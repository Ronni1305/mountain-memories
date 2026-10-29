"""Mountain Memories – Bausteine der App (ohne Streamlit-Seitenlogik)."""

# HTTPS-Zertifikate aus dem Speicher des Betriebssystems verwenden. Ohne das scheitern unter
# Windows mit Virenscanner oder Firmen-Proxy alle Abfragen der Geodienste und von Supabase.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover
    pass
