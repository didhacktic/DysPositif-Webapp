"""Module de construction du HTML final pour la webapp DysPositif.
Sépare la mise en page (CSS/JS) et le rendu des items de la logique
PDF → objets (extraction / classification / colorisation).
"""
from __future__ import annotations
import os
import re
import base64
from typing import List, Tuple

from .conversion_models import TextBlock, TableBlock
from .colorization import (
    escape_html,
    colorize_syllables_html,
    colorize_mute_letters_html,
    colorize_syllables_and_mute_html,
    colorize_numbers_in_html,
)

CSS_BASE = """
@import url('https://cdn.jsdelivr.net/npm/opendyslexic@1.0.3/fonts/opendyslexic-regular.min.css');
body { font-family: 'OpenDyslexic','Inter','Noto Sans Math','Noto Sans Symbols','DejaVu Sans','Symbola','Arial',sans-serif; margin: 1.5rem auto; max-width: 70ch; line-height: 1.15; background:#faf9f4; color:#222; font-size: 16px; transition: font-size 0.2s, letter-spacing 0.2s, line-height 0.2s; }
h1 { font-size:2.2em; font-weight:700; margin:2.5rem 0 1.5rem; }
h2 { font-size:1.6em; font-weight:600; margin:2.5rem 0 1rem; letter-spacing:0.3px; }
h3 { font-weight:600; letter-spacing:0.5px; margin-top:2rem; }
p { margin:1rem 0; }
ul { margin:1rem 0; padding-left:1.4rem; list-style:none; }
li span.checkbox { display:inline-block; width:1.1em; }
table.doc-table { border-collapse:collapse; margin:1.5rem 0; width:100%; background:#fff; font-size:0.95em; }
table.doc-table td, table.doc-table th { border:1px solid #bbb; padding:0.4rem 0.6rem; }
table.doc-table th { background:#e8e7e2; font-weight:600; }
li { margin:0.5rem 0; }
.meta { font-size:0.85rem; color:#555; margin-bottom:2rem; }
.page-break { border-top:2px solid #bbb; margin:3rem 0; padding-top:1rem; }
img.doc-image { max-width:100%; height:auto; margin:1.5rem 0; border:1px solid #ddd; border-radius:4px; }
"""

JS_BASE = """
"""

# TOOLBAR_HTML removed to produce raw HTML output (no interactive toolbox)

def _apply_colorization(text_raw: str, apply_syllables: bool, apply_mute: bool, apply_num_pos: bool, apply_num_multi: bool) -> str:
    """Applique les colorations demandées sur un texte brut."""
    result = text_raw
    if apply_syllables and apply_mute:
        result = colorize_syllables_and_mute_html(result)
    elif apply_syllables:
        result = colorize_syllables_html(result)
    elif apply_mute:
        result = colorize_mute_letters_html(result)
    else:
        result = escape_html(result)
    if apply_num_pos or apply_num_multi:
        result = colorize_numbers_in_html(result, apply_num_pos, apply_num_multi)
    return result

