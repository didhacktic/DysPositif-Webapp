"""
Module d'extraction PDF avec PyMuPDF (fitz).

Ce module contient toutes les fonctions d'extraction de contenu depuis des PDF :
- Extraction de texte avec détection du style (gras, italique, souligné)
- Extraction d'images avec filtrage des images vides/noires
- Détection et capture de diagrammes vectoriels
- Fusion d'annotations sur images
- Déduplication de contenu
- Fusion de phrases incomplètes
- Détection et filtrage de headers répétitifs

Fonctions principales :
- extract_blocks_pdf() : extraction complète d'un PDF
- is_black_or_empty_image() : filtre images uniformes noires
- dedupe_items() : déduplication de blocs texte
"""

import statistics
from typing import List, Tuple, Optional
from .conversion_models import ContentItem, TextBlock, ImageBlock

# Imports conditionnels
try:
    import fitz  # type: ignore
    HAVE_FITZ = True
except ImportError:
    HAVE_FITZ = False

# Import des fonctions de classification
from .classification import normalize_text, parse_exercises_table, is_numeric_row

# Constants pour checkbox (utilisées dans smart_annotations)
_CHECKBOX_EMPTY_VARIANTS = {
    '', '□', '☐', '❏', ''
}
_CHECKBOX_FILLED_VARIANTS = {
    '', '☒', '✔', '✓', '✅', '❎', '☑', '', ''
}

# Variable debug (peut être activée depuis le code appelant)
debug_images = False


def _extract_underlines_from_drawings(page) -> List[Tuple[float,float,float,float]]:
    """Récupère lignes ET rectangles très fins horizontaux susceptibles d'être des soulignements."""
    lines: List[Tuple[float,float,float,float]] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return lines
    for d in drawings:
        for it in d.get('items', []):
            if not it:
                continue
            kind = it[0]
            # Ligne
            if kind == 'l':
                pts = it[1]
                if not isinstance(pts, (list, tuple)) or len(pts) != 4:
                    continue
                x0,y0,x1,y1 = pts
                dy = abs(y1 - y0)
                dx = abs(x1 - x0)
                if dx < 8 or dy > 3:  # relâché légèrement
                    continue
                y_top = min(y0,y1)
                y_bottom = max(y0,y1)
                lines.append((min(x0,x1), max(x0,x1), y_top, y_bottom))
            # Rectangle fin
            elif kind == 're':
                rect = it[1]
                if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                    continue
                rx0,ry0,rx1,ry1 = rect
                width = abs(rx1 - rx0)
                height = abs(ry1 - ry0)
                if width < 8 or height > 6:  # pas assez large ou trop épais
                    continue
                # Soulignement plausible si largeur suffisante et hauteur petite
                lines.append((min(rx0,rx1), max(rx0,rx1), min(ry0,ry1), max(ry0,ry1)))
    return lines


def _span_has_underline(span_bbox: Tuple[float,float,float,float], underline_lines: List[Tuple[float,float,float,float]]) -> bool:
    """Vérifie si une ligne/rectangle fin couvre ≥60% du span juste sous sa baseline."""
    x0,y0,x1,y1 = span_bbox
    target_min = y1 - 2
    target_max = y1 + 6
    width = x1 - x0
    if width <= 4:
        return False
    for lx0,lx1,ly0,ly1 in underline_lines:
        if ly0 < target_min or ly1 > target_max:
            continue
        inter_left = max(x0, lx0)
        inter_right = min(x1, lx1)
        if inter_right <= inter_left:
            continue
        cover = (inter_right - inter_left) / width
        if cover >= 0.6:
            return True
    return False


def bbox_iou(bbox1: tuple, bbox2: tuple) -> float:
    """Calcule IoU (Intersection over Union) entre deux bboxes."""
    x0_1, y0_1, x1_1, y1_1 = bbox1
    x0_2, y0_2, x1_2, y1_2 = bbox2
    
    inter_x0 = max(x0_1, x0_2)
    inter_y0 = max(y0_1, y0_2)
    inter_x1 = min(x1_1, x1_2)
    inter_y1 = min(y1_1, y1_2)
    
    if inter_x1 <= inter_x0 or inter_y1 <= inter_y0:
        return 0.0
    
    inter_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
    area1 = (x1_1 - x0_1) * (y1_1 - y0_1)
    area2 = (x1_2 - x0_2) * (y1_2 - y0_2)
    union_area = area1 + area2 - inter_area
    
    if union_area <= 0:
        return 0.0
    
    return inter_area / union_area


