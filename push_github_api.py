#!/usr/bin/env python3
"""
push_github_api.py — Pousse les fichiers du dashboard vers GitHub Pages via l'API GitHub.
Utilise votre token PAT stocké dans .github_config.json
"""

import base64
import json
import os
import sys
import urllib.request
import urllib.error

# ── Config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)  # dossier parent = workspace
CONFIG_FILE = os.path.join(WORKSPACE_DIR, '.github_config.json')

# Fichiers à pousser (chemin local → chemin dans le dépôt)
FILES_TO_PUSH = [
    (os.path.join(SCRIPT_DIR, 'dashboard_capareseau.html'),  'index.html'),
    (os.path.join(SCRIPT_DIR, 'capareseau_historique.csv'), 'capareseau_historique.csv'),
]

# Chercher aussi le JSON du jour
from datetime import date
today = date.today().strftime('%Y-%m-%d')
json_path = os.path.join(SCRIPT_DIR, 'archives_capareseau', f'resume_{today}.json')
if os.path.exists(json_path):
    FILES_TO_PUSH.append((json_path, f'archives_capareseau/resume_{today}.json'))


def load_config():
    """Charge la config GitHub depuis .github_config.json"""
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ Fichier de config introuvable : {CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config


def github_api_call(method, url, token, body=None):
    """Effectue un appel à l'API GitHub."""
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {token}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'capareseau-dashboard-push')
    req.method = method

    data = json.dumps(body).encode('utf-8') if body else None

    try:
        with urllib.request.urlopen(req, data=data) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"   ⚠ HTTP {e.code}: {error_body[:200]}")
        return None


def get_file_sha(token, owner, repo, path, branch='main'):
    """Récupère le SHA actuel d'un fichier dans le dépôt."""
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}'
    result = github_api_call('GET', url, token)
    if result and 'sha' in result:
        return result['sha']
    return None


def push_file(token, owner, repo, local_path, repo_path, branch='main'):
    """Pousse un fichier vers GitHub via l'API."""
    print(f"   📤 {repo_path}...")

    # Lire et encoder le fichier
    with open(local_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode('ascii')

    file_size_kb = os.path.getsize(local_path) // 1024
    print(f"      Taille : {file_size_kb} KB ({len(content)} chars base64)")

    # Récupérer le SHA actuel
    sha = get_file_sha(token, owner, repo, repo_path, branch)
    if sha:
        print(f"      SHA actuel : {sha[:12]}...")
    else:
        print(f"      (nouveau fichier)")

    # Construire le corps de la requête
    body = {
        'message': f'Données {today} — dashboard mis à jour',
        'content': content,
        'branch': branch
    }
    if sha:
        body['sha'] = sha

    # PUT
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{repo_path}'
    result = github_api_call('PUT', url, token, body)

    if result and 'commit' in result:
        commit_sha = result['commit']['sha'][:8]
        print(f"      ✅ Commit : {commit_sha}")
        return True
    else:
        print(f"      ❌ Échec du push")
        return False


def main():
    print("=" * 60)
    print("  Push Dashboard Caparéseau → GitHub Pages")
    print("=" * 60)

    # Charger la config
    config = load_config()
    token = config['token']
    owner = config['owner']
    repo  = config['repo']
    branch = config.get('branch', 'main')

    print(f"\n📂 Dépôt : {owner}/{repo} (branche {branch})")
    print(f"📅 Date  : {today}")
    print(f"\n🔄 Fichiers à pousser :")

    success_count = 0
    for local_path, repo_path in FILES_TO_PUSH:
        if not os.path.exists(local_path):
            print(f"   ⏭  {repo_path} — introuvable localement, ignoré")
            continue
        if push_file(token, owner, repo, local_path, repo_path, branch):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"  Résultat : {success_count}/{len(FILES_TO_PUSH)} fichiers poussés avec succès")
    print(f"{'='*60}")

    if success_count > 0:
        print(f"\n🌐 Dashboard : https://{owner.lower()}.github.io/{repo}/")
        print("   (mise à jour visible dans ~30-60 secondes)")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
