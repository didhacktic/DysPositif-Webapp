"""Utilitaires HTML utilisés par les modules de coloration."""
from __future__ import annotations

def escape_html(s: str) -> str:
    """Échappe les entités HTML basiques."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def split_html_tags(html: str):
    """Découpe une string HTML en segments texte / balises (<...>).
    Renvoie la liste des segments (les balises incluent les chevrons).
    Utile pour recolorer du HTML déjà existant sans toucher aux attributs.
    """
    import re
    return re.split(r'(<[^>]+>)', html)
