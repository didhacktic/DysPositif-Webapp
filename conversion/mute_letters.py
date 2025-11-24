"""Règles et helpers pour déterminer les lettres muettes à griser.
Expose : get_mute_positions(word, sentence=None) -> Set[int]
et colorize_mute_letters_html(text) pour appliquer un traitement simple sur du texte brut.
"""
from __future__ import annotations
import re
from typing import Set
from .conversion_models import COLOR_MUTE
from .utils_html import escape_html

# spaCy: tentative de chargement du modèle français (fallback silencieux)
try:
    import spacy
    _nlp = spacy.load("fr_core_news_md")
    SPACY_OK = True
except Exception:
    _nlp = None
    SPACY_OK = False

# Exceptions et cas particuliers
EXC_B = {"rib", "blob", "club", "pub", "kebab", "nabab", "snob", "toubib", "baobab", "jazzclub", "motoclub", "night-club"}
EXC_G = {"grog", "ring", "bang", "gong", "yang", "ying", "slang", "gang", "erg", "iceberg", "zig", "zigzag", "krieg", "bowling", "briefing", "shopping", "building", "camping", "parking", "living", "marketing", "dancing", "jogging", "surfing", "training", "meeting", "feeling", "holding", "standing", "trading"}
EXC_P = {"stop", "workshop", "handicap", "wrap", "ketchup", "top", "flip-flop", "hip-hop", "clip", "slip", "trip", "grip", "strip", "shop", "drop", "hop", "pop", "flop", "chop", "prop", "crop", "laptop", "desktop"}
EXC_T = {"et", "est", "but", "chut", "fiat", "brut", "concept", "foot", "huit", "mat", "net", "ouest", "rut", "out", "ut", "flirt", "kurt", "loft", "raft", "rift", "soft", "watt", "west", "abstract", "affect", "apart", "audit", "belt", "best", "blast", "boost", "compact", "connect", "contact", "correct", "cost", "craft", "cut", "direct", "district", "draft", "drift", "exact", "exit", "impact", "infect", "input", "must", "next", "night", "outfit", "output", "paint", "perfect", "plot", "post", "print", "prompt", "prospect", "react", "root", "set", "shirt", "short", "shot", "smart", "spirit", "split", "spot", "sprint", "start", "strict", "tact", "test", "tilt", "tract", "trust", "twist", "volt"}
EXC_X = {"six", "dix", "index", "duplex", "latex", "lynx", "matrix", "mix", "multiplex", "reflex", "relax", "remix", "silex", "thorax", "vortex", "xerox"}
EXC_S = {"bus", "ours", "ars", "cursus", "lapsus", "virus", "cactus", "consensus", "us", "as", "mas", "bis", "lys", "métis", "os", "bonus", "campus", "focus", "boss", "stress", "express", "dress", "fitness"}

CAS_PARTICULIERS = {
    "croc": "c", "crocs": "cs",
    "clef": "f", "clefs": "fs",
    "cerf": "f", "cerfs": "fs",
    "boeuf": "fs", "bœuf": "fs", "boeufs": "fs", "bœufs": "fs",
    "oeuf": "fs", "œuf": "fs", "oeufs": "fs", "œufs": "fs"
}

# tokenisation simple pour traitement mot-à-mot
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’\-][A-Za-zÀ-ÖØ-öø-ÿ]+)*")


def _find_token_for_word(doc, word_lower: str):
    for t in doc:
        if t.text.lower() == word_lower:
            return t
    return None


def _apply_final_letter_rules(base_word: str, positions: set, original_len: int):
    if not base_word:
        return
    last = len(base_word) - 1
    last_char = base_word[last]

    if last_char == 'd':
        positions.add(original_len - 1)
        return
    if last_char == 'b' and base_word not in EXC_B:
        positions.add(original_len - 1)
        return
    if last_char == 'e' and len(base_word) >= 2:
        prev = base_word[-2]
        if prev in {'i', 'é', 'u'} and not (base_word.endswith('gue') or base_word.endswith('que')):
            positions.add(original_len - 1)
            return
    if last_char == 'g' and base_word not in EXC_G:
        positions.add(original_len - 1)
        return
    if last_char == 'p' and base_word not in EXC_P:
        positions.add(original_len - 1)
        return
    if last_char == 't' and base_word not in EXC_T:
        positions.add(original_len - 1)
        return
    if last_char == 'x' and base_word not in EXC_X:
        positions.add(original_len - 1)
        return


