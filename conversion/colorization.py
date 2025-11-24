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

# --- Portage des règles de grisage des lettres muettes depuis core/mute_letters.py ---
import re as _re
from typing import Set

# spaCy: tentative de chargement du modèle français (fallback silencieux)
try:
    import spacy as _spacy
    _nlp = _spacy.load("fr_core_news_md")
    SPACY_OK = True
except Exception as _e:
    _nlp = None
    SPACY_OK = False

# Exceptions et cas particuliers (définis strictement selon la spécification utilisateur)
EXC_B = {"rib", "blob", "club", "pub", "kebab", "nabab", "snob", "toubib", "baobab", "jazzclub", "motoclub", "night-club"}
EXC_G = {"grog", "ring", "bang", "gong", "yang", "ying", "slang", "gang", "erg", "iceberg", "zig", "zigzag", "krieg", "bowling", "briefing", "shopping", "building", "camping", "parking", "living", "marketing", "dancing", "jogging", "surfing", "training", "meeting", "feeling", "holding", "standing", "trading"}
EXC_P = {"stop", "workshop", "handicap", "wrap", "ketchup", "top", "flip-flop", "hip-hop", "clip", "slip", "trip", "grip", "strip", "shop", "drop", "hop", "pop", "flop", "chop", "prop", "crop", "laptop", "desktop"}
EXC_T = {"sept", "et", "est", "but", "chut", "fiat", "brut", "concept", "foot", "huit", "mat", "net", "ouest", "rut", "out", "ut", "flirt", "kurt", "loft", "raft", "rift", "soft", "watt", "west", "abstract", "affect", "apart", "audit", "belt", "best", "blast", "boost", "compact", "connect", "contact", "correct", "cost", "craft", "cut", "direct", "district", "draft", "drift", "exact", "exit", "impact", "infect", "input", "must", "next", "night", "outfit", "output", "paint", "perfect", "plot", "post", "print", "prompt", "prospect", "react", "root", "set", "shirt", "short", "shot", "smart", "spirit", "split", "spot", "sprint", "start", "strict", "tact", "test", "tilt", "tract", "trust", "twist", "volt"}
EXC_X = {"six", "dix", "index", "duplex", "latex", "lynx", "matrix", "mix", "multiplex", "reflex", "relax", "remix", "silex", "thorax", "vortex", "xerox"}
EXC_S = {"bus", "ours", "ars", "cursus", "lapsus", "virus", "cactus", "consensus", "us", "as", "mas", "bis", "lys", "métis", "os", "bonus", "campus", "focus", "boss", "stress", "express", "dress", "fitness", "s", "houmous", "humus", "humérus", "cubitus", "habitus", "hiatus", "des", "mes", "tes", "ces", "les", "ses"}

CAS_PARTICULIERS = {
    "croc": "c", "crocs": "cs",
    "clef": "f", "clefs": "fs",
    "cerf": "f", "cerfs": "fs",
    "boeuf": "fs", "bœuf": "fs", "boeufs": "fs", "bœufs": "fs",
    "oeuf": "fs", "œuf": "fs", "oeufs": "fs", "œufs": "fs"
}

# tokenisation simple pour traitement mot-à-mot
WORD_RE = _re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’\-][A-Za-zÀ-ÖØ-öø-ÿ]+)*")


def _find_token_for_word(doc, word_lower: str):
    """Retourne le premier token du doc dont .text.lower() == word_lower, ou None."""
    for t in doc:
        if t.text.lower() == word_lower:
            return t
    return None


