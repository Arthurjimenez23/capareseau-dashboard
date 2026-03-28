#!/usr/bin/env python3
"""
regenerate_dashboard.py
Régénère dashboard_capareseau.html avec les données les plus récentes.
Lit capareseau_historique.csv pour les stats régionales, et le CSV complet
du jour (~/Downloads/capareseau_DATE.csv) pour les tableaux de postes.
"""

import os, csv, json, glob, re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIQUE  = os.path.join(SCRIPT_DIR, "capareseau_historique.csv")
ARCHIVE_DIR = os.path.join(SCRIPT_DIR, "archives_capareseau")
DASHBOARD   = os.path.join(SCRIPT_DIR, "dashboard_capareseau.html")
DOWNLOADS   = os.path.expanduser("~/Downloads")

MOIS_FR = ['','janvier','février','mars','avril','mai','juin',
           'juillet','août','septembre','octobre','novembre','décembre']


def date_fr(date_str):
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return f"{d.day} {MOIS_FR[d.month]} {d.year}"
    except Exception:
        return date_str


def lire_derniere_date_historique():
    """Retourne (latest_date_str, [rows]) depuis capareseau_historique.csv."""
    if not os.path.exists(HISTORIQUE):
        return None, []
    rows_by_date = {}
    with open(HISTORIQUE, encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter=';'):
            d = row.get('Date', '')
            if d:
                rows_by_date.setdefault(d, []).append(row)
    if not rows_by_date:
        return None, []
    latest = max(rows_by_date)
    return latest, rows_by_date[latest]


def construire_region_js(rows):
    """Construit le dict regionData JS depuis les lignes historique."""
    d = {}
    for r in rows:
        region = r.get('Region', '?')
        try:
            count   = int(float(r.get('Nb_postes', 0)))
            cr      = float(r.get('CR_total_MW', 0))
            na      = float(r.get('NA_total_MW', 0))
            ess     = float(r.get('ESS3R_total_MW', 0))
            satures = int(float(r.get('Satures_100pct', 0)))
            proches = int(float(r.get('Proches_saturation_80pct', 0)))
            fa      = max(0.0, cr - na - ess)
            # Estimation des catégories de charge (approximatif sans le CSV complet)
            overloaded_est = satures
            high_est       = max(0, proches - satures)
            free_est       = max(0, int(na / cr * count * 0.6) if cr > 0 else 0)
            low_est        = max(0, int(na / cr * count * 0.3) if cr > 0 else 0)
            medium_est     = max(0, count - overloaded_est - high_est - free_est - low_est)
            d[region] = {
                'count': count,
                'total_cr':  round(cr),
                'total_na':  round(na),
                'total_ess': round(ess),
                'total_fa':  round(fa),
                'free': free_est, 'low': low_est, 'medium': medium_est,
                'high': high_est, 'overloaded': overloaded_est, 'noData': 0,
            }
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    return d


def trouver_csv_complet(date_str):
    """Cherche le CSV complet du jour dans ~/Downloads."""
    exact = os.path.join(DOWNLOADS, f"capareseau_{date_str}.csv")
    if os.path.exists(exact):
        return exact
    # Fallback : le CSV le plus récent
    candidates = sorted(glob.glob(os.path.join(DOWNLOADS, "capareseau_*.csv")), reverse=True)
    return candidates[0] if candidates else None


def extraire_top_postes(csv_file, n=20):
    """Extrait les top postes surchargés et disponibles depuis le CSV complet."""
    top_over, top_avail = [], []
    with open(csv_file, encoding='utf-8-sig') as f:
        lines = f.read().splitlines()
    if len(lines) < 3:
        return [], []
    codes = [c.strip() for c in lines[0].split(';')]
    for line in lines[2:]:
        if not line.strip():
            continue
        vals = line.split(';')
        p = {codes[i]: vals[i].strip().strip('"') for i in range(min(len(codes), len(vals)))}
        if not p.get('Code'):
            continue
        try:
            cr  = float(p.get('INFO_CR',  0) or 0)
            na  = float(p.get('INFO_NA',  0) or 0)
            ess = float(p.get('INFO_ESS3R', 0) or 0)
            fa  = float(p.get('INFO_FAS3R', 0) or 0)
            qp  = float((p.get('INFO_QP', '0') or '0').replace(',', '.'))
            if cr <= 0:
                continue
            load = round((ess + fa) / cr * 100)
            entry = dict(c=p.get('Code',''), n=p.get('Nom',''), r=p.get('S3REnR',''),
                         cr=round(cr,1), ess=round(ess,1), fa=round(fa,1), qp=round(qp,2))
            if load > 100:
                top_over.append({**entry, 'load': load})
            if na >= 50:
                top_avail.append({**entry, 'na': round(na,1)})
        except (ValueError, TypeError):
            pass
    top_over.sort(key=lambda x: x['load'], reverse=True)
    top_avail.sort(key=lambda x: x['na'],  reverse=True)
    return top_over[:n], top_avail[:n]


