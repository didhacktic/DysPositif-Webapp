"""Coloration des nombres (positionnelle et multicolor).
"""
from __future__ import annotations
from .conversion_models import COLORS_NUMBERS_POS, COLORS_NUMBERS_MULTI
from .utils_html import escape_html

import re


def colorize_numbers_position_html(text: str) -> str:
    if not text or not text.strip():
        return escape_html(text)
    pattern = re.compile(r"\d+")
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
    if not text or not text.strip():
        return escape_html(text)
    pattern = re.compile(r"\d+")
    result = []
    last_end = 0
    for match in pattern.finditer(text):
        result.append(escape_html(text[last_end:match.start()]))
        num_str = match.group(0)
        colored_digits = []
        for digit in num_str:
            try:
                idx = int(digit)
                color = COLORS_NUMBERS_MULTI[idx]
            except Exception:
                color = COLORS_NUMBERS_MULTI[0]
            colored_digits.append(f"<span style='color:{color}'>{digit}</span>")
        result.append(''.join(colored_digits))
        last_end = match.end()
    result.append(escape_html(text[last_end:]))
    return ''.join(result)


def colorize_numbers_in_html(html_text: str, use_position: bool, use_multicolor: bool) -> str:
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