def _apply_final_letter_rules(base_word: str, positions: set, original_len: int):
    """Applique les règles 2,3,4,5,7,8,9 sur le dernier caractère de base_word.
    base_word doit être en minuscules. positions sont indices relatifs à la chaîne d'origine.
    original_len est la longueur du mot original pour calculer indices absolus.
    """
    if not base_word:
        return
    last = len(base_word) - 1
    last_char = base_word[last]

    # règle 3: d final => toujours grisé
    if last_char == 'd':
        positions.add(original_len - 1)
        return

    # règle 2: b final sauf listes
    if last_char == 'b' and base_word not in EXC_B:
        positions.add(original_len - 1)
        return

    # règle 4: e final si précédé de i, é, u, sauf -gue/-que
    if last_char == 'e' and len(base_word) >= 2:
        prev = base_word[-2]
        if prev in {'i', 'é', 'u'} and not (base_word.endswith('gue') or base_word.endswith('que')):
            positions.add(original_len - 1)
            return

    # règle 5: g final sauf exceptions
    if last_char == 'g' and base_word not in EXC_G:
        positions.add(original_len - 1)
        return

    # règle 7: p final sauf exceptions
    if last_char == 'p' and base_word not in EXC_P:
        positions.add(original_len - 1)
        return

    # règle 8: t final sauf exceptions
    if last_char == 't' and base_word not in EXC_T:
        positions.add(original_len - 1)
        return

    # règle 9: x final sauf exceptions
    if last_char == 'x' and base_word not in EXC_X:
        positions.add(original_len - 1)
        return


def _is_plus_to_gray(doc, token):
    """Décide si 'plus' doit voir son 's' grisé selon les conditions (règle 14)."""
    # token est un token spacy identifié pour 'plus'
    # 1) précédé d'une négation
    prev = token.nbor(-1) if token.i > token.sent.start else None
    if prev is not None and (prev.text.lower() in {"ne", "n'"} or prev.dep_ == 'neg'):
        return True

    # 2) suivi d'un adj ou adv
    try:
        nxt = token.nbor(1) if token.i + 1 < token.sent.end else None
        if nxt is not None and nxt.pos_ in {"ADJ", "ADV"}:
            return True
    except Exception:
        pass

    # 3) suivi d'une quantité
    try:
        if nxt is not None and (getattr(nxt, 'like_num', False) or nxt.pos_ == 'NUM'):
            return True
        # heuristique: article + nom quantitatif -> check deux tokens suivants
        if nxt is not None and nxt.pos_ == 'DET':
            nxt2 = token.nbor(2) if token.i + 2 < token.sent.end else None
            if nxt2 is not None and nxt2.pos_ in {"NOUN", "NUM"}:
                return True
    except Exception:
        pass

    # 4) motif 'plus ... plus' : si on trouve un autre 'plus' dans la même phrase
    for t in token.sent:
        if t.i != token.i and t.text.lower() == 'plus':
            return True

    return False


def _is_tous_pronoun(doc, token):
    # si spaCy indique PRON pour tous
    return token.pos_ == 'PRON'


def get_mute_positions(word: str, sentence: str | None = None) -> Set[int]:
    """Retourne indices (0-based) des caractères à griser dans `word` selon règles.
    `sentence` est optionnel, utile pour décisions contextuelles (spaCy).
    """
    if not word:
        return set()

    original = word
    wn = word.lower()
    positions: Set[int] = set()

    # Normalize simple composed words: treat as literal when in CAS_PARTICULIERS
    if wn in CAS_PARTICULIERS:
        suffix = CAS_PARTICULIERS[wn]
        if wn.endswith(suffix):
            for k in range(len(suffix)):
                positions.add(len(original) - len(suffix) + k)
        return positions

    # règle 1: h initial
    if wn and wn[0] == 'h':
        positions.add(0)

    # Préparer doc spaCy si nécessaire
    doc = None
    token = None
    if SPACY_OK and sentence:
        try:
            doc = _nlp(sentence)
            token = _find_token_for_word(doc, wn)
        except Exception:
            doc = None
            token = None

    # règle 12: traitement des mots en -ent
    if wn.endswith('ent'):
        if doc is not None and token is not None and token.pos_ == 'VERB':
            # verbe détecté
            if wn.endswith('aient') and wn != 'aient':
                # griser 'ent' entier
                for k in range(3):
                    positions.add(len(original) - 3 + k)
                return positions
            else:
                # griser 'nt' (deux derniers caractères)
                positions.add(len(original) - 2)
                positions.add(len(original) - 1)
                return positions
        else:
            # spaCy absent ou token non-verbe -> fallback: if endswith 'aient' griser ent, sinon fallthrough
            if wn.endswith('aient') and wn != 'aient':
                for k in range(3):
                    positions.add(len(original) - 3 + k)
                return positions

    # règle 13: 'tous' spécial
    if wn == 'tous' and doc is not None and token is not None:
        if not _is_tous_pronoun(doc, token):
            positions.add(len(original) - 1)
        return positions

    # règle 14: 'plus' spécial
    if wn == 'plus':
        if doc is not None and token is not None:
            if _is_plus_to_gray(doc, token):
                positions.add(len(original) - 1)
                return positions
        else:
            # heuristic: look for "ne" before or digit after in sentence text
            if sentence:
                low = sentence.lower()
                if (" ne plus" in low) or ("n'plus" in low) or any(n in low for n in [" ne ", " n'"]):
                    positions.add(len(original) - 1)
                    return positions

    # règles générales sur la lettre finale
    # on travaille sur base (mot sans le 's' final si on doit traiter pluriel plus tard)
    if wn.endswith('s') and len(wn) > 1:
        # décision de griser le 's' selon EXC_S
        if wn not in EXC_S:
            positions.add(len(original) - 1)  # griser le s
            # règle 11: appliquer règles finales sur la lettre précédente
            base = wn[:-1]
            _apply_final_letter_rules(base, positions, len(original) - 1)
        # sinon, ne rien faire pour le s
        return positions

    # si on est ici, mot ne finit pas par 's' (ou c'est un 's' isolé traité plus haut)
    _apply_final_letter_rules(wn, positions, len(original))

    return positions

