#!/bin/bash
# setup_github_pages.sh — Configuration GitHub Pages pour le dashboard caparéseau
# À exécuter UNE SEULE FOIS depuis le dossier du projet.
#
# Prérequis :
#   - git installé (https://git-scm.com)
#   - gh CLI installé : brew install gh
#   - Authentifié avec GitHub : gh auth login
#
# Usage :
#   cd ~/chemin/vers/"Analyse raccordement caparéseau"
#   bash setup_github_pages.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_NAME="capareseau-dashboard"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║    Setup GitHub Pages — Dashboard Caparéseau        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Vérification des prérequis ─────────────────────────────────────────────
echo "► Vérification des prérequis..."

if ! command -v git &>/dev/null; then
    echo "  ❌ git non trouvé. Installez Xcode Command Line Tools : xcode-select --install"
    exit 1
fi
echo "  ✓ git $(git --version | awk '{print $3}')"

if ! command -v gh &>/dev/null; then
    echo "  ❌ gh CLI non trouvé."
    echo "     Installez-le avec : brew install gh"
    echo "     Puis authentifiez-vous : gh auth login"
    exit 1
fi
echo "  ✓ gh $(gh --version | head -1 | awk '{print $3}')"

if ! command -v python3 &>/dev/null; then
    echo "  ❌ python3 non trouvé."
    exit 1
fi
echo "  ✓ python3 $(python3 --version | awk '{print $2}')"

# ── 2. Authentification GitHub ────────────────────────────────────────────────
echo ""
echo "► Vérification de l'authentification GitHub..."
if ! gh auth status &>/dev/null; then
    echo "  Connexion à GitHub requise..."
    gh auth login
fi
GH_USER=$(gh api user --jq '.login')
echo "  ✓ Connecté en tant que : $GH_USER"

# ── 3. Initialisation git ─────────────────────────────────────────────────────
echo ""
echo "► Initialisation du dépôt git..."
cd "$SCRIPT_DIR"

if [ ! -d .git ]; then
    git init
    git checkout -b main 2>/dev/null || git branch -M main
    echo "  ✓ Dépôt git initialisé (branche main)"
else
    echo "  ✓ Dépôt git déjà existant"
    # S'assurer qu'on est sur main
    git checkout main 2>/dev/null || git checkout -b main 2>/dev/null || true
fi

# Configurer l'identité git si absente
if [ -z "$(git config user.email)" ]; then
    GH_EMAIL=$(gh api user --jq '.email // empty' 2>/dev/null || echo "")
    [ -z "$GH_EMAIL" ] && GH_EMAIL="$GH_USER@users.noreply.github.com"
    git config user.name "$GH_USER"
    git config user.email "$GH_EMAIL"
    echo "  ✓ Identité git configurée ($GH_USER)"
fi

# ── 4. .gitignore ─────────────────────────────────────────────────────────────
cat > .gitignore << 'GITIGNORE'
# CSV bruts quotidiens (trop volumineux pour git)
archives_capareseau/*.csv
# Logs
push_github.log
# Système
.DS_Store
__pycache__/
*.pyc
GITIGNORE
echo "  ✓ .gitignore configuré"

# ── 5. Création du dépôt GitHub ───────────────────────────────────────────────
echo ""
echo "► Création du dépôt GitHub '$REPO_NAME'..."
if gh repo view "$GH_USER/$REPO_NAME" &>/dev/null; then
    echo "  ✓ Dépôt déjà existant : https://github.com/$GH_USER/$REPO_NAME"
else
    gh repo create "$REPO_NAME" \
        --public \
        --description "Dashboard capacité d'accueil postes sources RTE (capareseau.fr) — mis à jour quotidiennement" \
        --confirm 2>/dev/null || \
    gh repo create "$GH_USER/$REPO_NAME" \
        --public \
        --description "Dashboard capacité d'accueil postes sources RTE (capareseau.fr) — mis à jour quotidiennement"
    echo "  ✓ Dépôt créé : https://github.com/$GH_USER/$REPO_NAME"
fi

# ── 6. Remote origin ──────────────────────────────────────────────────────────
if git remote get-url origin &>/dev/null; then
    git remote set-url origin "https://github.com/$GH_USER/$REPO_NAME.git"
else
    git remote add origin "https://github.com/$GH_USER/$REPO_NAME.git"
fi
echo "  ✓ Remote 'origin' configuré"

# ── 7. Régénération du dashboard ──────────────────────────────────────────────
echo ""
echo "► Régénération du dashboard avec les données du jour..."
if python3 regenerate_dashboard.py; then
    echo "  ✓ Dashboard régénéré"
else
    echo "  ⚠ Régénération ignorée — les données actuelles du dashboard seront utilisées"
fi

# ── 8. Premier commit ─────────────────────────────────────────────────────────
echo ""
echo "► Préparation du commit initial..."
git add dashboard_capareseau.html
git add capareseau_historique.csv
git add archives_capareseau/*.json 2>/dev/null || true
[ -f index.html ] && git add index.html
git add regenerate_dashboard.py push_github.sh setup_github_pages.sh .gitignore

# Commit (ignore si rien à commiter)
git commit -m "Initial commit — Dashboard caparéseau RTE" 2>/dev/null || echo "  (rien de nouveau à commiter)"

# ── 9. Push ───────────────────────────────────────────────────────────────────
echo ""
echo "► Push vers GitHub..."
git push -u origin main
echo "  ✓ Fichiers poussés sur GitHub"

# ── 10. Activation de GitHub Pages ────────────────────────────────────────────
echo ""
echo "► Activation de GitHub Pages..."
# Essayer d'activer via l'API (peut échouer si déjà activé)
gh api "repos/$GH_USER/$REPO_NAME/pages" \
    --method POST \
    -f source='{"branch":"main","path":"/"}' 2>/dev/null && \
    echo "  ✓ GitHub Pages activé" || \
    echo "  ✓ GitHub Pages déjà actif (ou activé manuellement dans Settings > Pages)"

# ── 11. Cron job pour le push quotidien (8h45) ────────────────────────────────
echo ""
echo "► Configuration du push automatique (chaque jour à 8h45)..."
chmod +x "$SCRIPT_DIR/push_github.sh"

CRON_JOB="45 8 * * * cd \"$SCRIPT_DIR\" && bash \"$SCRIPT_DIR/push_github.sh\" >> \"$SCRIPT_DIR/push_github.log\" 2>&1"

if crontab -l 2>/dev/null | grep -qF "push_github.sh"; then
    echo "  ✓ Cron job déjà configuré"
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "  ✓ Cron job ajouté (bash + push à 8h45 chaque matin)"
fi

# ── 12. Résumé ────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║                 ✅  SETUP TERMINÉ                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  🌐  Dashboard accessible (dans ~1 minute) :"
echo "      https://$GH_USER.github.io/$REPO_NAME/"
echo ""
echo "  📁  Dépôt GitHub :"
echo "      https://github.com/$GH_USER/$REPO_NAME"
echo ""
echo "  🔄  Mise à jour automatique :"
echo "      Archive caparéseau : 8h08  (tâche Claude planifiée)"
echo "      Push GitHub Pages  : 8h45  (cron sur ce Mac)"
echo ""
echo "  📋  Voir les logs de push : cat push_github.log"
echo ""
