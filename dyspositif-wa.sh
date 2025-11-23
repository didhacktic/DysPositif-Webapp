#!/bin/bash
# Script de lancement pour DysPositif Webapp
# Usage : ./dyspositif-wa.sh

set -e

# Chemin du dossier du script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Création et activation du venv si nécessaire
if [ ! -d ".venv" ]; then
    echo "Création de l'environnement virtuel (.venv)"
    python3 -m venv .venv
fi
source .venv/bin/activate

# 2. Installation des dépendances manquantes
pip install --upgrade pip
pip install -r requirements.txt

# 3. Téléchargement du modèle spaCy fr_core_news_md si absent
python -m spacy validate | grep -q 'fr_core_news_md' || {
    echo "Téléchargement du modèle spaCy fr_core_news_md..."
    python -m spacy download fr_core_news_md
}

# 4. Lancement de la webapp
exec python server.py
