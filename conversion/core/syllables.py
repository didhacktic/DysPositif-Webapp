# Copie minimale de core/syllables.py pour usage HTML (syllabize_word) dans webapp
import re, os, sys

try:
    from lirecouleur.word import syllables as syllables
    HAVE_LIRECOULEUR = True
except Exception as e:
    HAVE_LIRECOULEUR = False
    print(f"[WARN] lirecouleur indisponible: {e}")

WORD_PATTERN = re.compile(r"[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF'\u2019]+")

# Exposition directe de la fonction syllables (si disponible)