def build_html(structured: List[tuple], source_pdf: str,
               apply_syllables: bool = False,
               apply_mute: bool = False,
               apply_num_pos: bool = False,
               apply_num_multi: bool = False) -> str:
    """Construit le HTML final à partir des items structurés."""
    html_parts = ["<!DOCTYPE html>", "<html lang='fr'>", "<head>", "<meta charset='utf-8'/>",
                  f"<title>Document reflow - {os.path.basename(source_pdf)}</title>",
                  f"<style>{CSS_BASE}</style>", f"<script>{JS_BASE}</script>", "</head>", "<body>"]
    html_parts.append(f"<div class='meta'>Source PDF: {os.path.basename(source_pdf)}</div>")
    html_parts.append("<h1>Version adaptée</h1>")

    # Collect indentation info
    page_baseline = {}
    page_indent_values = {}
    for item in structured:
        if len(item) > 3 and item[0] in ('p', 'h2'):
            page = item[2]
            block_obj = item[3]
            if block_obj and isinstance(block_obj, TextBlock):
                x = block_obj.indent_x
                if x is None:
                    continue
                if x < 5:
                    x = 0.0
                prev = page_baseline.get(page)
                if prev is None or x < prev:
                    page_baseline[page] = x
                page_indent_values.setdefault(page, []).append(x)
    for item in structured:
        if item[2] not in page_baseline:
            page_baseline[item[2]] = 0.0

    centered_pages = set()
    for pg, xs in page_indent_values.items():
        if not xs:
            continue
        min_x = min(xs); max_x = max(xs); spread = max_x - min_x; avg_x = sum(xs)/len(xs)
        high_indent_ratio = sum(1 for x in xs if x > 90) / len(xs)
        is_shifted = (spread > 150 and avg_x > 100) or (min_x > 90 and avg_x > 120) or (high_indent_ratio > 0.8)
        if is_shifted:
            centered_pages.add(pg)

    in_list = False
    for item in structured:
        tag = item[0]
        content = item[1] if len(item) > 1 else None
        block_obj = item[3] if len(item) > 3 else None
        page_num = item[2] if len(item) > 2 else None

        if tag == 'li':
            if not in_list:
                html_parts.append('<ul>'); in_list = True
            html_parts.append(f"<li>{_apply_colorization(content, apply_syllables, apply_mute, apply_num_pos, apply_num_multi)}</li>")
        elif tag == 'table':
            if in_list:
                html_parts.append('</ul>'); in_list = False
            tb: TableBlock = content  # type: ignore
            html_parts.append("<table class='doc-table'><tbody>")
            if tb.rows and all(len(r)==2 for r in tb.rows) and any('Exercice' in r[0] for r in tb.rows):
                html_parts.append("<tr><th>Exercice</th><th>Points</th></tr>")
            for r in tb.rows:
                html_parts.append('<tr>' + ''.join(f'<td>{_apply_colorization(c, apply_syllables, apply_mute, apply_num_pos, apply_num_multi)}</td>' for c in r) + '</tr>')
            html_parts.append("</tbody></table>")
        else:
            if in_list:
                html_parts.append('</ul>'); in_list = False
            if tag == 'page-break':
                if page_num is not None:
                    html_parts.append(f"<p style='text-align:center; color:#888; font-size:0.9em; margin:2rem 0 0.5rem;'>— Page {page_num + 1} —</p>")
                html_parts.append("<div class='page-break'></div>")
            elif tag in ('image', 'cluster-image'):
                img = content
                b64 = base64.b64encode(img.data).decode('utf-8')
                mime = f"image/{img.ext}" if img.ext in ["png", "jpeg", "jpg", "gif"] else "image/png"
                if tag == 'image':
                    html_parts.append(f"<img class='doc-image' src='data:{mime};base64,{b64}' alt='Image (page {img.page+1})' />")
                else:
                    alt_txt = " | ".join(img.alt_texts) if img.alt_texts else f"Image annotée page {img.page+1}"
                    html_parts.append(f"<img class='doc-image' src='data:{mime};base64,{b64}' alt='{escape_html(alt_txt)}' />")
            elif tag == 'h2':
                html_parts.append(f"<h2>{block_obj.styled_html if block_obj else escape_html(content)}</h2>")
            elif tag == 'p':
                indent_style = ""
                if block_obj:
                    page = item[2]; baseline = page_baseline.get(page, 0.0)
                    raw_indent = block_obj.indent_x - baseline
                    if page not in centered_pages and raw_indent > 16 and raw_indent < 120:
                        indent_em = round(raw_indent / 16.0, 2)
                        indent_style = f" style=\"text-indent:{indent_em}em;\""
                text_raw = content if isinstance(content, str) else (block_obj.text if block_obj else "")
                if apply_syllables or apply_mute or apply_num_pos or apply_num_multi:
                    text_content = _apply_colorization(text_raw, apply_syllables, apply_mute, apply_num_pos, apply_num_multi)
                else:
                    text_content = block_obj.styled_html if block_obj else escape_html(text_raw)
                text_content = re.sub(r'^(\s|&nbsp;)+', '', text_content)
                text_content = re.sub(r'\s{2,}', ' ', text_content)
                html_parts.append(f"<p{indent_style}>{text_content}</p>")

    if in_list:
        html_parts.append('</ul>')
    html_parts.append('</body></html>')
    return "\n".join(html_parts)