def dedupe_items(items: List[ContentItem], iou_threshold: float = 0.85) -> List[ContentItem]:
    """Déduplication texte: conserve premier bloc si texte identique + IoU >= seuil."""
    # Séparer par page pour réduire complexité
    by_page: dict[int, List[ContentItem]] = {}
    for it in items:
        by_page.setdefault(it.page, []).append(it)
    kept: List[ContentItem] = []
    for page, page_items in by_page.items():
        text_items = [it for it in page_items if it.type == 'text']
        other_items = [it for it in page_items if it.type != 'text']
        # Préparer structure de comparaison
        normalized_texts = [normalize_text(it.content.text) for it in text_items]
        removed = set()
        for i, it_i in enumerate(text_items):
            if i in removed:
                continue
            txt_i = normalized_texts[i]
            bbox_i = it_i.content.bbox
            # Parcourir suivants pour trouver doublons
            for j in range(i + 1, len(text_items)):
                if j in removed:
                    continue
                if normalized_texts[j] != txt_i:
                    continue
                iou = bbox_iou(bbox_i, text_items[j].content.bbox)
                if iou >= iou_threshold:
                    removed.add(j)
        # Ajouter ceux non retirés + autres items
        for k, it in enumerate(text_items):
            if k not in removed:
                kept.append(it)
        kept.extend(other_items)
    # Rétablir ordre global par (page, order, y_coord)
    kept.sort(key=lambda x: (x.page, x.order, x.y_coord))
    return kept


def is_chart_text_block(text: str, bbox: tuple, fontsize: float = 10.0) -> bool:
    """Heuristique: texte de graphique (labels/axes) à écarter des paragraphes."""
    text = text.strip()
    if not text:
        return True  # Bloc vide, probablement espace réservé pour graphique

    # Ne jamais filtrer les gros titres (police > 12pt)
    if fontsize > 12.0:
        return False

    # Ne jamais filtrer les lignes tableau numérique (ex: "19 2 N 6")
    if is_numeric_row(text):
        return False

    # Ne pas filtrer les lignes avec exercices/score (tableau points)
    if 'Exercice' in text and 'points' in text:
        return False

    # Ne pas filtrer les lignes contenant cases à cocher (QCM)
    if any(sym in text for sym in (_CHECKBOX_EMPTY_VARIANTS | _CHECKBOX_FILLED_VARIANTS)):
        return False

    # Blocs très courts (< 4 caractères) qui sont probablement des labels/nombres
    if len(text) <= 3:
        return True
    
    # Texte contenant uniquement des chiffres et espaces (échelle)
    if text.replace(' ', '').replace('-', '').isdigit():
        return True
    
    # Mots isolés courts (< 10 chars, police petite) = labels d'axes
    words = text.split()
    if len(words) == 1 and len(text) <= 10 and fontsize <= 11.0:
        return True
    
    # Labels multiples courts (ex: "Ville Montagne Mer Campagne")
    # Mais exclure si contient ponctuation de phrase (. ! ? :) = vraie phrase
    if len(words) >= 2 and all(len(w) <= 12 for w in words) and len(text) <= 45:
        if not any(p in text for p in ['.', '!', '?', ':', ';', ',']):
            # Vérifier que ce ne sont pas des mots de phrase normale
            common_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'est', 'dans', 'pour', 'sur', 'à', 'au'}
            if not any(w.lower() in common_words for w in words):
                return True
    
    return False


def is_incomplete_sentence(text: str) -> bool:
    """Phrase incomplète (absence ponctuation finale)."""
    text = text.rstrip()
    if not text:
        return False
    # Liste de ponctuations qui marquent la fin d'une phrase
    sentence_endings = ('.', '!', '?', ':', '»', '"', ')', ']', '}', '…')
    # Exceptions : abréviations courantes
    abbreviations = ('M.', 'Mme', 'Dr.', 'etc.', 'ex.', 'cf.', 'p.', 'pp.')
    
    # Si se termine par une ponctuation finale, ce n'est pas incomplet
    if text.endswith(sentence_endings):
        # Vérifier si ce n'est pas juste une abréviation
        for abbr in abbreviations:
            if text.endswith(abbr):
                return True
        return False
    
    # Si se termine par une lettre ou chiffre (pas de ponctuation), c'est incomplet
    return True


