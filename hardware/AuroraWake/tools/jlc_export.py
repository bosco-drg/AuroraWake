# -*- coding: utf-8 -*-
"""Export complet pour JLCPCB : DRC, Gerber + percages (zip), BOM et CPL au format JLCPCB, plans PDF.
Usage (depuis hardware/AuroraWake) : python3 tools/jlc_export.py
Sortie : production/jlcpcb/
"""
import csv, glob, os, re, shutil, subprocess, sys, tempfile, zipfile
import xml.etree.ElementTree as ET

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
PCB, SCH, OUT = 'AuroraWake.kicad_pcb', 'AuroraWake.kicad_sch', 'production/jlcpcb'
GER, DOC = f'{OUT}/gerbers', f'{OUT}/docs'
TMP = tempfile.mkdtemp()

def run(*args):
    r = subprocess.run(['kicad-cli', *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'Echec : kicad-cli {" ".join(args)}\n{r.stdout}\n{r.stderr}')

def natkey(ref):
    m = re.match(r'([A-Z]+)(\d+)', ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)

for d in (GER, DOC):
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)

# 1. DRC (bloquant si erreur ou connexion manquante)
run('pcb', 'drc', '--schematic-parity', '--severity-error', '-o', f'{DOC}/DRC_erreurs.txt', PCB)
rpt = open(f'{DOC}/DRC_erreurs.txt').read()
nerr = int(re.search(r'Found (\d+) DRC violations', rpt).group(1))
nunc = int(re.search(r'Found (\d+) unconnected pads', rpt).group(1))
run('pcb', 'drc', '--schematic-parity', '--severity-all', '-o', f'{DOC}/DRC_rapport.txt', PCB)
os.remove(f'{DOC}/DRC_erreurs.txt')
print(f'DRC : {nerr} erreur(s), {nunc} connexion(s) manquante(s)')
if nerr or nunc:
    sys.exit('Export annule : corriger le DRC d abord (voir docs/DRC_rapport.txt).')

# 2. Gerber + percages
run('pcb', 'export', 'gerbers', '--layers',
    'F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
    '--no-x2', '--no-netlist', '--subtract-soldermask', '-o', GER + '/', PCB)
run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal',
    '--excellon-oval-format', 'alternate', '--excellon-separate-th', '--generate-map', '--map-format', 'pdf',
    '-o', GER + '/', PCB)
for f in glob.glob(f'{GER}/*.gbrjob'): os.remove(f)
for f in glob.glob(f'{GER}/*drl_map.pdf'): shutil.move(f, DOC)
with zipfile.ZipFile(f'{OUT}/AuroraWake_gerbers_JLCPCB.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(glob.glob(f'{GER}/*')): z.write(f, os.path.basename(f))

# 3. BOM JLCPCB (groupee par valeur / empreinte / reference fabricant)
run('sch', 'export', 'netlist', '--format', 'kicadxml', '-o', f'{TMP}/net.xml', SCH)
root = ET.parse(f'{TMP}/net.xml').getroot()
groups, excluded, manual = {}, [], {}
for c in root.find('components'):
    ref = c.get('ref')
    props = {p.get('name') for p in c.findall('property')}
    fields = {f.get('name'): f.text for f in c.iter('field')}
    if 'exclude_from_bom' in props or 'dnp' in props or ref.startswith(('H', 'NT', '#')):
        excluded.append(ref); continue
    key = (c.findtext('value'), c.findtext('footprint').split(':')[1], fields.get('MPN') or '', fields.get('LCSC') or '')
    if not key[3]:                       # sans reference LCSC -> soudure manuelle (traversants, BT601 au dos)
        manual.setdefault(key, []).append(ref); continue
    groups.setdefault(key, []).append(ref)
with open(f'{OUT}/AuroraWake_BOM_JLCPCB.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Manufacturer Part', 'Quantity'])
    for (val, fp, mpn, lcsc), refs in sorted(groups.items(), key=lambda kv: natkey(min(kv[1], key=natkey))):
        refs.sort(key=natkey)
        w.writerow([val, ','.join(refs), fp, lcsc, mpn, len(refs)])
bomrefs = {r for v in groups.values() for r in v}
with open(f'{OUT}/a_souder_a_la_main.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Valeur', 'Empreinte', 'Reference fabricant', 'Quantite'])
    for (val, fp, mpn, _), refs in sorted(manual.items(), key=lambda kv: natkey(min(kv[1], key=natkey))):
        refs.sort(key=natkey); w.writerow([','.join(refs), val, fp, mpn, len(refs)])

# 4. CPL JLCPCB
run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '--exclude-dnp', '-o', f'{TMP}/pos.csv', PCB)
pos = list(csv.DictReader(open(f'{TMP}/pos.csv')))
with open(f'{OUT}/AuroraWake_CPL_JLCPCB.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for r in sorted(pos, key=lambda r: natkey(r['Ref'])):
        if r['Ref'] in bomrefs:
            w.writerow([r['Ref'], f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm",
                        'Top' if r['Side'] == 'top' else 'Bottom', f"{float(r['Rot']):.1f}"])
missing = bomrefs - {r['Ref'] for r in pos}
if missing:
    sys.exit(f'Composants de la BOM absents du PCB : {sorted(missing)}')

# 5. Documents
run('pcb', 'export', 'pdf', '--layers', 'F.Fab,F.Silkscreen,Edge.Cuts', '--mode-single', '--include-border-title',
    '-o', f'{DOC}/AuroraWake_assemblage_dessus.pdf', PCB)
run('pcb', 'export', 'pdf', '--layers', 'B.Fab,B.Silkscreen,Edge.Cuts', '--mode-single', '--mirror', '--include-border-title',
    '-o', f'{DOC}/AuroraWake_assemblage_dessous.pdf', PCB)
run('sch', 'export', 'pdf', '-o', f'{DOC}/AuroraWake_schema.pdf', SCH)

print(f'BOM : {len(groups)} lignes / {len(bomrefs)} composants ; CPL : {len(bomrefs)} positions ; exclus : {sorted(excluded)}')
print('a souder a la main :', sorted((r for v in manual.values() for r in v), key=natkey))
print(f'Fichiers dans {OUT}/ :', sorted(os.listdir(OUT)))
