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

# Exceptions et cas particuliers (copiés/adaptés)
EXCEPTIONS_B = {
    "rib", "blob", "club", "pub", "kebab", "nabab", "snob", "toubib",
    "baobab", "jazzclub", "motoclub", "night-club"
}
EXCEPTIONS_G = {
    "grog", "ring", "bang", "gong", "yang", "ying", "slang", "gang", "erg",
    "iceberg", "zig", "zigzag", "krieg", "bowling", "briefing", "shopping",
    "building", "camping", "parking", "living", "marketing", "dancing",
    "jogging", "surfing", "training", "meeting", "feeling", "holding",
    "standing", "trading"
}
EXCEPTIONS_P = {
    "stop", "workshop", "handicap", "wrap", "ketchup", "top", "flip-flop",
    "hip-hop", "clip", "slip", "trip", "grip", "strip", "shop", "drop",
    "hop", "pop", "flop", "chop", "prop", "crop", "laptop", "desktop"
}
EXCEPTIONS_T = {
    "but", "chut", "fiat", "brut", "concept", "foot", "huit", "mat", "net",
    "ouest", "rut", "out", "ut", "flirt", "kurt", "loft", "raft", "rift",
    "soft", "watt", "west", "abstract", "affect", "apart", "audit", "belt",
    "best", "blast", "boost", "compact", "connect", "contact", "correct",
    "cost", "craft", "cut", "direct", "district", "draft", "drift", "exact",
    "exit", "impact", "infect", "input", "must", "next", "night", "outfit",
    "output", "paint", "perfect", "plot", "post", "print", "prompt",
    "prospect", "react", "root", "set", "shirt", "short", "shot", "smart",
    "spirit", "split", "spot", "sprint", "start", "strict", "tact", "test",
    "tilt", "tract", "trust", "twist", "volt", "et", "est"
}
EXCEPTIONS_X = {
    "six", "dix", "index", "duplex", "latex", "lynx", "matrix", "mix",
    "multiplex", "reflex", "relax", "remix", "silex", "thorax", "vortex", "xerox"
}
EXCEPTIONS_S = {
    "bus", "ours", "tous", "plus", "ars", "cursus", "lapsus", "virus",
    "cactus", "consensus", "us", "as", "mas", "bis", "lys", "métis", "os",
    "bonus", "campus", "focus", "boss", "stress", "express", "dress",
    "fitness", "Arras", "s", "houmous", "humus", "humérus", "cubitus", "habitus",
    "hiatus", "des", "mes", "tes", "ces", "les", "ses"
}

EXCEPTIONS_D = {"david"}

CAS_PARTICULIERS = {
    "croc": "c", "crocs": "cs",
    "clef": "f", "clefs": "fs",
    "cerf": "f", "cerfs": "fs",
    "boeuf": "fs", "bœuf": "fs", "boeufs": "fs", "bœufs": "fs",
    "oeuf": "fs", "œuf": "fs", "oeufs": "fs", "œufs": "fs"
}

# ARTICLES pattern (pour règle 'tous + déterminant')
ARTICLES = [
    "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux",
    "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
    "notre", "nos", "votre", "vos", "ce", "cet", "cette", "ces",
    "quelques", "chaque", "tout", "tous"
]
ARTICLES_RE = _re.compile(r"\b[tT]ous\s+(?:" + "|".join(_re.escape(a) for a in ARTICLES) + r")\b", _re.IGNORECASE)


def is_tous_followed_by_article(sentence: str) -> bool:
    if not sentence:
        return False
    return bool(ARTICLES_RE.search(sentence))


def _prev_non_punct(doc, i, sent_start):
    j = i - 1
    while j >= sent_start:
        if not doc[j].is_punct:
            return doc[j]
        j -= 1
    return None


def _next_non_punct(doc, i, sent_end):
    j = i + 1
    while j < sent_end:
        if not doc[j].is_punct:
            return doc[j]
        j += 1
    return None


def is_verb(word: str, sentence: str) -> bool:
    if not SPACY_OK or not sentence:
        return False
    try:
        doc = _nlp(sentence)
        for token in doc:
            if token.text.lower() == word.lower():
                return token.pos_ == "VERB"
    except Exception:
        return False
    return False


