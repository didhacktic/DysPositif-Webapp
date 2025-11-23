"""Orchestrateur de conversion PDF → HTML reflow pour DysPositifWebapp.
Centralise les étapes: extraction → classification → construction HTML.
Permet réutilisation programmatique et future intégration (API / worker).
"""
from __future__ import annotations
import os
import sys
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from .extraction import extract_blocks_pdf, dedupe_items
from .classification import classify_items
from .html_builder import build_html

# Flags optionnels pour colorisations
class ConversionOptions:
    def __init__(self,
                 min_heading_delta: float = 2.0,
                 max_heading_length: int = 120,
                 detect_titles: bool = True,
                 merge_annotations: bool = False,
                 annotation_margin: float = 10.0,
                 annotation_dpi: int = 144,
                 smart_annotations: bool = False,
                 syllables: bool = False,
                 mute_letters: bool = False,
                 numbers_position: bool = False,
                 numbers_multicolor: bool = False,
                 dedupe_annotations: bool = False):
        self.min_heading_delta = min_heading_delta
        self.max_heading_length = max_heading_length
        self.detect_titles = detect_titles
        self.merge_annotations = merge_annotations
        self.annotation_margin = annotation_margin
        self.annotation_dpi = annotation_dpi
        self.smart_annotations = smart_annotations
        self.syllables = syllables
        self.mute_letters = mute_letters
        self.numbers_position = numbers_position
        self.numbers_multicolor = numbers_multicolor
        self.dedupe_annotations = dedupe_annotations


def convert_pdf_to_html(pdf_path: str, output_dir: str | Path, options: ConversionOptions, force: bool = False) -> Path:
    """Convertit un PDF en HTML reflow. Retourne le chemin du fichier HTML généré.
    Ne lève pas d'exception fatale : imprime des messages et continue (MVP).
    """
    pdf_path = str(pdf_path)
    out_dir = Path(output_dir)
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"Fichier PDF introuvable: {pdf_path}")

    if out_dir.exists():
        if force:
            shutil.rmtree(out_dir)
        else:
            raise FileExistsError(f"Dossier {out_dir} existe déjà (utilisez --force pour écraser)")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[PIPELINE] Extraction...")
    items = extract_blocks_pdf(pdf_path,
                               merge_annotations=options.merge_annotations,
                               margin=options.annotation_margin,
                               annotation_dpi=options.annotation_dpi,
                               smart_annotations=options.smart_annotations)

    if options.dedupe_annotations:
        before = len([it for it in items if it.type == 'text'])
        items = dedupe_items(items)
        after = len([it for it in items if it.type == 'text'])
        print(f"[PIPELINE] Déduplication annotations: {before} → {after} blocs texte")

    if not items:
        print("[PIPELINE] Aucun bloc détecté, génération fallback HTML vide.")
        html = build_html([], pdf_path)
        html_file = out_dir / 'index.html'
        html_file.write_text(html, encoding='utf-8')
        return html_file

    print("[PIPELINE] Classification...")
    structured = classify_items(items,
                                options.min_heading_delta,
                                options.max_heading_length,
                                options.detect_titles)

    print("[PIPELINE] Construction HTML...")
    html = build_html(structured, pdf_path,
                      apply_syllables=options.syllables,
                      apply_mute=options.mute_letters,
                      apply_num_pos=options.numbers_position,
                      apply_num_multi=options.numbers_multicolor)
    html_file = out_dir / 'index.html'
    html_file.write_text(html, encoding='utf-8')
    print(f"[PIPELINE] Terminé: {html_file}")
    return html_file


def _parse_cli_args(argv: Optional[List[str]] = None):
    import argparse
    ap = argparse.ArgumentParser(description="Pipeline conversion PDF → HTML reflow (webapp)")
    ap.add_argument('pdf', help='Chemin du PDF source')
    ap.add_argument('--out', default='reflow_output', help='Dossier de sortie (sera écrasé)')
    ap.add_argument('--min-heading-delta', type=float, default=2.0, help='Delta taille police vs médiane pour titre')
    ap.add_argument('--max-heading-length', type=int, default=120, help='Longueur max titre')
    ap.add_argument('--no-title-detect', action='store_true', help='Désactiver la détection titres')
    ap.add_argument('--merge-annotations', action='store_true', help='Fusionner annotations et images')
    ap.add_argument('--annotation-margin', type=float, default=10.0, help='Marge autour images pour annotations')
    ap.add_argument('--annotation-dpi', type=int, default=144, help='DPI pour clusters avec annotations')
    ap.add_argument('--smart-annotations', action='store_true', help='Filtrer annotations non pertinentes')
    ap.add_argument('--dedupe-annotations', action='store_true', help='Déduplication post-process (obsolète)')
    ap.add_argument('--syllables', action='store_true', help='Coloration syllabique')
    ap.add_argument('--mute-letters', action='store_true', help='Grisage lettres muettes')
    ap.add_argument('--numbers-position', action='store_true', help='Coloration nombres par position')
    ap.add_argument('--numbers-multicolor', action='store_true', help='Coloration nombres multicolor')
    ap.add_argument('--force', action='store_true', help='Écrase le dossier de sortie s’il existe déjà')
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None):
    args = _parse_cli_args(argv)
    opts = ConversionOptions(
        min_heading_delta=args.min_heading_delta,
        max_heading_length=args.max_heading_length,
        detect_titles=not args.no_title_detect,
        merge_annotations=args.merge_annotations,
        annotation_margin=args.annotation_margin,
        annotation_dpi=args.annotation_dpi,
        smart_annotations=args.smart_annotations,
        syllables=args.syllables,
        mute_letters=args.mute_letters,
        numbers_position=args.numbers_position,
        numbers_multicolor=args.numbers_multicolor,
        dedupe_annotations=args.dedupe_annotations,
    )
    try:
        html_path = convert_pdf_to_html(args.pdf, args.out, opts, force=args.force)
    except FileExistsError as e:
        print(f"[ERREUR] {e}")
        sys.exit(1)
    print(f"[PIPELINE] HTML généré: {html_path}")


if __name__ == '__main__':
    main()
