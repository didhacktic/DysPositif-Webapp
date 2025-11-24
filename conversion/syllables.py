"""Coloration syllabique (wrapper autour de lirecouleur si disponible).
Fournit : get_syllables(word) et colorize_syllables_html(text)
"""
from __future__ import annotations
from .conversion_models import COLORS_SYLLABLES
from .utils_html import escape_html

try:
    from lirecouleur.word import syllables as syllabize_word  # type: ignore
    import re
    SYLL_WORD_PATTERN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:'[A-Za-zÀ-ÖØ-öø-ÿ]+)?")
    HAVE_SYLLABLES = True
except Exception:
    syllabize_word = None
    SYLL_WORD_PATTERN = None
    HAVE_SYLLABLES = False


def get_syllables(word: str) -> list[str]:
    """Retourne la liste des syllabes pour `word` (vide si indisponible)."""
    if not HAVE_SYLLABLES or not word:
        return []
    try:
        return syllabize_word(word.lower()) or []
    except Exception:
        return []


def colorize_syllables_html(text: str) -> str:
    """Colorise le texte par syllabes (HTML)."""
    if not HAVE_SYLLABLES or not text or not text.strip():
        return escape_html(text)

    import re
    result = []
    color_index = 0
    i = 0

    while i < len(text):
        match = SYLL_WORD_PATTERN.match(text, i)
        if match:
            word = match.group(0)
            try:
                syllables_list = get_syllables(word)
                if not syllables_list:
                    result.append(escape_html(word))
                else:
                    pos = 0
                    for syl in syllables_list:
                        syl_len = len(syl)
                        part = word[pos:pos+syl_len] if pos+syl_len <= len(word) else word[pos:]
                        color = COLORS_SYLLABLES[color_index % len(COLORS_SYLLABLES)]
                        result.append(f"<span style='color:{color}'>{escape_html(part)}</span>")
                        color_index += 1
                        pos += len(part)
                    if pos < len(word):
                        rest = word[pos:]
                        color = COLORS_SYLLABLES[color_index % len(COLORS_SYLLABLES)]
                        result.append(f"<span style='color:{color}'>{escape_html(rest)}</span>")
                        color_index += 1
            except Exception:
                result.append(escape_html(word))
            i = match.end()
        else:
            result.append(escape_html(text[i]))
            i += 1

    return ''.join(result)
