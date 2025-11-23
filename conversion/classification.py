"""Classification de contenus PDF (titres, paragraphes, listes, tableaux).
Externalisé du script monolithique pour modularisation.
"""
from __future__ import annotations
import re
import statistics
from typing import List
from .conversion_models import ContentItem, TextBlock, TableBlock


def normalize_text(text: str) -> str:
    """Normalise texte: césures, espaces multiples, glyphes spéciaux."""
    import unicodedata
    
    # Normalisation Unicode NFC
    text = unicodedata.normalize('NFC', text)
    
    # Supprimer césures fin de ligne (trait d'union + espace/newline)
    text = re.sub(r'-\s*\n\s*', '', text)
    text = re.sub(r'\s*\n\s*', ' ', text)
    
    # Normaliser glyphes (puces, cases, italique math)
    result = []
    for ch in text:
        result.append(normalize_glyph_char(ch))
    text = ''.join(result)
    
    # Espaces multiples → simple
    text = re.sub(r'\s{2,}', ' ', text)
    
    return text.strip()


_BULLET_VARIANTS = {
    '•', '◦', '∙', '‣', '▪', '▫', '■', '□', '○'
}
_CHECKBOX_EMPTY_VARIANTS = {
    '□', '☐', '❏'
}
_CHECKBOX_FILLED_VARIANTS = {
    '☒', '✔', '✓', '✅', '❎', '☑'
}
_MATH_ITALIC_MAP = {
    '𝑓': 'f', '𝑔': 'g', '𝑁': 'N', '𝑥': 'x', '𝑛': 'n', '𝑦': 'y'
}

# Mapping pour glyphes hors-UNICODE standards souvent présents dans les PDFs
# (Private Use / embedded font glyphs). On mappe les codepoints fréquents vers
# des équivalents Unicode canoniques utilisés ailleurs dans le pipeline.
_PRIVATE_USE_MAP = {
    '\uf06f': '☐',  # glyphe extrait parfois depuis Wingdings / polices embarquées → case vide
    # Variantes PUA fréquentes rencontrées dans des PDFs (Wingdings / ZapfDingbats, etc.)
    # On mappe majoritairement vers la case vide canonique '☐'.
    '\uf0a8': '☐',
    '\uf0a3': '☐',
    '\uf0a4': '☐',
    '\uf0a5': '☐',
    '\uf0a6': '☐',
    '\uf0a7': '☐',
    '\uf0a9': '☐',
    '\uf0aa': '☐',
    '\uf0ab': '☐',
    '\uf0ac': '☐',
    '\uf0ad': '☐',
    '\uf0ae': '☐',
    '\uf0af': '☐',
    '\uf0b0': '☐',
    '\uf0b1': '☐',
    '\uf0b2': '☐',
    '\uf0b3': '☐',
    '\uf0b4': '☐',
    # Quelques variantes parfois utilisées pour cases cochées — normaliser en case cochée
    '\uf0a2': '☑',
    '\uf0b5': '☑',
}


def normalize_glyph_char(ch: str) -> str:
    """Normalise glyphes (puces, cases, italique math)."""
    # Gestion des glyphes Private Use (polices embarquées dans le PDF)
    if ch in _PRIVATE_USE_MAP:
        return _PRIVATE_USE_MAP[ch]
    if ch in _BULLET_VARIANTS:
        return '•'
    if ch in _CHECKBOX_EMPTY_VARIANTS:
        return '☐'
    if ch in _CHECKBOX_FILLED_VARIANTS:
        return '☑'
    if ch in _MATH_ITALIC_MAP:
        return _MATH_ITALIC_MAP[ch]
    return ch


def parse_exercises_table(text: str) -> List[List[str]]:
    """Extrait lignes multi 'Exercice N X points'."""
    if "Exercice" not in text or "points" not in text:
        return []
    pair_re = re.compile(r"(Exercice\s+\d+(?:\s*\([^)]*\))?)\s+(\d+)\s+(points?)", re.IGNORECASE)
    rows = []
    for m in pair_re.finditer(text):
        ex = m.group(1).strip()
        pts = m.group(2).strip() + " " + m.group(3).strip()
        rows.append([ex, pts])
    return rows


