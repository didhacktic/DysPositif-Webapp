"""Modèles et constantes de conversion PDF → HTML.
Séparé du script monolithique pour modularisation.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

# Couleurs HTML pour colorations
COLORS_SYLLABLES = ['#DC143C', '#1E90FF']  # Rouge, Bleu
COLOR_MUTE = '#C8C8C8'  # Gris
COLORS_NUMBERS_POS = ['#0000FF', '#FF0000', '#00FF00', '#FFFF00', '#FF00FF']  # Bleu (unités), Rouge (dizaines), Vert (centaines)...
COLORS_NUMBERS_MULTI = ['#0000FF', '#FF0000', '#00FF00', '#FFFF00', '#FF7F00', '#4B0082', '#9400D3']  # Arc-en-ciel

@dataclass
class TextBlock:
    text: str
    fontsize: float
    page: int
    order: int
    y_coord: float = 0.0
    spans: List[dict] = None
    indent_x: float = 0.0
    styled_html: str = ""
    bbox: tuple = (0.0, 0.0, 0.0, 0.0)

@dataclass
class ImageBlock:
    data: bytes
    page: int
    order: int
    ext: str = "png"
    y_coord: float = 0.0
    bbox: tuple = (0, 0, 0, 0)
    alt_texts: Optional[List[str]] = None

@dataclass
class ContentItem:
    type: str  # 'text' / 'image' / autres types internes
    page: int
    order: int
    y_coord: float
    content: any  # TextBlock | ImageBlock

@dataclass
class TableBlock:
    page: int
    order: int
    y_coord: float
    rows: List[List[str]]
    bbox: tuple
