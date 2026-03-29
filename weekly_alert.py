#!/usr/bin/env python3
# weekly_alert.py — Alerte email hebdomadaire Capareseau
import os, smtplib, csv
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
EMAIL_TO  = os.environ.get('EMAIL_TO', 'arthur@groupewattetco.com')

BASE_DIR   = Path(__file__).parent
CSV_PATH   = BASE_DIR / 'capareseau_historique.csv'
WINDOW_DAYS = 7
HTML_OUTPUT = Path('/tmp/capareseau_weekly_report.html')

def load_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            try:
                row['_date'] = datetime.strptime(row['Date'], '%Y-%m-%d').date()
            except ValueError:
                continue
            rows.append(row)
    return rows

def latest_snapshot_per_region(rows, since, until):
    best = {}
    for row in rows:
        d = row['_date']
        if since <= d < until:
            region = row['Region']
            if region not in best or d > best[region]['_date']:
                best[region] = row
    return best

def safe_float(val):
    try:
        return float(str(val).replace(',', '.'))
    except:
        return None

def build_comparison(cur_snap, prev_snap):
    results = []
    for region in sorted(set(cur_snap) | set(prev_snap)):
        cur  = cur_snap.get(region)
        prev = prev_snap.get(region)
        def delta(key):
            c = safe_float(cur.get(key)) if cur else None
            p = safe_float(prev.get(key)) if prev else None
            return (c, p, c - p) if c is not None and p is not None else (None, None, None)
        cr_cur,  _, cr_d  = delta('CR_total_MW')
        na_cur,  _, na_d  = delta('NA_total_MW')
        sat_cur, _, sat_d = delta('Satures_100pct')
        prox_cur,_, prx_d = delta('Proches_saturation_80pct')
        results.append({'region': region,
            'cr_cur': cr_cur, 'cr_delta': cr_d,
            'na_cur': na_cur, 'na_delta': na_d,
            'sat_cur': sat_cur, 'sat_delta': sat_d,
            'prox_cur': prox_cur, 'prox_delta': prx_d,
            'date_cur': cur['_date'].isoformat() if cur else '—'})
    return results

def fmt_delta(val, unit='', positive_bad=True):
    if val is None: return '<td style="text-align:center;color:#999">—</td>'
    if val == 0: return '<td style="text-align:center;color:#555">=</td>'
    color = ('#c0392b' if positive_bad else '#27ae60') if val > 0 else ('#27ae60' if positive_bad else '#c0392b')
    sign = f'+{val:,.1f}{unit}' if val > 0 else f'{val:,.1f}{unit}'
    return f'<td style="text-align:center;color:{color};font-weight:600">{sign}</td>'

def fmt_val(val, unit=''):
    if val is None: return '<td style="text-align:center;color:#999">—</td>'
    return f'<td style="text-align:center">{val:,.0f}{unit}</td>'

def build_html(results, today, week_start, prev_start):
    hs = 'background:#1a5276;color:#fff;padding:9px 12px;text-align:center'
    rows = ''.join(f"""
      <tr style="border-bottom:1px solid #eee">
        <td style="padding:8px 12px;font-weight:600">{r['region']}</td>
        {fmt_val(r['sat_cur'])}{fmt_delta(r['sat_delta'],'',True)}
        {fmt_val(r['prox_cur'])}{fmt_delta(r['prox_delta'],'',True)}
        {fmt_val(r['cr_cur'],' MW')}{fmt_delta(r['cr_delta'],' MW',False)}
        {fmt_val(r['na_cur'],' MW')}{fmt_delta(r['na_delta'],' MW',False)}
      </tr>""" for r in results)
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f6f9;margin:0;padding:20px">
<div style="max-width:900px;margin:auto;background:#fff;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.12)">
  <div style="background:#1a5276;padding:20px 30px">
    <h1 style="color:#fff;margin:0;font-size:20px">Alerte hebdomadaire Capareseau</h1>
    <p style="color:#aed6f1;margin:4px 0 0">Rapport du {today} | Semaine {week_start} vs {prev_start}</p>
  </div>
  <div style="padding:20px 30px">
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr>
        <th style="{hs};text-align:left">Region</th>
        <th style="{hs}" colspan="2">Satures 100%</th>
        <th style="{hs}" colspan="2">Proches 80%</th>
        <th style="{hs}" colspan="2">CR (MW)</th>
        <th style="{hs}" colspan="2">NA (MW)</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div></body></html>"""

def save_html_for_outlook(subject, html_body):
    HTML_OUTPUT.write_text(html_body, encoding='utf-8')
    print(f'[OK] HTML sauvegarde: {HTML_OUTPUT}')
    print(f'[INFO] Sujet: {subject} | Destinataire: {EMAIL_TO}')

def send_email(subject, html_body):
    save_html_for_outlook(subject, html_body)
    if not SMTP_USER or not SMTP_PASS:
        return
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [EMAIL_TO], msg.as_string())
    print(f'[OK] Email envoye a {EMAIL_TO}')

def main():
    today      = datetime.today().date()
    week_start = today - timedelta(days=WINDOW_DAYS)
    prev_start = today - timedelta(days=WINDOW_DAYS * 2)
    rows = load_csv(CSV_PATH)
    if not rows:
        print('[ERROR] CSV vide ou introuvable.'); return
    cur_snap  = latest_snapshot_per_region(rows, week_start, today + timedelta(days=1))
    prev_snap = latest_snapshot_per_region(rows, prev_start, week_start)
    if not cur_snap:
        print('[WARN] Aucune donnee pour la semaine courante.'); return
    comparison = build_comparison(cur_snap, prev_snap)
    html = build_html(comparison, today.isoformat(), week_start.isoformat(), prev_start.isoformat())
    subject = f'[Capareseau] Rapport hebdomadaire — {today.strftime("%d/%m/%Y")}'
    send_email(subject, html)

if __name__ == '__main__':
    main()
