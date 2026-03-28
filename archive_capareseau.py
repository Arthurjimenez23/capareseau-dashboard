#!/usr/bin/env python3
"""
Script d'archivage quotidien des données Caparéseau (RTE)
Télécharge le CSV des capacités d'accueil de tous les postes sources de France
et l'archive avec la date du jour pour permettre l'analyse d'évolution.
"""

import os
import csv
import json
import urllib.request
import urllib.error
from datetime import datetime, date

# === CONFIGURATION ===
DOWNLOAD_URL = "https://www.capareseau.fr/medias/53BD59A8-0733-2108-FF9B-726AFBC13CAC"
# Dossier de base pour les archives (relatif au script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.path.join(SCRIPT_DIR, "archives_capareseau")
# Fichier consolidé pour l'analyse historique
CONSOLIDATED_FILE = os.path.join(SCRIPT_DIR, "capareseau_historique.csv")

# Colonnes principales à suivre pour l'analyse d'évolution
COLONNES_CLES = {
    "Code": "Code du poste source",
    "Nom": "Nom du poste source",
    "S3REnR": "Région / S3REnR",
    "TXA": "Taux d'affectation des capacités réservées",
    "INFO_CR": "Capacité réservée aux EnR au titre du S3REnR",
    "INFO_NA": "Capacité d'accueil réservée restant à affecter",
    "INFO_ESS3R": "Puissance des projets en service du S3REnR",
    "INFO_FAS3R": "Puissance des projets en file d'attente du S3REnR",
    "INFO_QP": "Quote-Part unitaire actualisée",
    "RTE_CDR": "Capacité dispo vue réseau transport",
    "RTE_TVX": "Travaux RTE pour augmenter la capacité",
    "RTE_ESS3R": "Installations raccordées au réseau transport",
    "GRD1_CDR": "Capacité dispo vue réseau distribution (GRD1)",
    "GRD1_ESS3R": "Installations raccordées au RPD (GRD1)",
    "GRD2_CDR": "Capacité dispo vue réseau distribution (GRD2)",
}


def telecharger_csv(url):
    """Télécharge le CSV depuis Caparéseau et retourne le contenu texte."""
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] Téléchargement depuis {url}...")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; CapareseauArchiver/1.0)",
        "Accept": "text/csv, application/octet-stream, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()
            # Le fichier est en UTF-8 avec BOM
            text = content.decode("utf-8-sig")
            print(f"  -> {len(text)} caractères téléchargés")
            return text
    except urllib.error.URLError as e:
        print(f"  ERREUR de téléchargement: {e}")
        raise


def parser_csv(texte_csv):
    """Parse le CSV Caparéseau (séparateur ;) et retourne les données."""
    lines = texte_csv.strip().split("\n")
    if len(lines) < 3:
        raise ValueError(f"CSV trop court: {len(lines)} lignes")

    # Ligne 1 = codes des colonnes, Ligne 2 = descriptions, Ligne 3+ = données
    codes_colonnes = next(csv.reader([lines[0]], delimiter=";", quotechar='"'))

    donnees = []
    reader = csv.reader(lines[2:], delimiter=";", quotechar='"')
    for row in reader:
        if len(row) >= 2 and row[0]:  # Ignorer les lignes vides
            poste = {}
            for i, code in enumerate(codes_colonnes):
                if i < len(row):
                    poste[code] = row[i]
            donnees.append(poste)

    print(f"  -> {len(donnees)} postes sources parsés")
    return codes_colonnes, donnees


