from __future__ import annotations
debug_images = False
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/pdf_to_reflow_html.py

MVP : Conversion d'un PDF en HTML reflow adapté dyslexie.

Principe :
1. Extraction des blocs texte via PyMuPDF (fitz). Fallback minimal si non installé.
2. Heuristiques pour détecter titres (taille de police supérieure à la médiane + <=120 caractères).
3. Nettoyage : suppression césures, espaces multiples, lignes vides.
4. Génération d'un HTML monocolonne avec CSS dys (OpenDyslexic si dispo, sinon sans-serif).
5. Hook prévu pour coloration syllabique/lettres muettes (non implémenté ici).

Usage :
    python scripts/pdf_to_reflow_html.py input.pdf --out dossier_sortie

Options :
    --min-heading-delta   Différence de taille vs médiane pour considérer un titre (par défaut 2pt).
    --max-heading-length  Longueur max d'une ligne de titre (par défaut 120).
    --no-title-detect     Désactive la détection des titres.
    --force               Écrase le dossier de sortie s'il existe.

Limites :
    - Pas d'OCR (détection image seulement). Si aucun texte trouvé, message conseillé : lancer OCR externe.
    - Tables/images non reconstruites (placeholder).
    - Export EPUB non encore implémenté.
"""
import argparse
import os
import sys
import re
import shutil
import statistics
import base64
import unicodedata
from typing import List, Tuple, Optional

# Import modèles et constantes externalisés
from .conversion_models import (
    TextBlock, ImageBlock, ContentItem, TableBlock,
    COLORS_SYLLABLES, COLOR_MUTE, COLORS_NUMBERS_POS, COLORS_NUMBERS_MULTI
)
# Import fonctions de coloration
from .colorization import (
    escape_html,
    colorize_syllables_html,
    colorize_mute_letters_html,
    colorize_syllables_and_mute_html,
    colorize_numbers_position_html,
    colorize_numbers_multicolor_html,
    colorize_numbers_in_html
)
# Import classification
from .classification import (
    normalize_text,
    parse_exercises_table,
    is_numeric_row,
    classify_items
)
# Import extraction
from .extraction import (
    extract_blocks_pdf,
    is_black_or_empty_image,
    dedupe_items,
    is_chart_text_block,
    is_incomplete_sentence,
    is_table_candidate
)
from .html_builder import build_html

try:
    import fitz  # PyMuPDF
    HAVE_FITZ = True
except ImportError:
    HAVE_FITZ = False

# Syllabisation désormais gérée entièrement dans colorization.py via lirecouleur



# (Dataclasses & constantes déplacées dans conversion_models.py)

# --- Utilitaires bbox / déduplication ---
# extract_blocks_pdf, is_black_or_empty_image, dedupe_items, is_chart_text_block,
# is_incomplete_sentence, is_table_candidate, bbox_iou, _extract_underlines_from_drawings,
# _span_has_underline → moved to extraction.py


# classify_items → moved to classification.py
# classify_blocks, classify_blocks_legacy_compat → removed (unused legacy wrappers)

# build_html déplacé vers html_builder.py


def main():
    """Point d'entrée CLI."""
    ap = argparse.ArgumentParser(description="MVP conversion PDF → HTML reflow dys")
    ap.add_argument("pdf", help="Chemin du PDF source")
    ap.add_argument("--out", default="reflow_output", help="Dossier de sortie")
    ap.add_argument("--min-heading-delta", type=float, default=2.0, help="Delta taille police vs médiane pour titre")
    ap.add_argument("--max-heading-length", type=int, default=120, help="Longueur max titre")
    ap.add_argument("--no-title-detect", action="store_true", help="Désactiver détection titres")
    ap.add_argument("--force", action="store_true", help="Écraser dossier sortie s'il existe")
    ap.add_argument("--merge-annotations", action="store_true", help="Fusionner overlays (texte + dessins) avec chaque image")
    ap.add_argument("--annotation-margin", type=float, default=10.0, help="Marge (points) autour des images pour capturer annotations. <=10 active marge adaptative (3%% dimensions, bornes 8-24pt)")
    ap.add_argument("--annotation-dpi", type=int, default=144, help="DPI pour rastérisation des clusters d'images avec annotations (défaut: 144)")
    ap.add_argument("--smart-annotations", action="store_true", help="Affiner la fusion annotations: ignorer QCM, tableaux, exercices et conserver seulement légendes courtes")
    ap.add_argument("--dedupe-annotations", action="store_true", help="(Obsolète) Déduplication post-process texte. Les doublons d'annotations sont déjà filtrés lors de l'extraction/fusion.")
    ap.add_argument("--syllables", action="store_true", help="Appliquer coloration syllabique alternée (requiert pylirecouleur)")
    ap.add_argument("--mute-letters", action="store_true", help="Appliquer grisage lettres muettes")
    ap.add_argument("--numbers-position", action="store_true", help="Appliquer coloration nombres par position")
    ap.add_argument("--numbers-multicolor", action="store_true", help="Appliquer coloration nombres multicolor")
    args = ap.parse_args()
    # Options traitées

    if not os.path.isfile(args.pdf):
        print(f"[ERREUR] Fichier introuvable: {args.pdf}")
        sys.exit(1)

    if os.path.exists(args.out):
        if args.force:
            shutil.rmtree(args.out)
        else:
            print(f"[ERREUR] Dossier {args.out} existe déjà. Utilisez --force pour écraser.")
            sys.exit(1)
    os.makedirs(args.out, exist_ok=True)

    print("[INFO] Extraction du contenu PDF...")
    items = extract_blocks_pdf(args.pdf, merge_annotations=args.merge_annotations, margin=args.annotation_margin, annotation_dpi=args.annotation_dpi,
                               smart_annotations=args.smart_annotations)
    if args.dedupe_annotations:
        before = len([it for it in items if it.type=='text'])
        items = dedupe_items(items)
        after = len([it for it in items if it.type=='text'])
        print(f"[INFO] Déduplication annotations: {before} → {after} blocs texte")
    if not items:
        print("[AVERTISSEMENT] Aucun bloc texte détecté. Document scanné ? Lancer OCR avant reflow.")
        html = build_html([], args.pdf)
        out_html = os.path.join(args.out, 'index.html')
        with open(out_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"[FIN] Sortie minimale : {out_html}")
        return

    nb_text = sum(1 for it in items if it.type == 'text')
    nb_images = sum(1 for it in items if it.type == 'image')
    print(f"[INFO] {nb_text} blocs texte et {nb_images} image(s) extraits.")
    
    structured = classify_items(items, args.min_heading_delta, args.max_heading_length, not args.no_title_detect)
    nb_titles = sum(1 for entry in structured if entry[0] == 'h2')
    nb_paras = sum(1 for entry in structured if entry[0] == 'p')
    nb_lists = sum(1 for entry in structured if entry[0] == 'li')
    nb_imgs = sum(1 for entry in structured if entry[0] == 'image')
    print(f"[INFO] Structure : {nb_titles} titres, {nb_paras} paragraphes, {nb_lists} items liste, {nb_imgs} images.")

    # Appliquer colorations si demandées
    colorations_actives = []
    if args.syllables:
        colorations_actives.append("syllabique")
    if args.mute_letters:
        colorations_actives.append("lettres muettes")
    if args.numbers_position:
        colorations_actives.append("nombres position")
    if args.numbers_multicolor:
        colorations_actives.append("nombres multicolor")
    
    if colorations_actives:
        print(f"[INFO] Colorations activées : {', '.join(colorations_actives)}")
    
    html = build_html(structured, args.pdf,
                     apply_syllables=args.syllables,
                     apply_mute=args.mute_letters,
                     apply_num_pos=args.numbers_position,
                     apply_num_multi=args.numbers_multicolor)
    out_html = os.path.join(args.out, 'index.html')
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[SUCCÈS] Fichier HTML reflow généré: {out_html}")
    print("Étapes suivantes possibles :")
    print(" - Intégrer syllabisation / lettres muettes sur chaque <p>")
    print(" - Détection listes (regex puces) et transformation en <ul>/<ol>")
    print(" - Extraction tableaux (Camelot) → <table>")
    print(" - Génération EPUB (ebooklib)")


if __name__ == '__main__':
    main()
