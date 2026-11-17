# -*- coding: utf-8 -*-
"""Construit AuroraWake.kicad_pcb a partir du schema (netlist) + pcb_place.py + pcb_route.py.
Usage (depuis hardware/AuroraWake) : python3 tools/pcb_build.py
ATTENTION : reconstruit entierement le PCB (empreintes, pistes, zones).
"""
import os, sys, subprocess, tempfile, xml.etree.ElementTree as ET
import pcbnew
sys.path.insert(0, os.path.dirname(__file__))
from pcb_place import PLACE, BOARD_W, BOARD_H, ORIGIN, FIXED, KEEPOUT

PROJ = 'AuroraWake'
FPDIR = '/usr/share/kicad/footprints'
mm = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))

# ------------------------------------------------------------------ netlist
tmp = tempfile.mkdtemp()
xmlp = os.path.join(tmp, 'net.xml')
subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xmlp, f'{PROJ}.kicad_sch'],
               check=True, capture_output=True)
root = ET.parse(xmlp).getroot()
comps = {}
for c in root.find('components'):
    fields = {f.get('name'): f.text for f in c.iter('field')}
    comps[c.get('ref')] = dict(value=c.findtext('value'), fp=c.findtext('footprint'),
                               uuid=c.find('tstamps').text, sheet=c.find('sheetpath').get('tstamps'),
                               mpn=fields.get('MPN', ''))
pinnet = {}
for n in root.find('nets'):
    for nd in n.findall('node'):
        pinnet[(nd.get('ref'), nd.get('pin'))] = n.get('name')

missing = set(comps) - set(PLACE)
if missing:
    sys.exit(f'Pas de position pour : {sorted(missing)}')

# ------------------------------------------------------------------ carte
if os.path.exists(f'{PROJ}.kicad_pcb'):
    import pcb_route
    import re
    n_gen = (sum(len(t[3]) - 1 for t in pcb_route.TRACKS) + len(pcb_route.VIAS)
             + sum(1 for v in pcb_route.VIAS if v[2]))
    txt = open(f'{PROJ}.kicad_pcb').read()
    n_cur = len(re.findall(r'^\t\((segment|arc|via)\b', txt, re.M))
    if n_cur > n_gen and '--force' not in sys.argv:
        sys.exit(f'Le PCB contient {n_cur} pistes/vias (> {n_gen} generees) : routage manuel detecte. '
                 'Reconstruction refusee (elle l\'effacerait). Utiliser --force pour ecraser.')
    os.remove(f'{PROJ}.kicad_pcb')       # reconstruction complete a partir d'une carte vierge
board = pcbnew.NewBoard(f'{PROJ}.kicad_pcb')
board.SetCopperLayerCount(2)
ds = board.GetDesignSettings()
ds.SetBoardThickness(mm(1.6))
ds.m_TrackMinWidth = mm(0.2)
ds.m_MinClearance = mm(0.2)
ds.m_ViasMinSize = mm(0.6)
ds.m_MinThroughDrill = mm(0.2)   # vias thermiques 0,2 mm du module ESP32 (OK JLCPCB)
ds.m_CopperEdgeClearance = mm(0.3)
ds.m_HoleToHoleMin = mm(0.5)
ds.SetAuxOrigin(P(0, 0)); ds.SetGridOrigin(P(0, 0))

# nets
nets = {}
for name in sorted(set(pinnet.values())):
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    nets[name] = ni

# empreintes
for ref, c in sorted(comps.items()):
    lib, name = c['fp'].split(':')
    fp = pcbnew.FootprintLoad(f'{FPDIR}/{lib}.pretty', name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref)
    fp.SetValue(c['value'])
    fp.SetPath(pcbnew.KIID_PATH(c['sheet'] + c['uuid']))
    if c['mpn']:
        fp.SetField('MPN', c['mpn'])
        f = fp.GetFieldByName('MPN'); f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
    fp.Value().SetVisible(False)
    board.Add(fp)
    pl = PLACE[ref]
    x, y, rot = pl[:3]
    fp.SetPosition(P(x, y))
    fp.SetOrientationDegrees(rot)
    if len(pl) > 3 and pl[3] == 'B':
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for pad in fp.Pads():
        n = pinnet.get((ref, pad.GetNumber()))
        if n:
            pad.SetNet(nets[n])
    # reference : petite, sur la serigraphie
    r = fp.Reference()
    r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    r.SetTextThickness(mm(0.12))