def is_table_candidate(text: str) -> bool:
    """Candidat tableau d'exercices (score)."""
    if not text.strip():
        return False
    return bool(parse_exercises_table(text))


def escape_html(s: str) -> str:
    """Échappe caractères HTML spéciaux."""
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def is_black_or_empty_image(image_data: bytes) -> bool:
    """Filtre images uniformes noires/sombres vides."""
    try:
        import fitz
        pix = fitz.Pixmap(image_data)
        # Échantillonner davantage de pixels pour plus de précision
        sample_size = min(5000, len(pix.samples))
        samples = pix.samples[:sample_size]
        if not samples:
            return True
        
        avg = sum(samples) / len(samples)
        # Calculer aussi l'écart-type pour détecter images uniformes
        variance = sum((s - avg) ** 2 for s in samples[:500]) / min(500, len(samples))
        std_dev = variance ** 0.5
        
        # Méthode 1: Image noire uniforme (seuils d'origine)
        if (avg < 25 and std_dev < 15) or avg < 8:
            return True

        # Méthode 2: Ratio de pixels sombres (seuil d'origine 0.7)
        dark_pixels = sum(1 for s in samples if s < 30)
        dark_ratio = dark_pixels / len(samples)
        if dark_ratio > 0.7:
            return True
        
        return False
    except Exception:
        return False