def is_negation_plus(sentence: str, word: str) -> bool:
    if not SPACY_OK or not sentence:
        return False
    try:
        doc = _nlp(sentence)
    except Exception:
        return False

    idx_plus = None
    for i, t in enumerate(doc):
        if t.text.lower() == word.lower():
            idx_plus = i
            break
    if idx_plus is None:
        return False

    plus_tok = doc[idx_plus]
    sent = plus_tok.sent
    sent_start = sent.start
    sent_end = sent.end

    max_prev = 4
    prev_tokens = []
    j = plus_tok.i - 1
    while j >= sent_start and len(prev_tokens) < max_prev:
        if not doc[j].is_punct:
            prev_tokens.append(doc[j])
        j -= 1

    neg_tokens = [tok for tok in prev_tokens if tok.text.lower() in {"ne", "n'"} or getattr(tok, "dep_,", "") == "neg"]
    if neg_tokens:
        neg_tok = neg_tokens[0]
        if any(tok.pos_ == "VERB" for tok in sent if neg_tok.i < tok.i < plus_tok.i):
            return True
        next_tok = _next_non_punct(doc, plus_tok.i, sent_end)
        if next_tok is not None and next_tok.pos_ == "VERB":
            return True

    return False


def is_plus_relevant(sentence: str, word: str) -> bool:
    if not SPACY_OK or not sentence:
        return False
    try:
        doc = _nlp(sentence)
    except Exception:
        return False

    for t in doc:
        if t.text.lower() == word.lower():
            sent = t.sent
            left = _prev_non_punct(doc, t.i, sent.start)
            right = _next_non_punct(doc, t.i, sent.end)

            def is_number(tok):
                return getattr(tok, "like_num", False) or tok.pos_ == "NUM"

            if left is not None and right is not None:
                if is_number(left) and is_number(right):
                    return False
                if left.pos_ == "PRON" and right.pos_ == "PRON":
                    return False
                if left.pos_ in {"NOUN", "PROPN"} and right.pos_ in {"NOUN", "PROPN"}:
                    return False

            return is_negation_plus(sentence, word)
    return False


def is_tous_determiner(sentence: str, word: str) -> bool:
    return is_tous_followed_by_article(sentence)


def is_proper_noun(sentence: str, word: str) -> bool:
    if not sentence:
        return False

    # spaCy
    if SPACY_OK:
        try:
            doc = _nlp(sentence)
            for token in doc:
                if token.text.lower() == word.lower():
                    if token.pos_ == "PROPN":
                        return True
                    if getattr(token, "ent_type_,", "") in {"PER", "PERSON"}:
                        return True
        except Exception:
            pass

    # fallback: Titlecase
    if word and word[0].isupper():
        return True

    return False


def get_mute_positions(word: str, sentence: str = None) -> Set[int]:
    w = word.lower()
    positions: Set[int] = set()

    if sentence and is_proper_noun(sentence, word):
        return positions

    if w in CAS_PARTICULIERS:
        for c in CAS_PARTICULIERS[w]:
            idx = w.rfind(c)
            if idx != -1:
                positions.add(idx)
        return positions

    if w and w[0] == "h":
        positions.add(0)

    if w.endswith("ent") and sentence and is_verb(w, sentence):
        positions.add(len(w) - 2)
        positions.add(len(w) - 1)

    if w == "plus" and sentence and is_plus_relevant(sentence, w):
        positions.add(len(w) - 1)
        return positions

    if w == "tous" and sentence and is_tous_followed_by_article(sentence):
        positions.add(len(w) - 1)
        return positions

    if w.endswith("aient") and w != "aient":
        positions.add(len(w) - 3)
        positions.add(len(w) - 2)
        positions.add(len(w) - 1)
        return positions

    last = len(w) - 1
    if last < 0:
        return positions

    if w[last] == "d" and w in EXCEPTIONS_D:
        pass
    elif w[last] == "d":
        positions.add(last)

    if w[last] == "b" and w not in EXCEPTIONS_B:
        positions.add(last)

    if w.endswith(("ie", "ée")):
        positions.add(last)
    elif w.endswith("ue"):
        if not (w.endswith("gue") or w.endswith("que")):
            positions.add(last)

    if w[last] == "g" and w not in EXCEPTIONS_G:
        positions.add(last)
    if w[last] == "p" and w not in EXCEPTIONS_P:
        positions.add(last)
    if w[last] == "t" and w not in EXCEPTIONS_T:
        positions.add(last)
    if w[last] == "x" and w not in EXCEPTIONS_X:
        positions.add(last)
    if w[last] == "s" and w not in EXCEPTIONS_S:
        positions.add(last)
        if len(w) > 1:
            prev = w[:-1]
            prev_pos = get_mute_positions(prev, sentence)
            for p in prev_pos:
                positions.add(p)

    return positions

# --- fin portage ---


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
