#!/bin/bash
# push_now.command — Double-cliquez pour pousser le dashboard vers GitHub Pages
# Ce fichier s'ouvre dans Terminal et exécute le push automatiquement

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📁 Dossier : $SCRIPT_DIR"
echo ""
echo "🚀 Push du dashboard caparéseau vers GitHub Pages..."
echo ""

python3 "$SCRIPT_DIR/push_github_api.py"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Dashboard mis à jour ! Vérifiez dans 30-60 secondes :"
    echo "   https://arthurjimenez23.github.io/capareseau-dashboard/"
else
    echo ""
    echo "❌ Erreur lors du push. Code : $EXIT_CODE"
fi

echo ""
echo "Appuyez sur Entrée pour fermer..."
read
