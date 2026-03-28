#!/bin/bash
# push_github.sh — Push quotidien du dashboard caparéseau vers GitHub Pages
# Exécuté automatiquement chaque jour à 8h45 via cron (configuré par setup_github_pages.sh)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M')]"

echo "$LOG_PREFIX Démarrage du push GitHub Pages..."
cd "$SCRIPT_DIR"

# 1. Régénérer le dashboard avec les données du jour
if [ -f "regenerate_dashboard.py" ]; then
    echo "$LOG_PREFIX Régénération du dashboard..."
    python3 regenerate_dashboard.py
    if [ $? -ne 0 ]; then
        echo "$LOG_PREFIX ⚠ Régénération du dashboard échouée — push annulé"
        exit 1
    fi
fi

# 2. Vérifier s'il y a des changements à commiter
if git diff --quiet && git diff --cached --quiet; then
    echo "$LOG_PREFIX Aucun changement détecté — pas de push nécessaire"
    exit 0
fi

# 3. Ajouter les fichiers modifiés
git add dashboard_capareseau.html
git add capareseau_historique.csv
git add archives_capareseau/*.json 2>/dev/null || true

# 4. Commit daté
DATE=$(date '+%Y-%m-%d')
git commit -m "Archive caparéseau du $DATE"
if [ $? -ne 0 ]; then
    echo "$LOG_PREFIX ⚠ Commit échoué"
    exit 1
fi

# 5. Push
git push origin main
if [ $? -eq 0 ]; then
    echo "$LOG_PREFIX ✓ Push GitHub réussi — dashboard mis à jour"
else
    echo "$LOG_PREFIX ✗ Push GitHub échoué — vérifiez votre connexion ou les credentials"
    exit 1
fi