def archiver_csv_brut(texte_csv, date_str):
    """Sauvegarde le CSV brut dans le dossier d'archives."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    fichier = os.path.join(ARCHIVE_DIR, f"capareseau_{date_str}.csv")
    with open(fichier, "w", encoding="utf-8") as f:
        f.write(texte_csv)
    print(f"  -> Archive brute sauvegardée: {fichier}")
    return fichier


def mettre_a_jour_historique(donnees, date_str):
    """Ajoute les données du jour au fichier historique consolidé."""
    # Colonnes du fichier historique
    colonnes_historique = ["Date", "Code", "Nom", "S3REnR", "TXA",
                           "INFO_CR", "INFO_NA", "INFO_ESS3R", "INFO_FAS3R",
                           "INFO_QP", "RTE_CDR", "RTE_TVX", "RTE_ESS3R",
                           "GRD1_CDR", "GRD1_ESS3R", "GRD2_CDR"]

    fichier_existe = os.path.exists(CONSOLIDATED_FILE)

    # Vérifier si les données du jour existent déjà
    if fichier_existe:
        with open(CONSOLIDATED_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if row and row[0] == date_str:
                    print(f"  -> Données du {date_str} déjà présentes, mise à jour ignorée")
                    return

    with open(CONSOLIDATED_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Écrire l'en-tête si nouveau fichier
        if not fichier_existe:
            writer.writerow(colonnes_historique)

        # Ajouter les données du jour
        nb_lignes = 0
        for poste in donnees:
            row = [date_str]
            for col in colonnes_historique[1:]:
                row.append(poste.get(col, ""))
            writer.writerow(row)
            nb_lignes += 1

    print(f"  -> {nb_lignes} lignes ajoutées à l'historique consolidé")


def generer_resume(donnees, date_str):
    """Génère un résumé statistique des données du jour."""
    resume = {
        "date": date_str,
        "nb_postes": len(donnees),
        "par_region": {},
        "postes_satures": [],  # TXA >= 100%
        "postes_forte_capacite": [],  # Grande capacité restante
    }

    for poste in donnees:
        region = poste.get("S3REnR", "Inconnu")
        if region not in resume["par_region"]:
            resume["par_region"][region] = {"nb_postes": 0, "total_cr": 0}
        resume["par_region"][region]["nb_postes"] += 1

        # Analyser le taux d'affectation
        txa = poste.get("TXA", "").replace("%", "").strip()
        try:
            txa_val = float(txa)
            if txa_val >= 100:
                resume["postes_satures"].append({
                    "code": poste.get("Code", ""),
                    "nom": poste.get("Nom", ""),
                    "region": region,
                    "txa": f"{txa_val}%"
                })
        except (ValueError, TypeError):
            pass

        # Analyser la capacité réservée
        cr = poste.get("INFO_CR", "").strip()
        try:
            cr_val = float(cr)
            resume["par_region"][region]["total_cr"] += cr_val
        except (ValueError, TypeError):
            pass

    resume["nb_postes_satures"] = len(resume["postes_satures"])

    # Sauvegarder le résumé
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    resume_file = os.path.join(ARCHIVE_DIR, f"resume_{date_str}.json")
    with open(resume_file, "w", encoding="utf-8") as f:
        json.dump(resume, f, ensure_ascii=False, indent=2)
    print(f"  -> Résumé sauvegardé: {resume_file}")

    return resume


def main():
    """Fonction principale d'archivage."""
    date_str = date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"  ARCHIVAGE CAPARÉSEAU - {date_str}")
    print(f"{'='*60}\n")

    try:
        # 1. Télécharger le CSV
        texte_csv = telecharger_csv(DOWNLOAD_URL)

        # 2. Parser les données
        colonnes, donnees = parser_csv(texte_csv)

        # 3. Archiver le CSV brut du jour
        archiver_csv_brut(texte_csv, date_str)

        # 4. Mettre à jour le fichier historique consolidé
        mettre_a_jour_historique(donnees, date_str)

        # 5. Générer un résumé statistique
        resume = generer_resume(donnees, date_str)

        # 6. Afficher le résumé
        print(f"\n--- RÉSUMÉ DU JOUR ---")
        print(f"Postes sources: {resume['nb_postes']}")
        print(f"Postes saturés (TXA >= 100%): {resume['nb_postes_satures']}")
        print(f"\nPar région:")
        for region, info in sorted(resume["par_region"].items()):
            print(f"  {region}: {info['nb_postes']} postes, "
                  f"capacité réservée totale: {info['total_cr']:.0f} MW")

        print(f"\n✓ Archivage terminé avec succès")

    except Exception as e:
        print(f"\n✗ ERREUR lors de l'archivage: {e}")
        raise


if __name__ == "__main__":
    main()
