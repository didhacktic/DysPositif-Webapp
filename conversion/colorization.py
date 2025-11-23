"""Fonctions de coloration pour adaptation dyslexie (syllabes, lettres muettes, nombres).
Externalisé du script monolithique pour modularisation.
"""
from __future__ import annotations
from .conversion_models import COLORS_SYLLABLES, COLOR_MUTE, COLORS_NUMBERS_POS, COLORS_NUMBERS_MULTI

# Import syllabisation via paquet PyPI lirecouleur (pylirecouleur)
try:
    from lirecouleur.word import syllables as syllabize_word  # type: ignore
    import re
    # Mot français simplifié (lettres + accents + apostrophe interne)
    SYLL_WORD_PATTERN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:'[A-Za-zÀ-ÖØ-öø-ÿ]+)?")
    HAVE_SYLLABLES = True
except ImportError as e:
    HAVE_SYLLABLES = False
    SYLL_WORD_PATTERN = None
    print(f"[WARN] Module 'lirecouleur.word' non disponible, syllabisation désactivée: {e}")


def escape_html(s: str) -> str:
    """Échappe entités HTML basiques."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace("\"", "&quot;"))


def colorize_syllables_html(text: str) -> str:
    """Applique coloration syllabique alternée rouge/bleu sur texte."""
    if not HAVE_SYLLABLES or not text.strip():
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
                syllables_list = syllabize_word(word.lower())
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


def colorize_mute_letters_html(text: str) -> str:
    """Applique grisage sur lettres muettes finales (heuristique simplifiée regex)."""
    if not text.strip():
        return escape_html(text)
    
    import re
    pattern = re.compile(r'\b(\w*[aeiouyéèêëàâôù])([stdxe])\b', re.IGNORECASE)
    
    def replacer(m):
        prefix = m.group(1)
        mute = m.group(2)
        return f"{escape_html(prefix)}<span style='color:{COLOR_MUTE}'>{escape_html(mute)}</span>"
    
    return pattern.sub(replacer, escape_html(text))


def colorize_syllables_and_mute_html(text: str) -> str:
    """Applique syllabique + muettes en HTML (syllabes colorées + override gris sur lettres finales)."""
    if not HAVE_SYLLABLES or not text.strip():
        return escape_html(text)
    
    import re
    result = []
    color_index = 0
    i = 0
    
    mute_pattern = re.compile(r'([aeiouyéèêëàâôù])([stdxe])$', re.IGNORECASE)
    
    while i < len(text):
        match = SYLL_WORD_PATTERN.match(text, i)
        if match:
            word = match.group(0)
            word_lower = word.lower()
            
            try:
                syllables_list = syllabize_word(word_lower)
                if not syllables_list:
                    result.append(escape_html(word))
                else:
                    mute_match = mute_pattern.search(word_lower)
                    has_mute = mute_match is not None
                    mute_letter = mute_match.group(2) if has_mute else None
                    
                    pos = 0
                    for idx, syl in enumerate(syllables_list):
                        syl_len = len(syl)
                        part = word[pos:pos+syl_len] if pos+syl_len <= len(word) else word[pos:]
                        
                        is_last_syl = (idx == len(syllables_list) - 1)
                        part_lower = part.lower()
                        
                        if has_mute and is_last_syl and part_lower.endswith(mute_letter):
                            main_part = part[:-1]
                            mute_part = part[-1]
                            
                            if main_part:
                                color = COLORS_SYLLABLES[color_index % len(COLORS_SYLLABLES)]
                                result.append(f"<span style='color:{color}'>{escape_html(main_part)}</span>")
                            
                            result.append(f"<span style='color:{COLOR_MUTE}'>{escape_html(mute_part)}</span>")
                        else:
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


def colorize_numbers_position_html(text: str) -> str:
    """Colore chiffres selon position décimale (unités, dizaines, centaines...)."""
    if not text.strip():
        return escape_html(text)
    
    import re
    pattern = re.compile(r'\d+')
    
    result = []
    last_end = 0
    
    for match in pattern.finditer(text):
        result.append(escape_html(text[last_end:match.start()]))
        
        num_str = match.group(0)
        colored_digits = []
        for i, digit in enumerate(reversed(num_str)):
            color = COLORS_NUMBERS_POS[i % len(COLORS_NUMBERS_POS)]
            colored_digits.insert(0, f"<span style='color:{color}'>{digit}</span>")
        result.append(''.join(colored_digits))
        
        last_end = match.end()
    
    result.append(escape_html(text[last_end:]))
    
    return ''.join(result)


def colorize_numbers_multicolor_html(text: str) -> str:
    """Colore chaque chiffre avec couleur arc-en-ciel."""
    if not text.strip():
        return escape_html(text)
    
    import re
    pattern = re.compile(r'\d+')
    
    result = []
    last_end = 0
    
    for match in pattern.finditer(text):
        result.append(escape_html(text[last_end:match.start()]))
        
        num_str = match.group(0)
        colored_digits = []
        # Nouvelle logique : couleur fixe par chiffre (0..9)
        for digit in num_str:
            try:
                idx = int(digit)
                color = COLORS_NUMBERS_MULTI[idx]
            except Exception:
                # fallback: rotation sur la palette si caractère inattendu
                color = COLORS_NUMBERS_MULTI[0]
            colored_digits.append(f"<span style='color:{color}'>{digit}</span>")
        result.append(''.join(colored_digits))
        
        last_end = match.end()
    
    result.append(escape_html(text[last_end:]))
    
    return ''.join(result)


def colorize_numbers_in_html(html_text: str, use_position: bool, use_multicolor: bool) -> str:
    """Colore les nombres dans un HTML déjà généré (évite de colorer attributs/balises existantes).
    Découpe en segments texte/balise, ne traite que le texte pur."""
    import re
    
    segments = re.split(r'(<[^>]+>)', html_text)
    result = []
    
    for seg in segments:
        if seg.startswith('<'):
            result.append(seg)
        else:
            pattern = re.compile(r'(\d+)')
            
            def replacer(match):
                num_str = match.group(1)
                colored_digits = []
                
                if use_position:
                    for i, digit in enumerate(reversed(num_str)):
                        color = COLORS_NUMBERS_POS[i % len(COLORS_NUMBERS_POS)]
                        colored_digits.insert(0, f"<span style='color:{color}'>{digit}</span>")
                else:
                    # couleur fixe par chiffre : utiliser la valeur du chiffre comme index
                    for digit in num_str:
                        try:
                            idx = int(digit)
                            color = COLORS_NUMBERS_MULTI[idx]
                        except Exception:
                            color = COLORS_NUMBERS_MULTI[0]
                        colored_digits.append(f"<span style='color:{color}'>{digit}</span>")
                
                return ''.join(colored_digits)
            
            result.append(pattern.sub(replacer, seg))
    
    return ''.join(result)
