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
# 'plus' doit être géré par la logique contextuelle (spaCy/fallback),
# ne pas le griser systématiquement via la règle générique "endswith('s')".
EXC_S.add("plus")

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
    # look back a few tokens for negation markers (ne, n', etc.) or any token with dep_ == 'neg'
    try:
        # quick arithmetic/coordination exceptions:
        # NUM plus NUM -> do not gray (e.g. "sept plus huit")
        try:
            left = token.nbor(-1) if token.i > token.sent.start else None
            right = token.nbor(1) if token.i + 1 < token.sent.end else None
            if left is not None and right is not None:
                # numeric addition
                if (getattr(left, 'like_num', False) or left.pos_ == 'NUM') and (getattr(right, 'like_num', False) or right.pos_ == 'NUM'):
                    return False
                # noun/proper noun/pronoun coordination (e.g. "toi plus moi", "Pierre plus Paul") -> do not gray
                # also treat common noun + noun/adjective sequences as coordination
                # (e.g. "pain plus beurre") to avoid false positives when spaCy
                # tags the RHS as ADJ.
                if left.pos_ in {'NOUN', 'PROPN', 'PRON'} and right.pos_ in {'NOUN', 'PROPN', 'PRON', 'ADJ'}:
                    return False
        except Exception:
            pass

        # special fixed phrase: "de plus en plus" -> do not gray either occurrence
        try:
            prev1 = token.nbor(-1) if token.i > token.sent.start else None
            next1 = token.nbor(1) if token.i + 1 < token.sent.end else None
            next2 = token.nbor(2) if token.i + 2 < token.sent.end else None
            if prev1 is not None and next1 is not None and next2 is not None:
                if prev1.text.lower() == 'de' and next1.text.lower() == 'en' and next2.text.lower() == 'plus':
                    return False
        except Exception:
            pass
        # If previous token is 'en' (e.g. "trois en plus" / "en plus"), do not gray
        try:
            prev0 = token.nbor(-1) if token.i > token.sent.start else None
            if prev0 is not None and prev0.text.lower() == 'en':
                return False
        except Exception:
            pass

        # check tokens up to 3 positions to the left
        for offset in range(1, 4):
            if token.i - offset < token.sent.start:
                break
            prev = token.doc[token.i - offset]
            if prev is None:
                break
            if prev.text.lower() in {"ne", "n'", "n’"} or prev.dep_ == 'neg':
                return True
        # also check for any neg token in the sentence whose head relates to this token
        for t in token.sent:
            if t.dep_ == 'neg' and (t.head == token or t.head == token.head or token.head == t.head):
                return True
    except Exception:
        pass

    # look forward for context that indicates graying
    try:
        nxt = token.nbor(1) if token.i + 1 < token.sent.end else None
        # adjective/adverb after -> grisé (comparatif/qualificatif)
        if nxt is not None and nxt.pos_ in {"ADJ", "ADV"}:
            return True
    except Exception:
        nxt = None
    try:
        # number-like or numeric following -> grisé
        if nxt is not None and (getattr(nxt, 'like_num', False) or nxt.pos_ == 'NUM'):
            return True
        # DET (ex: "de") or ADP (preposition 'de') followed by NOUN/NUM -> grisé (ex: "plus de 10 km")
        if nxt is not None and nxt.pos_ in {'DET', 'ADP'}:
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


def get_mute_positions(word: str, sentence: str | None = None, token=None) -> Set[int]:
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
    # `token` can be provided by callers (per-occurrence token from spaCy).
    if SPACY_OK:
        # If caller provided a token, prefer its Doc to avoid reparsing the text.
        if token is not None and getattr(token, 'doc', None) is not None:
            doc = token.doc
        else:
            if sentence:
                try:
                    doc = _nlp(sentence)
                except Exception:
                    doc = None
        if doc is not None and token is None:
            try:
                token = _find_token_for_word(doc, wn)
            except Exception:
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

    # Pre-parse the entire text with spaCy once (if available) so we can locate
    # the exact token corresponding to each word occurrence. This avoids the
    # previous bug of always matching the first occurrence of a word.
    doc = None
    if SPACY_OK:
        try:
            doc = _nlp(text)
        except Exception:
            doc = None

    result = []
    i = 0
    while i < len(text):
        match = WORD_RE.match(text, i)
        if match:
            word = match.group(0)
            token_for_match = None
            if doc is not None:
                # try to find a token whose character offset falls within the match
                start_char = match.start()
                end_char = match.end()
                for t in doc:
                    if t.idx >= start_char and t.idx < end_char and t.text.lower() == word.lower():
                        token_for_match = t
                        break
            try:
                positions = get_mute_positions(word, text, token_for_match)
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