def extract_blocks_pdf(path: str, merge_annotations: bool = False, margin: float = 10.0, annotation_dpi: int = 144,
                       smart_annotations: bool = False) -> List[ContentItem]:
    """Extraction principale PDF (texte + images + fusion annotations)."""
    if not HAVE_FITZ:
        print("[WARN] PyMuPDF non installé. Installation recommandée: pip install pymupdf")
        return []
    import fitz  # type: ignore
    doc = fitz.open(path)
    items: List[ContentItem] = []

    for page_index, page in enumerate(doc):
        # Images avec positions - identifier d'abord les grandes images et petites annotations
        img_list = page.get_images(full=True)
        img_count = len(img_list)
        # Pré-calcul des traits sous la page (potentiels soulignements dessinés, non stylés dans police)
        underline_lines = _extract_underlines_from_drawings(page)
        
        # Première passe : identifier les grandes images (images principales)
        main_images = []
        for img_info in img_list:
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            if base_image:
                try:
                    rects = [r for r in page.get_image_rects(xref)]
                    if rects:
                        bbox = rects[0]
                        width = bbox[2] - bbox[0]
                        height = bbox[3] - bbox[1]
                        size_kb = len(base_image["image"]) / 1024
                        # Image principale = grande taille (>150px) ET taille fichier significative (>5KB)
                        if width > 150 and height > 150 and size_kb > 5:
                            main_images.append(bbox)
                except Exception:
                    pass
        
        # Deuxième passe : extraire les images en excluant les petites annotations proches des grandes
        for img_index, img_info in enumerate(img_list):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            if base_image:
                try:
                    rects = [r for r in page.get_image_rects(xref)]
                    bbox = rects[0] if rects else (0, 0, 0, 0)
                    y_coord = bbox[1]
                except Exception:
                    bbox = (0, 0, 0, 0)
                    y_coord = 0.0
                
                # Vérifier si c'est une petite annotation superposée
                #
                # Les doublons d'annotations sont supprimés ici :
                # - Toute petite image strictement contenue dans une grande est considérée comme annotation et fusionnée.
                # - Cela évite la création de doublons dès l'extraction, sans post-process risqué.
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                size_kb = len(base_image["image"]) / 1024
                
                is_annotation = False
                if merge_annotations:
                    # Containment strict pour marquer une petite image comme annotation intégrée
                    small_candidate = ((width < 140 and height < 140) or size_kb < 2)
                    if small_candidate:
                        img_rect = fitz.Rect(bbox)
                        for main_bbox in main_images:
                            main_rect = fitz.Rect(main_bbox)
                            if main_rect.contains(img_rect):
                                is_annotation = True
                                if debug_images:
                                    pass  # (aucun print, mais variable présente)
                                break
                    if debug_images:
                        pass  # (aucun print, mais variable présente)
                
                # Exclure les annotations, garder les images principales et indépendantes
                if not is_annotation and not is_black_or_empty_image(base_image["image"]):
                    img_block = ImageBlock(
                        data=base_image["image"],
                        page=page_index,
                        order=img_index,
                        ext=base_image.get("ext", "png"),
                        y_coord=y_coord,
                        bbox=bbox
                    )
                    items.append(ContentItem(
                        type='image',
                        page=page_index,
                        order=img_index,
                        y_coord=y_coord,
                        content=img_block
                    ))
        
        # Détecter et capturer les diagrammes vectoriels
        # Approche simple : chercher dessins stroke complexes (diagrammes = axes + barres)
        drawings = page.get_drawings()
        if drawings:
            page_rect = page.rect
            
            # Identifier dessins complexes : stroke avec beaucoup d'items (axes/grilles)
            complex_drawings = []
            for d in drawings:
                items_count = len(d.get('items', []))
                dtype = d.get('type', '')
                # Diagramme = stroke ('s') avec ≥8 items (lignes multiples)
                if dtype == 's' and items_count >= 8:
                    complex_drawings.append(d)
            
            # Regrouper dessins complexes proches (même diagramme)
            if complex_drawings:
                processed = set()
                for i, d1 in enumerate(complex_drawings):
                    if i in processed:
                        continue
                    
                    rect1 = fitz.Rect(d1['rect'])
                    group = [rect1]
                    processed.add(i)
                    
                    # Chercher autres dessins proches
                    for j, d2 in enumerate(complex_drawings):
                        if j <= i or j in processed:
                            continue
                        rect2 = fitz.Rect(d2['rect'])
                        # Distance entre rectangles
                        if rect1.intersects(rect2) or (
                            abs(rect1.x0 - rect2.x0) < 50 and
                            abs(rect1.y0 - rect2.y0) < 50):
                            group.append(rect2)
                            processed.add(j)
                    
                    # Calculer bbox englobant du groupe
                    combined = group[0]
                    for r in group[1:]:
                        combined |= r
                    
                    # Validation : taille et position raisonnables
                    aspect_ratio = combined.width / combined.height if combined.height > 0 else 0
                    area = combined.width * combined.height
                    
                    if (50 < combined.width < 500 and
                        50 < combined.height < 400 and
                        0.3 < aspect_ratio < 4.0 and
                        area < (page_rect.width * page_rect.height * 0.4) and
                        combined.y0 > 70):  # Pas en haut de page (header)
                        try:
                            # Capturer avec marge généreuse
                            clip_rect = fitz.Rect(
                                max(0, combined.x0 - 25),
                                max(0, combined.y0 - 25),
                                min(page_rect.width, combined.x1 + 25),
                                min(page_rect.height, combined.y1 + 25)
                            )
                            pix = page.get_pixmap(clip=clip_rect, dpi=144)
                            png_bytes = pix.tobytes("png")
                            
                            chart_block = ImageBlock(
                                data=png_bytes,
                                page=page_index,
                                order=img_count,
                                ext='png',
                                y_coord=combined.y0,
                                bbox=(clip_rect.x0, clip_rect.y0, clip_rect.x1, clip_rect.y1)
                            )
                            items.append(ContentItem(
                                type='image',
                                page=page_index,
                                order=img_count,
                                y_coord=combined.y0,
                                content=chart_block
                            ))
                            img_count += 1
                        except Exception:
                            pass

        # Fusion annotations si demandé
        merged_regions = []  # Stocker les zones d'images fusionnées pour filtrer les textes
        if merge_annotations and img_count > 0:
            # Récupérer toutes les images de la page (bitmap + dessins vectoriels)
            current_images = [item for item in items if item.type == 'image' and item.page == page_index]
            
            for img_item in current_images:
                img_block = img_item.content
                bbox = img_block.bbox
                if not bbox or len(bbox) < 4:
                    continue
                
                # Calculer marge adaptative généreuse pour capturer annotations débordantes (6% des dimensions)
                img_width = bbox[2] - bbox[0]
                img_height = bbox[3] - bbox[1]
                adaptive_margin = max(15, min(40, 0.06 * max(img_width, img_height)))
                
                expanded = fitz.Rect(
                    max(0, bbox[0] - adaptive_margin),
                    max(0, bbox[1] - adaptive_margin),
                    min(page.rect.width, bbox[2] + adaptive_margin),
                    min(page.rect.height, bbox[3] + adaptive_margin)
                )
                
                # Capturer la zone avec les annotations
                try:
                    pix = page.get_pixmap(clip=expanded, dpi=annotation_dpi)
                    merged_bytes = pix.tobytes("png")
                    
                    # Remplacer l'image par la version avec annotations
                    img_block.data = merged_bytes
                    img_block.ext = 'png'
                    img_block.bbox = (expanded.x0, expanded.y0, expanded.x1, expanded.y1)
                    
                    # Stocker la zone étendue pour filtrer les textes
                    merged_regions.append(expanded)
                except Exception:
                    pass

        # Texte avec reconstruction ligne
        raw = page.get_text("dict")
        order = 0
        for block in raw.get("blocks", []):
            if "lines" not in block:
                continue
            line_groups = []
            collected_spans = []
            min_x = None
            min_y = None
            max_x = None
            max_y = None
            for line in block.get("lines", []):
                line_text = []
                fontsizes = []
                y_coords = []
                for span in line.get("spans", []):
                    t = span.get("text", "")
                    if t.strip():
                        line_text.append(t)
                        fontsizes.append(span.get("size", 10.0))
                        y_coords.append(span.get("bbox", [0,0,0,0])[1])
                        x0 = span.get("bbox", [0,0,0,0])[0]
                        y0 = span.get("bbox", [0,0,0,0])[1]
                        x1 = span.get("bbox", [0,0,0,0])[2]
                        y1 = span.get("bbox", [0,0,0,0])[3]
                        if min_x is None or x0 < min_x:
                            min_x = x0
                        if min_y is None or y0 < min_y:
                            min_y = y0
                        if max_x is None or x1 > max_x:
                            max_x = x1
                        if max_y is None or y1 > max_y:
                            max_y = y1
                        fontname = span.get("font", "")
                        flags = span.get("flags", 0)
                        is_bold = ("Bold" in fontname) or bool(flags & 256)
                        is_italic = ("Italic" in fontname) or bool(flags & 1)
                        # Détection underline via nom de police OU ligne dessinée sous le span
                        raw_bbox = span.get("bbox", [0,0,0,0])
                        span_bbox = (raw_bbox[0], raw_bbox[1], raw_bbox[2], raw_bbox[3])
                        is_underline_font = ("Underline" in fontname)
                        is_underline_draw = _span_has_underline(span_bbox, underline_lines)
                        is_underline = is_underline_font or is_underline_draw
                        collected_spans.append({
                            "text": t,
                            "bold": is_bold,
                            "italic": is_italic,
                            "underline": is_underline
                        })
                if line_text:
                    line_groups.append((" ".join(line_text), fontsizes, y_coords))
            if not line_groups:
                continue
            all_text = " ".join([lg[0] for lg in line_groups])
            all_sizes = [s for lg in line_groups for s in lg[1]]
            all_y = [y for lg in line_groups for y in lg[2]]
            fontsize = statistics.median(all_sizes) if all_sizes else 10.0
            y_coord = statistics.median(all_y) if all_y else 0.0
            styled_parts = []
            for sp in collected_spans:
                # Normaliser chaque segment de texte pour remplacer glyphes spéciaux avant styling
                seg = escape_html(normalize_text(sp["text"]))
                if sp["italic"]:
                    seg = f"<em>{seg}</em>"
                if sp["bold"]:
                    seg = f"<strong>{seg}</strong>"
                if sp["underline"]:
                    seg = f"<u>{seg}</u>"
                styled_parts.append(seg)
            styled_html = " ".join(styled_parts)
            indent_x = min_x or 0.0
            bbox = (min_x or 0.0, min_y or y_coord, max_x or (min_x or 0.0), max_y or y_coord)

            # Filtrer les blocs de texte qui appartiennent à des diagrammes/graphiques
            # Ne pas filtrer si candidat tableau
            if is_chart_text_block(all_text, bbox, fontsize) and not is_table_candidate(all_text):
                order += 1
                continue
            
            # Ancien filtrage des textes inclus dans les zones fusionnées d'annotations désactivé
            # (risque de suppression de contenu utile : QCM, tableau). À remplacer par déduplication post-process.
            
            text_block = TextBlock(text=all_text, fontsize=fontsize, page=page_index, order=order,
                                   y_coord=y_coord, spans=collected_spans, indent_x=indent_x, styled_html=styled_html, bbox=bbox)
            items.append(ContentItem(
                type='text',
                page=page_index,
                order=order,
                y_coord=y_coord,
                content=text_block
            ))
            order += 1

    items.sort(key=lambda x: (x.page, x.y_coord, x.order))

    # Fusionner les blocs texte incomplets (phrases coupées)
    merged_items: List[ContentItem] = []
    i = 0
    while i < len(items):
        current = items[i]
        if current.type == 'text':
            # Vérifier si ce bloc et les suivants doivent être fusionnés
            text_to_merge = [current]
            j = i + 1
            while j < len(items):
                next_item = items[j]
                last_item = text_to_merge[-1]
                
                # Ne traiter que les blocs texte
                if next_item.type != 'text':
                    break
                
                # Calculer espacement vertical et horizontal
                y_gap = abs(next_item.y_coord - last_item.y_coord)
                indent_diff = abs(next_item.content.indent_x - last_item.content.indent_x)
                
                # Ne fusionner que si même page, proche verticalement, indentation similaire, et texte actuel incomplet
                if (next_item.page == current.page and
                    y_gap < 30 and  # Lignes consécutives (augmenté pour capturer interligne standard)
                    indent_diff < 30 and  # Indentation relativement similaire (tolère léger décalage)
                    is_incomplete_sentence(normalize_text(last_item.content.text))):
                    text_to_merge.append(next_item)
                    j += 1
                else:
                    break
            
            # Fusionner si plus d'un bloc
            if len(text_to_merge) > 1:
                merged_text = " ".join([normalize_text(tb.content.text) for tb in text_to_merge])
                merged_spans = []
                for tb in text_to_merge:
                    merged_spans.extend(tb.content.spans or [])
                
                # Reconstruire styled_html
                styled_parts = []
                for sp in merged_spans:
                    seg = escape_html(sp["text"])
                    if sp["italic"]:
                        seg = f"<em>{seg}</em>"
                    if sp["bold"]:
                        seg = f"<strong>{seg}</strong>"
                    if sp["underline"]:
                        seg = f"<u>{seg}</u>"
                    styled_parts.append(seg)
                merged_styled = " ".join(styled_parts)
                
                # Créer bloc fusionné
                first_block = text_to_merge[0].content
                merged_block = TextBlock(
                    text=merged_text,
                    fontsize=first_block.fontsize,
                    page=first_block.page,
                    order=first_block.order,
                    y_coord=first_block.y_coord,
                    spans=merged_spans,
                    indent_x=first_block.indent_x,
                    styled_html=merged_styled,
                    bbox=first_block.bbox
                )
                merged_items.append(ContentItem(
                    type='text',
                    page=current.page,
                    order=current.order,
                    y_coord=current.y_coord,
                    content=merged_block
                ))
                i = j
            else:
                merged_items.append(current)
                i += 1
        else:
            merged_items.append(current)
            i += 1
    
    items = merged_items

    # TOUJOURS filtrer les images overlay et noires (même sans merge_annotations)
    image_items = [it for it in items if it.type == 'image']
    overlay_candidate_ids: set[int] = set()
    
    for i, img_item in enumerate(image_items):
        img_block: ImageBlock = img_item.content
        
        bbox = img_block.bbox if isinstance(img_block.bbox, tuple) else (img_block.bbox.x0, img_block.bbox.y0, img_block.bbox.x1, img_block.bbox.y1)
        x0, y0, x1, y1 = bbox
        area = max((x1 - x0) * (y1 - y0), 1)
        width = x1 - x0
        height = y1 - y0
        
        # Filtre 1 : Images noires/vides
        is_black = is_black_or_empty_image(img_block.data)
        
        # Filtre 2 : Images très petites (< 20x20 pixels)
        if width < 20 or height < 20:
            overlay_candidate_ids.add(id(img_item))
            continue
        
        # Filtre 3 : Rectangles noirs (même s'ils ne sont pas petits)
        # Ratio aspect extrême (très allongé ou très large) + noir = probable décoration
        aspect_ratio = width / height if height > 0 else 0
        if is_black and (aspect_ratio > 10 or aspect_ratio < 0.1 or area < 5000):
            overlay_candidate_ids.add(id(img_item))
            continue
        
        # Filtre 4 : Images noires isolées de petite/moyenne taille
        if is_black and area < 50000:  # ~220x220 pixels
            overlay_candidate_ids.add(id(img_item))
            continue
        
        # Filtre 5 : Chercher si cette image est incluse dans une autre image (plus grande)
        for j, other_img in enumerate(image_items):
            if i == j or other_img.page != img_item.page or id(other_img) in overlay_candidate_ids:
                continue
            other_bbox = other_img.content.bbox if isinstance(other_img.content.bbox, tuple) else (other_img.content.bbox.x0, other_img.content.bbox.y0, other_img.content.bbox.x1, other_img.content.bbox.y1)
            ox0, oy0, ox1, oy1 = other_bbox
            other_area = max((ox1 - ox0) * (oy1 - oy0), 1)
            
            # Si cette image est incluse dans l'autre ET est plus petite
            if x0 >= ox0 and y0 >= oy0 and x1 <= ox1 and y1 <= oy1 and area < other_area * 0.8:
                overlay_candidate_ids.add(id(img_item))
                break

    if merge_annotations:
        
        # Étape 2 : Créer les clusters avec les images principales uniquement
        new_items: List[ContentItem] = []
        consumed_ids: set[int] = set()
        
        for img_item in image_items:
            if id(img_item) in consumed_ids or id(img_item) in overlay_candidate_ids:
                continue
            img_block: ImageBlock = img_item.content
            bbox = img_block.bbox if isinstance(img_block.bbox, tuple) else (img_block.bbox.x0, img_block.bbox.y0, img_block.bbox.x1, img_block.bbox.y1)
            x0, y0, x1, y1 = bbox
            
            # Calcul marge adaptative : 3% des dimensions + bornes [8pt, 24pt]
            img_width = x1 - x0
            img_height = y1 - y0
            adaptive_margin = max(8.0, min(24.0, 0.03 * max(img_width, img_height)))
            effective_margin = adaptive_margin if margin <= 10.0 else margin  # Respecter si utilisateur fixe marge > 10
            
            # Marge plus large vers le HAUT pour capturer les légendes au-dessus des images
            # Ajustement : rendre la marge adaptative pour éviter de capturer des paragraphes trop éloignés
            # Stratégie : multiplier la marge effective (facteur 2.0) mais plafonner à 35% de la hauteur de l'image
            # Ceci conserve la capture des labels proches (cas page 8) tout en limitant la sur‑capture (cas première image)
            top_margin = min(effective_margin * 2.0, img_height * 0.35)
            
            ext_x0 = x0 - effective_margin
            ext_y0 = y0 - top_margin
            ext_x1 = x1 + effective_margin
            ext_y1 = y1 + effective_margin
            annotation_texts: List[str] = []
            annotation_blocks: List[ContentItem] = []
            overlay_image_blocks: List[ContentItem] = []
            main_area = max((x1 - x0) * (y1 - y0), 1)
            # Chercher textes et petites images inclus
            for other in items:
                if other.page != img_item.page or id(other) in consumed_ids or id(other) == id(img_item):
                    continue
                if other.type == 'text':
                    tb: TextBlock = other.content
                    tx0, ty0, tx1, ty1 = tb.bbox
                    if tx0 >= ext_x0 and ty0 >= ext_y0 and tx1 <= ext_x1 and ty1 <= ext_y1:
                        area_txt = max((tx1 - tx0) * (ty1 - ty0), 1)
                        text_width = tx1 - tx0
                        text_normalized = normalize_text(tb.text)
                        char_count = len(text_normalized)
                        
                        # Filtrer paragraphes ordinaires : largeur >80% image OU >150 caractères
                        if text_width > img_width * 0.8 or char_count > 150:
                            continue
                        
                        # PRIORITÉ 1 : Exclure lignes tableau numérique AVANT test de taille
                        # Ces lignes doivent former un tableau indépendant, pas être fusionnées avec l'image
                        if smart_annotations and is_numeric_row(text_normalized):
                            # Ne pas consommer ce bloc : il doit rester dans items pour détection tableau
                            continue
                        
                        if area_txt < main_area * 0.25:
                            # Heuristiques smart: exclure contenus majeurs
                            if smart_annotations:
                                if ('Exercice' in text_normalized and 'points' in text_normalized):
                                    continue
                                # Exclure lignes QCM avec >=2 cases à cocher
                                checkbox_count = sum(text_normalized.count(sym) for sym in (_CHECKBOX_EMPTY_VARIANTS | _CHECKBOX_FILLED_VARIANTS))
                                if checkbox_count >= 2:
                                    continue
                                # Capturer uniquement légendes courtes / labels
                                if len(text_normalized) > 80:
                                    continue
                            annotation_texts.append(text_normalized)
                            annotation_blocks.append(other)
                elif other.type == 'image':
                    obx0, oby0, obx1, oby1 = other.content.bbox if isinstance(other.content.bbox, tuple) else (other.content.bbox.x0, other.content.bbox.y0, other.content.bbox.x1, other.content.bbox.y1)
                    if obx0 >= ext_x0 and oby0 >= ext_y0 and obx1 <= ext_x1 and oby1 <= ext_y1:
                        overlay_area = max((obx1 - obx0) * (oby1 - oby0), 1)
                        if overlay_area < main_area * 0.4:
                            overlay_image_blocks.append(other)
            if annotation_texts or overlay_image_blocks:
                try:
                    page_obj = doc[img_item.page]
                    clip_rect = fitz.Rect(ext_x0, ext_y0, ext_x1, ext_y1)
                    pix = page_obj.get_pixmap(clip=clip_rect, dpi=annotation_dpi)
                    png_bytes = pix.tobytes("png")
                except Exception:
                    png_bytes = img_block.data
                cluster_block = ImageBlock(
                    data=png_bytes,
                    page=img_item.page,
                    order=img_item.order,
                    ext='png',
                    y_coord=img_block.y_coord,
                    bbox=(ext_x0, ext_y0, ext_x1, ext_y1),
                    alt_texts=annotation_texts
                )
                new_items.append(ContentItem(
                    type='cluster-image',
                    page=img_item.page,
                    order=img_item.order,
                    y_coord=img_block.y_coord,
                    content=cluster_block
                ))
                consumed_ids.add(id(img_item))
                for ab in annotation_blocks:
                    consumed_ids.add(id(ab))
                for oi in overlay_image_blocks:
                    consumed_ids.add(id(oi))
            else:
                new_items.append(img_item)
        
        # Marquer tous les overlays comme consommés
        for overlay_id in overlay_candidate_ids:
            consumed_ids.add(overlay_id)
        
        # Ajouter les autres items non consommés
        for it in items:
            if id(it) in consumed_ids:
                continue
            if it.type != 'image':
                new_items.append(it)
        new_items.sort(key=lambda x: (x.page, x.y_coord, x.order))
        items = new_items
    else:
        # Même sans merge, filtrer les images overlay identifiées
        items = [it for it in items if it.type != 'image' or id(it) not in overlay_candidate_ids]

    # Détection headers répétitifs (apparaissent sur plusieurs pages avec texte identique en haut)
    # Grouper blocs texte par page et position haute
    header_candidates: dict[str, List[tuple]] = {}  # texte normalisé -> [(page, y_coord)]
    for item in items:
        if item.type == 'text':
            tb: TextBlock = item.content
            # Candidat header : haut de page (y < 80) ET court (< 100 chars)
            if tb.y_coord < 80 and len(normalize_text(tb.text)) < 100:
                normalized = normalize_text(tb.text).strip()
                if normalized:
                    header_candidates.setdefault(normalized, []).append((item.page, tb.y_coord, id(item)))
    
    # Identifier headers répétitifs (>= 2 pages différentes)
    repetitive_header_ids: set[int] = set()
    for text, occurrences in header_candidates.items():
        pages_set = set(page for page, _, _ in occurrences)
        # Si présent sur >= 2 pages différentes ET pas sur page 0 uniquement
        if len(pages_set) >= 2:
            # Exclure page 0 de la suppression (exception première page)
            for page, y, item_id in occurrences:
                if page != 0:
                    repetitive_header_ids.add(item_id)
    
    # Filtrer headers répétitifs
    items = [it for it in items if it.type != 'text' or id(it) not in repetitive_header_ids]

    return items