def _is_plus_to_gray(doc, token):
    prev = token.nbor(-1) if token.i > token.sent.start else None
    if prev is not None and (prev.text.lower() in {"ne", "n'"} or prev.dep_ == 'neg'):
        return True
    try:
        nxt = token.nbor(1) if token.i + 1 < token.sent.end else None
        if nxt is not None and nxt.pos_ in {"ADJ", "ADV"}:
            return True
    except Exception:
        pass
    try:
        if nxt is not None and (getattr(nxt, 'like_num', False) or nxt.pos_ == 'NUM'):
            return True
        if nxt is not None and nxt.pos_ == 'DET':
            nxt2 = token.nbor(2) if token.i + 2 < token.sent.end else None
            if nxt2 is not None and nxt2.pos_ in {"NOUN", "NUM"}:
                return True
    except Exception:
        pass
    for t in token.sent:
        if t.i != token.i and t.text.lower() == 'plus':
            return True
    return False


def _is_tous_pronoun(doc, token):
    return token.pos_ == 'PRON'


def get_mute_positions(word: str, sentence: str | None = None) -> Set[int]:
    if not word:
        return set()
    original = word
    wn = word.lower()
    positions: Set[int] = set()
    if wn in CAS_PARTICULIERS:
        suffix = CAS_PARTICULIERS[wn]
        if wn.endswith(suffix):
            for k in range(len(suffix)):
                positions.add(len(original) - len(suffix) + k)
        return positions
    if wn and wn[0] == 'h':
        positions.add(0)
    doc = None
    token = None
    if SPACY_OK and sentence:
        try:
            doc = _nlp(sentence)
            token = _find_token_for_word(doc, wn)
        except Exception:
            doc = None
            token = None
    if wn.endswith('ent'):
        if doc is not None and token is not None and token.pos_ == 'VERB':
            if wn.endswith('aient') and wn != 'aient':
                for k in range(3):
                    positions.add(len(original) - 3 + k)
                return positions
            else:
                positions.add(len(original) - 2)
                positions.add(len(original) - 1)
                return positions
        else:
            if wn.endswith('aient') and wn != 'aient':
                for k in range(3):
                    positions.add(len(original) - 3 + k)
                return positions
    if wn == 'tous' and doc is not None and token is not None:
        if not _is_tous_pronoun(doc, token):
            positions.add(len(original) - 1)
        return positions
    if wn == 'plus':
        if doc is not None and token is not None:
            if _is_plus_to_gray(doc, token):
                positions.add(len(original) - 1)
                return positions
        else:
            if sentence:
                low = sentence.lower()
                if (" ne plus" in low) or ("n'plus" in low) or any(n in low for n in [" ne ", " n'"]):
                    positions.add(len(original) - 1)
                    return positions
    if wn.endswith('s') and len(wn) > 1:
        if wn not in EXC_S:
            positions.add(len(original) - 1)
            base = wn[:-1]
            _apply_final_letter_rules(base, positions, len(original) - 1)
        return positions
    _apply_final_letter_rules(wn, positions, len(original))
    return positions


def colorize_mute_letters_html(text: str) -> str:
    """Applique grisage simple sur texte brut en utilisant get_mute_positions."""
    if not text or not text.strip():
        return escape_html(text)
    from .syllables import SYLL_WORD_PATTERN
    if SYLL_WORD_PATTERN is None:
        pattern = re.compile(r'\b(\w*[aeiouyéèêëàâôù])([stdxe])\b', re.IGNORECASE)

        def replacer(m):
            prefix = m.group(1)
            mute = m.group(2)
            return f"{escape_html(prefix)}<span style='color:{COLOR_MUTE}'>{escape_html(mute)}</span>"

        return pattern.sub(replacer, escape_html(text))

    result = []
    i = 0
    while i < len(text):
        match = WORD_RE.match(text, i)
        if match:
            word = match.group(0)
            try:
                positions = get_mute_positions(word, text)
            except Exception:
                positions = set()
            parts = []
            for idx, ch in enumerate(word):
                if idx in positions:
                    parts.append(f"<span style='color:{COLOR_MUTE}'>" + escape_html(ch) + "</span>")
                else:
                    parts.append(escape_html(ch))
            result.append(''.join(parts))
            i = match.end()
        else:
            result.append(escape_html(text[i]))
            i += 1
    return ''.join(result)
