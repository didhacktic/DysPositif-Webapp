# DysPositif-Webapp
Webapp DysPositif : adaptation de documents PDF pour la dyslexie (conversion, coloration, reflow, etc). Version web moderne.

---

# DysPositif Webapp

Version autonome web pour conversion de PDF en HTML adapté (syllabes, lettres muettes, nombres colorés).

## Structure du projet
```
DysPositifWebapp/
  server.py                # Point d'entrée Flask
  templates/
    index.html             # Formulaire upload + options
    result.html            # Affiche résultat via iframe
  static/
    style.css              # Styles modernes
  conversion/
    pdf_to_reflow_html.py  # Conversion PDF -> HTML reflow
    html_builder.py        # Génération HTML/CSS adapté
    pipeline.py            # Pipeline principal de conversion
    core/
      syllables.py         # Segmentation syllabique
  uploads/                 # (créé au runtime, fichiers uploadés)
  outputs/                 # (créé au runtime, résultats conversion)
  requirements.txt
  LICENSE
```

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Si syllabisation activée :
```bash
pip install git+https://framagit.org/arkaline/pylirecouleur.git
```

## Lancement
```bash
python app/app.py
```
Puis ouvrir http://localhost:5000

## Conversion
La webapp appelle le script original `DysPositif/scripts/pdf_to_reflow_html.py`. Assurez-vous que le projet principal est présent au chemin parent attendu.

Options de coloration (cases à cocher) :
- Syllabes (`--syllables`)
- Lettres muettes (`--mute-letters`)
- Nombres par position (`--numbers-position`)
- Nombres multicolor (`--numbers-multicolor`)

## Personnalisation
Pour supprimer la dépendance au script original, recopiez son contenu complet dans `conversion/pdf_to_reflow_html.py` et adaptez les imports (chemins core).

## Licence
GPLv3 – dérivé du projet principal DysPositif.
