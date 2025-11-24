"""Orchestrateur de coloration minimal.

Ce fichier ne contient pas d'implémentations lourdes :
- il ré-exporte les fonctions publiques des modules `syllables`,
  `mute_letters` et `numbers` ;
- il fournit une fonction d'orchestration `colorize_syllables_and_mute_html`
  qui appelle les helpers des modules appropriés.

L'objectif est d'éviter la duplication de code et de garder la logique
tests/implémentations dans leurs modules respectifs.
"""
from __future__ import annotations

from . import syllables as _syllables
from . import mute_letters as _mute
from . import numbers as _numbers
from .utils_html import escape_html
from .conversion_models import COLORS_SYLLABLES, COLOR_MUTE

# Ré-exports pour compatibilité publique
colorize_syllables_html = _syllables.colorize_syllables_html
colorize_mute_letters_html = _mute.colorize_mute_letters_html
colorize_numbers_position_html = _numbers.colorize_numbers_position_html
colorize_numbers_multicolor_html = _numbers.colorize_numbers_multicolor_html
colorize_numbers_in_html = _numbers.colorize_numbers_in_html
get_mute_positions = _mute.get_mute_positions

SYLL_WORD_PATTERN = getattr(_syllables, "SYLL_WORD_PATTERN", None)
HAVE_SYLLABLES = getattr(_syllables, "HAVE_SYLLABLES", False)


def colorize_syllables_and_mute_html(text: str) -> str:
    """Orchestre la coloration syllabique puis le grisage des lettres muettes.

    Comportement :
    - si aucun syllabiseur n'est disponible, retombe sur le grisage simple;
    - sinon, récupère les syllabes via `_syllables.get_syllables` puis applique
      les positions muettes fournies par `_mute.get_mute_positions` pour
      regrouper les caractères muets/non-muets et éviter les spans imbriqués.
    """
    if not text or not text.strip():
        return escape_html(text)

    if not HAVE_SYLLABLES or SYLL_WORD_PATTERN is None:
        return colorize_mute_letters_html(text)

    result: list[str] = []
    color_index = 0
    i = 0

    import re
    while i < len(text):
        m = SYLL_WORD_PATTERN.match(text, i)
        if not m:
            result.append(escape_html(text[i]))
            i += 1
            continue

        word = m.group(0)
        sylls = _syllables.get_syllables(word)
        if not sylls:
            result.append(escape_html(word))
            i = m.end()
            continue

        try:
            mute_pos = get_mute_positions(word, text)
        except Exception:
            mute_pos = set()

        pos = 0
        for syl in sylls:
            part = word[pos:pos + len(syl)]
            color = COLORS_SYLLABLES[color_index % len(COLORS_SYLLABLES)]

            # regrouper muets / non-muets
            buf = []
            buf_muted = None
            chunks: list[str] = []
            for k, ch in enumerate(part):
                gidx = pos + k
                is_muted = gidx in mute_pos
                if buf_muted is None:
                    buf_muted = is_muted
                    buf.append(ch)
                elif is_muted == buf_muted:
                    buf.append(ch)
                else:
                    s = "".join(buf)
                    if buf_muted:
                        chunks.append(f"<span style='color:{COLOR_MUTE}'>" + escape_html(s) + "</span>")
                    else:
                        chunks.append(f"<span style='color:{color}'>" + escape_html(s) + "</span>")
                    buf = [ch]
                    buf_muted = is_muted

            if buf:
                s = "".join(buf)
                if buf_muted:
                    chunks.append(f"<span style='color:{COLOR_MUTE}'>" + escape_html(s) + "</span>")
                else:
                    chunks.append(f"<span style='color:{color}'>" + escape_html(s) + "</span>")

            result.append("".join(chunks))
            color_index += 1
            pos += len(part)

        if pos < len(word):
            rest = word[pos:]
            color = COLORS_SYLLABLES[color_index % len(COLORS_SYLLABLES)]
            result.append(f"<span style='color:{color}'>{escape_html(rest)}</span>")
            color_index += 1

        i = m.end()

    return "".join(result)

