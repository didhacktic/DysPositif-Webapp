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


> requirements.txt contient uniquement les dépendances principales nécessaires au fonctionnement de la webapp.
> Pour un environnement complet (développement, documentation, etc.), utilisez requirements-dev.txt :
> ```bash
> pip install -r requirements-dev.txt
> ```



## Lancement automatique (recommandé)
Un script facilite le lancement de la webapp :

```bash
./dyspositif-wa.sh
```

Ce script :
- crée et active l’environnement virtuel si besoin
- installe les dépendances manquantes
- télécharge le modèle spaCy fr_core_news_md si nécessaire
- lance automatiquement le serveur Flask

Vous pouvez ensuite ouvrir http://localhost:5000

## Lancement manuel (avancé)
Si vous préférez lancer manuellement :
```bash
python main.py
```
Puis ouvrir http://localhost:5000


## Conversion
La webapp intègre la logique de conversion directement dans le dossier `conversion/` du dépôt `DysPositifWebapp`.

Options de coloration (cases à cocher) :
- Syllabes (`--syllables`)
- Lettres muettes (`--mute-letters`)
- Nombres par position (`--numbers-position`)
- Nombres multicolor (`--numbers-multicolor`)


## Personnalisation
Pour adapter ou enrichir la conversion, modifiez les scripts du dossier `conversion/` et les modules du dossier `core/`.

## Licence

GPLv3 – dérivé du projet principal DysPositif.