def fmt_kpi(value):
    """Formate un nombre avec espace fine comme séparateur de milliers."""
    return f"{int(value):,}".replace(',', '\u202f')


def main():
    print("Régénération du dashboard caparéseau...")

    # 1. Données historique
    latest_date, rows = lire_derniere_date_historique()
    if not latest_date:
        print("  ERREUR : capareseau_historique.csv vide ou absent")
        return
    print(f"  Date la plus récente : {latest_date}")

    region_js = construire_region_js(rows)

    # 2. KPIs agrégés
    total_postes = sum(int(float(r.get('Nb_postes', 0))) for r in rows)
    total_na  = sum(float(r.get('NA_total_MW', 0))    for r in rows)
    total_cr  = sum(float(r.get('CR_total_MW', 0))    for r in rows)
    total_ess = sum(float(r.get('ESS3R_total_MW', 0)) for r in rows)
    total_sat = sum(int(float(r.get('Satures_100pct', 0))) for r in rows)
    total_fa  = max(0.0, total_cr - total_na - total_ess)

    # 3. Top postes (CSV complet)
    csv_file = trouver_csv_complet(latest_date)
    if csv_file:
        print(f"  CSV complet : {os.path.basename(csv_file)}")
        top_over, top_avail = extraire_top_postes(csv_file)
        print(f"  → {len(top_over)} postes surchargés, {len(top_avail)} postes disponibles")
        over_json  = json.dumps(top_over,  ensure_ascii=False, indent=2)
        avail_json = json.dumps(top_avail, ensure_ascii=False, indent=2)
    else:
        print("  Pas de CSV complet trouvé — tableaux de postes inchangés")
        over_json = avail_json = None

    # 4. Lire le dashboard actuel
    with open(DASHBOARD, encoding='utf-8') as f:
        html = f.read()

    # 5. Mettre à jour le sous-titre
    html = re.sub(
        r'Données du \d+ \w+ \d{4} •',
        f'Données du {date_fr(latest_date)} •',
        html
    )

    # 6. Mettre à jour les KPIs (par label texte)
    def replace_kpi(label, new_value, h):
        return re.sub(
            rf'({re.escape(label)}</div>\s*<div class="value">)[^<]*(</div>)',
            rf'\g<1>{new_value}\2',
            h, flags=re.DOTALL
        )
    html = replace_kpi('Postes sources',      fmt_kpi(total_postes), html)
    html = replace_kpi('Capacité disponible', fmt_kpi(total_na),     html)
    html = replace_kpi('Capacité réservée',   fmt_kpi(total_cr),     html)
    html = replace_kpi('En service',          fmt_kpi(total_ess),    html)
    html = replace_kpi("En file d'attente",   fmt_kpi(total_fa),     html)
    html = replace_kpi('Postes surchargés',   str(total_sat),        html)

    # 7. Reconstruire la section DATA du JavaScript
    region_json = json.dumps(region_js, ensure_ascii=False, indent=2)

    if over_json is None:
        # Conserver les données existantes
        m_over  = re.search(r'const topOverloaded = (\[.*?\]);', html, re.DOTALL)
        m_avail = re.search(r'const topAvailable = (\[.*?\]);',  html, re.DOTALL)
        over_json  = m_over.group(1)  if m_over  else '[]'
        avail_json = m_avail.group(1) if m_avail else '[]'

    new_data = (
        "// ===== DATA =====\n"
        f"const regionData = {region_json};\n\n"
        f"const topOverloaded = {over_json};\n\n"
        f"const topAvailable = {avail_json};\n"
    )
    html = re.sub(
        r'// ===== DATA =====.*?(?=// ===== CHARTS =====)',
        new_data + '\n',
        html, flags=re.DOTALL
    )

    # 8. Mettre à jour le footer
    html = re.sub(
        r'(Dashboard Caparéseau — Données)[^<]*(<br>)',
        rf'\1 du {date_fr(latest_date)}\2',
        html
    )

    # 9. Écrire le dashboard mis à jour
    with open(DASHBOARD, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Dashboard mis à jour — {fmt_kpi(total_postes)} postes, "
          f"{fmt_kpi(int(total_na))} MW dispo, {total_sat} saturés")


if __name__ == '__main__':
    main()