# ------------------------------------------------------------------ legalisation
def bbox_mm(fp):
    if fp.GetReference() == 'U201':     # corps du module seulement (l'antenne est geree par KEEPOUT)
        x, y = pcbnew.ToMM(fp.GetPosition().x) - ORIGIN[0], pcbnew.ToMM(fp.GetPosition().y) - ORIGIN[1]
        return [x - 9.3, y - 13.05, x + 9.3, y + 13.05]
    side = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    cy = fp.GetCourtyard(side)
    b = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
    return [pcbnew.ToMM(b.GetLeft()) - ORIGIN[0], pcbnew.ToMM(b.GetTop()) - ORIGIN[1],
            pcbnew.ToMM(b.GetRight()) - ORIGIN[0], pcbnew.ToMM(b.GetBottom()) - ORIGIN[1]]
def is_tht(fp): return any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in fp.Pads())
def inter(a, b, g=0.15): return not (a[2] + g <= b[0] or b[2] + g <= a[0] or a[3] + g <= b[1] or b[3] + g <= a[1])
fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
placed = []    # (ref, bbox, side, tht)
def conflicts(ref, fp, bb):
    conflicts.last = 'bord/zone interdite'
    if ref.startswith('H'):
        pass
    elif bb[0] < 0.4 or bb[1] < 0.4 or bb[2] > BOARD_W - 0.4 or bb[3] > BOARD_H - 0.4:
        if ref not in ('U201', 'J101', 'J201', 'J501', 'J301'):
            return True
    for (r, owner) in KEEPOUT:
        if ref != owner and inter(bb, r, 0):
            return True
    side, tht = fp.IsFlipped(), is_tht(fp)
    for (r2, b2, s2, t2) in placed:
        if (s2 == side or tht or t2) and inter(bb, b2):
            conflicts.last = r2
            return True
    return False
order = sorted(fps, key=lambda r: (r not in FIXED, -abs((lambda b: (b[2]-b[0])*(b[3]-b[1]))(bbox_mm(fps[r])))))
moved = []
for ref in order:
    fp = fps[ref]
    bb = bbox_mm(fp)
    if ref in FIXED or not conflicts(ref, fp, bb):
        if ref in FIXED and conflicts(ref, fp, bb):
            print('ATTENTION conflit :', ref, 'avec', getattr(conflicts, 'last', '?'), [round(v, 1) for v in bb])
        placed.append((ref, bb, fp.IsFlipped(), is_tht(fp))); continue
    x0, y0 = PLACE[ref][0], PLACE[ref][1]
    best = None
    for r in [i * 0.25 for i in range(1, 80)]:
        for k in range(max(8, int(r * 8))):
            import math
            a = 2 * math.pi * k / max(8, int(r * 8))
            dx, dy = round(r * math.cos(a) / 0.25) * 0.25, round(r * math.sin(a) / 0.25) * 0.25
            fp.SetPosition(P(x0 + dx, y0 + dy))
            b2 = bbox_mm(fp)
            if not conflicts(ref, fp, b2):
                best = (x0 + dx, y0 + dy, b2); break
        if best: break
    if not best:
        print('IMPOSSIBLE de placer', ref); fp.SetPosition(P(x0, y0)); continue
    moved.append((ref, round(best[0] - x0, 2), round(best[1] - y0, 2)))
    placed.append((ref, best[2], fp.IsFlipped(), is_tht(fp)))
print('deplaces par legalisation :', moved)

# contour : rectangle a coins arrondis (r = 3 mm)
def seg(a, b, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetLayer(layer); s.SetWidth(mm(w)); board.Add(s)
def arc(c, start, mid, end, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*start), P(*mid), P(*end)); s.SetLayer(layer); s.SetWidth(mm(w)); board.Add(s)
R = 3.0; W, H = BOARD_W, BOARD_H; k = R * (1 - 0.70710678)
seg((R, 0), (W - R, 0)); seg((W, R), (W, H - R)); seg((W - R, H), (R, H)); seg((0, H - R), (0, R))
arc(None, (W - R, 0), (W - k, k), (W, R)); arc(None, (W, H - R), (W - k, H - k), (W - R, H))
arc(None, (R, H), (k, H - k), (0, H - R)); arc(None, (0, R), (k, k), (R, 0))

# routage / zones / textes
import pcb_route, pcb_silk
texts = pcb_route.apply(board, nets, P, mm)
hidden = pcb_silk.apply(board, ORIGIN, BOARD_W, BOARD_H, texts)
print('references sans place (masquees en serigraphie, visibles sur F.Fab) :', hidden)

pcbnew.SaveBoard(f'{PROJ}.kicad_pcb', board)
# remplissage des zones apres rechargement (regles du projet .kicad_pro prises en compte)
board = pcbnew.LoadBoard(f'{PROJ}.kicad_pcb')
board.BuildConnectivity()
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(f'{PROJ}.kicad_pcb', board)
print('PCB ecrit :', len(comps), 'empreintes,', len(nets), 'nets,', len(board.GetTracks()), 'pistes/vias,', len(board.Zones()), 'zones')