# --- fin implémentation complète des règles ---


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
    # If we don't have a word tokenizer/syllabizer, fallback to previous regex-based method
    if SYLL_WORD_PATTERN is None:
        import re
        pattern = re.compile(r'\b(\w*[aeiouyéèêëàâôù])([stdxe])\b', re.IGNORECASE)

        def replacer(m):
            prefix = m.group(1)
            mute = m.group(2)
            return f"{escape_html(prefix)}<span style='color:{COLOR_MUTE}'>{escape_html(mute)}</span>"

        return pattern.sub(replacer, escape_html(text))

    # Otherwise iterate words and apply spaCy/heuristic detection per-word
    result = []
    i = 0
    while i < len(text):
        match = SYLL_WORD_PATTERN.match(text, i)
        if match:
            word = match.group(0)
            try:
                positions = get_mute_positions(word, text)
            except Exception:
                positions = set()

            # build html for the word: wrap muted chars individually
            word_html_parts = []
            for idx, ch in enumerate(word):
                if idx in positions:
                    word_html_parts.append(f"<span style='color:{COLOR_MUTE}'>" + escape_html(ch) + "</span>")
                else:
                    word_html_parts.append(escape_html(ch))

            result.append(''.join(word_html_parts))
            i = match.end()
        else:
            result.append(escape_html(text[i]))
            i += 1

    return ''.join(result)


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
                    try:
                        mute_positions = get_mute_positions(word, text)
                    except Exception:
                        mute_positions = set()

                    pos = 0
                    for idx, syl in enumerate(syllables_list):
                        syl_len = len(syl)
                        part = word[pos:pos+syl_len] if pos+syl_len <= len(word) else word[pos:]

                        color = COLORS_SYLLABLES[color_index % len(COLORS_SYLLABLES)]

                        # build syl html respecting muted characters
                        part_html_chunks = []
                        chunk_buf = []
                        chunk_is_muted = None
                        for k, ch in enumerate(part):
                            global_idx = pos + k
                            is_muted = global_idx in mute_positions
                            if chunk_is_muted is None:
                                chunk_is_muted = is_muted
                                chunk_buf.append(ch)
                            elif is_muted == chunk_is_muted:
                                chunk_buf.append(ch)
                            else:
                                # flush
                                s = ''.join(chunk_buf)
                                if chunk_is_muted:
                                    part_html_chunks.append(f"<span style='color:{COLOR_MUTE}'>" + escape_html(s) + "</span>")
                                else:
                                    part_html_chunks.append(f"<span style='color:{color}'>" + escape_html(s) + "</span>")
                                chunk_buf = [ch]
                                chunk_is_muted = is_muted

                        # flush remaining
                        if chunk_buf:
                            s = ''.join(chunk_buf)
                            if chunk_is_muted:
                                part_html_chunks.append(f"<span style='color:{COLOR_MUTE}'>" + escape_html(s) + "</span>")
                            else:
                                part_html_chunks.append(f"<span style='color:{color}'>" + escape_html(s) + "</span>")

                        result.append(''.join(part_html_chunks))
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