def is_numeric_row(text: str) -> bool:
    """Ligne courte numérique (table)."""
    tokens = [t for t in text.strip().split() if t]
    if len(tokens) < 2 or len(tokens) > 5:
        return False
    score = 0
    for t in tokens:
        if re.match(r"^[0-9]+$", t):
            score += 1
        elif re.match(r"^[0-9]+[.,][0-9]+$", t):
            score += 1
        elif re.match(r"^[𝑁𝑓𝑔𝑥𝑦𝑛Nfgxyn]{1}$", t):
            score += 1
    return score == len(tokens)


def classify_items(items: List[ContentItem], min_delta: float, max_heading_len: int, enable_titles: bool) -> List[tuple]:
    """Classifie items (titre, paragraphe, liste, image, table)."""
    if not items:
        return []
    
    sizes = [item.content.fontsize for item in items if item.type == 'text']
    if not sizes:
        return []
    median_size = statistics.median(sizes)
    result = []
    bullet_pattern = re.compile(r"^([•\-\*☐☑✓])\s+")
    current_page = -1
    
    current_table_rows: List[List[str]] = []
    current_table_page = -1
    table_start_y = 0.0
    table_order = 0
    
    def flush_table():
        nonlocal current_table_rows, result, table_start_y, current_table_page, table_order
        if current_table_rows:
            rows = current_table_rows
            page = current_table_page
            tb = TableBlock(page=page, order=table_order, y_coord=table_start_y, rows=rows, bbox=(0,0,0,0))
            result.append(("table", tb, page, tb))
            current_table_rows = []
    
    for item in items:
        if item.page != current_page:
            flush_table()
            if current_page >= 0:
                result.append(("page-break", None, current_page))
            current_page = item.page
        
        if item.type == 'image':
            result.append(("image", item.content, item.page, None))
        elif item.type == 'cluster-image':
            result.append(("cluster-image", item.content, item.page, None))
        elif item.type == 'text':
            text_clean = normalize_text(item.content.text)
            if not text_clean:
                continue
            
            if item.y_coord > 780:
                continue
            
            m = bullet_pattern.match(text_clean)
            ex_rows = parse_exercises_table(text_clean)
            
            if ex_rows:
                if not current_table_rows:
                    current_table_page = item.page
                    table_start_y = item.y_coord
                    table_order = item.order
                current_table_rows.extend(ex_rows)
                continue
            elif is_numeric_row(text_clean) and item.page == 6:
                if not current_table_rows or (current_table_page == item.page and abs(item.y_coord - table_start_y) < 50):
                    if not current_table_rows:
                        current_table_page = item.page
                        table_start_y = item.y_coord
                        table_order = item.order
                    current_table_rows.append(text_clean.split())
                    continue
            elif m:
                if current_table_rows:
                    flush_table()
                symbol = m.group(1)
                item_text = text_clean[m.end():].strip()
                result.append(("li", f"{symbol} {item_text}", item.page, item.content))
            elif enable_titles and item.content.fontsize - median_size >= min_delta and len(text_clean) <= max_heading_len:
                if current_table_rows:
                    flush_table()
                result.append(("h2", text_clean, item.page, item.content))
            else:
                if current_table_rows:
                    flush_table()
                result.append(("p", text_clean, item.page, item.content))
    
    flush_table()
    
    # Injection scoreboard exercices
    scoreboard_pages = {}
    exercise_pattern = re.compile(r"(Exercice\s+\d+).*?(\d+)\s+points?", re.IGNORECASE)
    for entry in result:
        tag = entry[0]
        page = entry[2] if len(entry) > 2 else None
        content = entry[1] if len(entry) > 1 else ''
        if tag == 'p' and page is not None and isinstance(content, str):
            m = exercise_pattern.search(content)
            if m:
                ex = m.group(1).strip()
                pts = m.group(2).strip() + ' points'
                scoreboard_pages.setdefault(page, []).append([ex, pts])
    
    if scoreboard_pages:
        new_result = []
        injected = set()
        for entry in result:
            tag = entry[0]
            page = entry[2] if len(entry) > 2 else None
            if page in scoreboard_pages and page not in injected and tag in ('h2','p','li','image','cluster-image'):
                rows = scoreboard_pages[page]
                if len(rows) >= 3:
                    tb = TableBlock(page=page, order=0, y_coord=0.0, rows=rows, bbox=(0,0,0,0))
                    new_result.append(('table', tb, page, tb))
                injected.add(page)
            new_result.append(entry)
        result = new_result
    
    return result
