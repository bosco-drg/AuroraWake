# -*- coding: utf-8 -*-
"""Generateur de schema hierarchique KiCad 9 pour AuroraWake.
Usage : python3 gen.py <dossier_sortie>
"""
import sys, os, re, uuid, json, collections
from kilib import get_symbol, pins, prop, dump, val, q
import design

OUT = sys.argv[1]
PROJECT = 'AuroraWake'
FPDIR = '/usr/share/kicad/footprints'
NS = uuid.UUID('6f1c1e5a-3c1b-4f5e-9d6a-a0e0a0a0a001')
def U(*k):  # uuid deterministe => regenerations stables (diff git propres)
    return str(uuid.uuid5(NS, '/'.join(map(str, k))))

G = 2.54
def snap(v, g=G): return round(v / g) * g
def f(v): return ('%.4f' % v).rstrip('0').rstrip('.')

ROOT_UUID = U('root')
SHORT = {'power.kicad_sch': 'Alimentation', 'mcu.kicad_sch': 'Microcontroleur', 'led_driver.kicad_sch': 'Panneau LED',
         'audio.kicad_sch': 'Audio', 'sd_card.kicad_sch': 'Carte SD', 'rtc.kicad_sch': 'RTC', 'display.kicad_sch': 'Ecran', 'buttons.kicad_sch': 'Boutons'}
PAPER = {'A0': (1189, 841), 'A1': (841, 594), 'A2': (594, 420), 'A3': (420, 297), 'A4': (297, 210)}

# ------------------------------------------------------------------ global/local nets
net_sheets = collections.defaultdict(set)
for sh in design.SHEETS:
    for (ref, lid, v, fp, nets, kw) in sh['parts']:
        for n in nets.values():
            net_sheets[n].add(sh['file'])
GLOBAL = set()  # feuille unique : tous les labels sont locaux

# ------------------------------------------------------------------ verification empreintes
def fp_pads(fp):
    lib, name = fp.split(':')
    p = f'{FPDIR}/{lib}.pretty/{name}.kicad_mod'
    if not os.path.exists(p):
        return None
    return set(re.findall(r'\(pad "([^"]*)"', open(p).read())) - {''}

errors = []
for sh in design.SHEETS:
    for (ref, lid, v, fp, nets, kw) in sh['parts']:
        if not fp:
            continue
        pads = fp_pads(fp)
        if pads is None:
            errors.append(f'{ref}: empreinte introuvable {fp}'); continue
        pn = {p['num'] for p in pins(get_symbol(lid))}
        miss = pn - pads
        if miss:
            errors.append(f'{ref}: broches {sorted(miss)} sans pad dans {fp}')
if errors:
    print('\n'.join(errors)); sys.exit(1)

# ------------------------------------------------------------------ geometrie symbole
def body_bbox(sym):
    xs, ys = [], []
    for e in sym:
        if isinstance(e, list) and e[0] == 'symbol':
            for g in e:
                if not isinstance(g, list): continue
                if g[0] == 'rectangle':
                    for k in g:
                        if isinstance(k, list) and k[0] in ('start', 'end'):
                            xs.append(float(k[1])); ys.append(float(k[2]))
                elif g[0] == 'polyline':
                    for k in g:
                        if isinstance(k, list) and k[0] == 'pts':
                            for xy in k[1:]:
                                xs.append(float(xy[1])); ys.append(float(xy[2]))
                elif g[0] == 'circle':
                    c = [k for k in g if isinstance(k, list) and k[0] == 'center'][0]
                    r = float([k for k in g if isinstance(k, list) and k[0] == 'radius'][0][1])
                    xs += [float(c[1]) - r, float(c[1]) + r]; ys += [float(c[2]) - r, float(c[2]) + r]
    for p in pins(sym):
        xs.append(p['x']); ys.append(p['y'])
    if not xs: xs, ys = [-2, 2], [-2, 2]
    # coordonnees ecran (y vers le bas)
    return min(xs), -max(ys), max(xs), -min(ys)

OUTWARD = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}   # angle broche lib -> direction ecran
LABEL_ANGLE = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}
ROT_GND = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}
ROT_VCC = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}

def text_w(s): return 1.0 * len(s) + 3.0

def pin_groups(sym, nets, ref):
    """Regroupe les broches par position ; renvoie [(x,y,dir,net)]"""
    groups = collections.OrderedDict()
    for p in pins(sym):
        groups.setdefault((p['x'], p['y']), []).append(p)
    res = []
    for (x, y), ps in groups.items():
        assigned = {nets[p['num']] for p in ps if p['num'] in nets}
        if len(assigned) > 1:
            raise SystemExit(f'{ref}: broches empilees {[p["num"] for p in ps]} sur nets differents {assigned}')
        if not assigned:
            if all(p['hidden'] and p['type'] == 'no_connect' for p in ps):
                continue
            raise SystemExit(f'{ref}: broche(s) {[p["num"] for p in ps]} ({ps[0]["name"]}) non affectee(s)')
        vis = [p for p in ps if not p['hidden']] or ps
        res.append((x, -y, OUTWARD[vis[0]['a'] % 360], assigned.pop()))
    return res

def extent(sym, nets, ref):
    """bbox ecran incluant fils + labels, relatif a l'origine"""
    x0, y0, x1, y1 = body_bbox(sym)
    for (px, py, d, net) in pin_groups(sym, nets, ref):
        if net == 'NC':
            continue
        L = 2 * G + (6 if net in design.POWER else text_w(net) + (3 if net in GLOBAL else 0))
        ex, ey = px + d[0] * L, py + d[1] * L
        x0, x1, y0, y1 = min(x0, ex), max(x1, ex), min(y0, ey), max(y1, ey)
    return x0 - 2, y0 - 6, x1 + 2, y1 + 6

# ------------------------------------------------------------------ emission
def eff(size=1.27, justify=None, hide=False):
    s = f'(effects (font (size {size} {size}))'
    if justify: s += f' (justify {justify})'
    if hide: s += ' (hide yes)'
    return s + ')'

class SheetWriter:
    def __init__(self, fname, title, page_uuid_path, paper='A3', page='1'):
        self.fname, self.title, self.path, self.paper = fname, title, page_uuid_path, paper
        self.items, self.libs = [], collections.OrderedDict()
        self.uuid = U('sheetfile', fname)
        self.pwr_n = 0

    def lib(self, lid):
        if lid not in self.libs:
            self.libs[lid] = get_symbol(lid)
        return self.libs[lid]

    def symbol(self, ref, lid, value, fp, X, Y, rot=0, extra=None, hide_val=False, in_bom=True, pins_list=None, justify_ref='left'):
        sym = self.lib(lid)
        x0, y0, x1, y1 = body_bbox(sym)
        is_pwr = lid.startswith('power:')
        u = U(self.fname, ref, X, Y)
        out = [f'\t(symbol\n\t\t(lib_id {q(lid)})\n\t\t(at {f(X)} {f(Y)} {rot})\n\t\t(unit 1)\n'
               f'\t\t(exclude_from_sim no)\n\t\t(in_bom {"yes" if in_bom and not is_pwr and not ref.startswith(("H", "NT")) else "no"})\n\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid {q(u)})']
        if is_pwr:
            rx, ry = X, Y
            vx, vy = self._pwr_val_pos
            out.append(f'\t\t(property "Reference" {q(ref)} (at {f(rx)} {f(ry)} 0) {eff(hide=True)})')
            out.append(f'\t\t(property "Value" {q(value)} (at {f(vx)} {f(vy)} 0) {eff(hide=hide_val)})')
        else:
            out.append(f'\t\t(property "Reference" {q(ref)} (at {f(X + x1 + 1)} {f(Y + y0 - 1.5)} 0) {eff(justify="left")})')
            out.append(f'\t\t(property "Value" {q(value)} (at {f(X + x1 + 1)} {f(Y + y1 + 2.5)} 0) {eff(justify="left")})')
        out.append(f'\t\t(property "Footprint" {q(fp)} (at {f(X)} {f(Y)} 0) {eff(hide=True)})')
        out.append(f'\t\t(property "Datasheet" {q(prop(sym, "Datasheet") or "~")} (at {f(X)} {f(Y)} 0) {eff(hide=True)})')
        out.append(f'\t\t(property "Description" {q(prop(sym, "Description") or "")} (at {f(X)} {f(Y)} 0) {eff(hide=True)})')
        for k, v in (extra or {}).items():
            out.append(f'\t\t(property {q(k)} {q(v)} (at {f(X)} {f(Y)} 0) {eff(hide=True)})')
        for p in pins(sym):
            out.append(f'\t\t(pin {q(p["num"])} (uuid {q(U(u, "pin", p["num"]))}))')
        out.append(f'\t\t(instances\n\t\t\t(project {q(PROJECT)}\n\t\t\t\t(path {q(self.path)}\n\t\t\t\t\t(reference {q(ref)})\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)')
        out.append('\t)')
        self.items.append('\n'.join(out))

    def wire(self, a, b):
        self.items.append(f'\t(wire (pts (xy {f(a[0])} {f(a[1])}) (xy {f(b[0])} {f(b[1])})) (stroke (width 0) (type default)) (uuid {q(U(self.fname, "w", a, b))}))')

    def noconn(self, x, y):
        self.items.append(f'\t(no_connect (at {f(x)} {f(y)}) (uuid {q(U(self.fname, "nc", x, y))}))')

    def label(self, net, x, y, d):
        ang = LABEL_ANGLE[d]
        just = 'left bottom' if ang in (0, 90) else 'right bottom'
        u = U(self.fname, 'lbl', net, x, y)
        if net in GLOBAL:
            gj = 'left' if ang in (0, 90) else 'right'
            self.items.append(f'\t(global_label {q(net)} (shape bidirectional) (at {f(x)} {f(y)} {ang}) (fields_autoplaced yes) {eff(justify=gj)} (uuid {q(u)})\n'
                              f'\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {f(x)} {f(y)} 0) {eff(justify=gj, hide=True)})\n\t)')
        else:
            self.items.append(f'\t(label {q(net)} (at {f(x)} {f(y)} {ang}) (fields_autoplaced yes) {eff(justify=just)} (uuid {q(u)}))')

    def power(self, net, x, y, d):
        lid, kind = design.POWER[net]
        rot = (ROT_GND if kind == 'gnd' else ROT_VCC)[d]
        self.pwr_n += 1
        self._pwr_val_pos = (x + d[0] * 5.5, y + d[1] * 5.5 + (0 if d[1] else -1.5))
        ref = '#PWR%s%02d' % (self.prefix, self.pwr_n)
        self.symbol(ref, lid, net, '', x, y, rot=rot)

    def rect(self, x0, y0, x1, y1):
        self.items.append(f'\t(rectangle (start {f(x0)} {f(y0)}) (end {f(x1)} {f(y1)}) (stroke (width 0.3) (type dash)) (fill (type none)) (uuid {q(U(self.fname, "rect", x0, y0))}))')

    def text(self, s, x, y, size=1.5):
        self.items.append(f'\t(text {q(s)} (exclude_from_sim no) (at {f(x)} {f(y)} 0) {eff(size, "left bottom")} (uuid {q(U(self.fname, "txt", s[:40], x, y))}))')

    def place_part(self, part, X, Y):
        ref, lid, value, fp, nets, kw = part
        sym = self.lib(lid)
        if lid == 'power:PWR_FLAG':
            # drapeau : symbole + fil vers le bas + symbole d'alimentation
            self._pwr_val_pos = (X, Y - 3)
            self.symbol(ref, lid, value, '', X, Y, in_bom=False)
            self.wire((X, Y), (X, Y + 2 * G))
            net = nets['1']
            if net in design.POWER: self.power(net, X, Y + 2 * G, (0, 1))
            else: self.label(net, X, Y + 2 * G, (0, 1))
            return
        self.symbol(ref, lid, value, fp, X, Y, extra=kw)
        for (px, py, d, net) in pin_groups(sym, nets, ref):
            ax, ay = X + px, Y + py
            if net == 'NC':
                self.noconn(ax, ay); continue
            bx, by = ax + d[0] * 2 * G, ay + d[1] * 2 * G
            self.wire((ax, ay), (bx, by))
            if net in design.POWER: self.power(net, bx, by, d)
            else: self.label(net, bx, by, d)

    def write(self, extra_head='', sheet_instances=''):
        W, H = PAPER[self.paper]
        libs = '\n'.join('\t\t' + dump(s, 2) for s in self.libs.values())
        s = (f'(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n\t(generator_version "9.0")\n'
             f'\t(uuid {q(self.uuid)})\n\t(paper {q(self.paper)})\n'
             f'\t(title_block\n\t\t(title {q(self.title)})\n\t\t(date "2026-11-17")\n\t\t(rev "V2.0")\n\t\t(company "AuroraWake")\n'
             f'\t\t(comment 1 "Reveil lumineux - ESP32-S3 - entree jack 12 V")\n\t\t(comment 2 "Genere par script (gen.py) - verifier ERC/DRC avant fabrication")\n\t)\n'
             f'\t(lib_symbols\n{libs}\n\t)\n' + extra_head + '\n'.join(self.items) + '\n' + sheet_instances +
             '\t(embedded_fonts no)\n)\n')
        open(os.path.join(OUT, self.fname), 'w').write(s)

def layout(parts, sheetw, x0, y0, width):
    """placement en rangees dans un cadre (x0,y0) de largeur donnee ; renvoie y bas"""
    x, y, rowh = x0, y0, 0
    for part in parts:
        ref, lid, value, fp, nets, kw = part
        sym = sheetw.lib(lid)
        if lid == 'power:PWR_FLAG':
            bb = (-4, -8, 8, 12)
        else:
            bb = extent(sym, nets, ref)
            bb = (bb[0], bb[1], bb[2] + text_w(value) * 0.6, bb[3])
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if x + w > x0 + width and x > x0:
            x, y, rowh = x0, y + rowh + 4, 0
        X, Y = snap(x - bb[0]), snap(y - bb[1])
        sheetw.place_part(part, X, Y)
        x += w + 4
        rowh = max(rowh, h)
    return y + rowh

class _Dummy(SheetWriter):
    def __init__(self): super().__init__('dummy', '', '/', 'A0')
    def write(self, *a, **k): pass

NOTE_DY = 4.2
TITLE_H = 12
def section_size(sh, width):
    d = _Dummy(); d.prefix = 'x'
    bottom = layout(sh['parts'], d, 0, TITLE_H, width)
    return bottom + 6 + NOTE_DY * len(sh['notes']) + 4

# ------------------------------------------------------------------ feuille unique
os.makedirs(OUT, exist_ok=True)
for old in [sh['file'] for sh in design.SHEETS]:
    p = os.path.join(OUT, old)
    if os.path.exists(p): os.remove(p)

MARGIN, GAP, BOTTOM_RESERVED = 20, 10, 45
def pack(paper, ncol):
    W, H = PAPER[paper]
    colw = (W - 2 * MARGIN - (ncol - 1) * GAP) / ncol
    cols = [MARGIN + 0.0] * ncol
    placed = []
    for sh in design.SHEETS:
        h = section_size(sh, colw - 10)
        c = min(range(ncol), key=lambda i: cols[i])
        placed.append((sh, MARGIN + c * (colw + GAP), cols[c], colw, h))
        cols[c] += h + GAP
    ok = max(cols) <= H - BOTTOM_RESERVED
    return ok, placed

for paper, ncol in [('A1', 2), ('A1', 3), ('A1', 4), ('A0', 3), ('A0', 4)]:
    ok, placed = pack(paper, ncol)
    if ok: break
else:
    raise SystemExit('le schema ne tient pas sur une page A0')

sw = SheetWriter(f'{PROJECT}.kicad_sch', 'AuroraWake V2 - schema complet', f'/{ROOT_UUID}', paper)
sw.uuid = ROOT_UUID
for i, (sh, x, y, w, h) in enumerate(placed):
    sw.prefix = str(i + 1)
    sw.rect(x, y, x + w, y + h)
    sw.text(f'{i + 1}. {sh["title"].upper()}', x + 4, y + 8, 3.0)
    bottom = layout(sh['parts'], sw, x + 5, y + TITLE_H, w - 10)
    for k, line in enumerate(sh['notes']):
        sw.text(line, x + 5, bottom + 6 + k * NOTE_DY, 1.8 if k == 0 else 1.4)
# trous de fixation
sw.prefix = '0'
W, H = PAPER[paper]
for k, ref in enumerate(['H1', 'H2', 'H3', 'H4']):
    sw.symbol(ref, 'Mechanical:MountingHole', 'M3', 'MountingHole:MountingHole_3.2mm_M3', MARGIN + 10 + k * 20, H - 25)
sw.write(sheet_instances=f'\t(sheet_instances\n\t\t(path "/" (page "1"))\n\t)\n')
print('page', paper, ncol, 'colonnes')

# ------------------------------------------------------------------ projet
pro = {
    "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 3},
    "board": {"design_settings": {"defaults": {}, "rules": {"min_clearance": 0.2, "min_track_width": 0.2, "min_through_hole_diameter": 0.2, "min_via_diameter": 0.6, "min_hole_to_hole": 0.5, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25}}},
    "net_settings": {"classes": [
        {"name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "microvia_diameter": 0.3, "microvia_drill": 0.1},
        {"name": "PWR_LED", "clearance": 0.25, "track_width": 2.5, "via_diameter": 1.0, "via_drill": 0.5, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 0, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "microvia_diameter": 0.3, "microvia_drill": 0.1},
        {"name": "PWR_5V", "clearance": 0.2, "track_width": 0.8, "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 1, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "microvia_diameter": 0.3, "microvia_drill": 0.1},
        {"name": "USB", "clearance": 0.2, "track_width": 0.3, "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 3, "diff_pair_gap": 0.15, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.3, "microvia_diameter": 0.3, "microvia_drill": 0.1},
    ], "meta": {"version": 4},
        "netclass_patterns": [
            {"netclass": "PWR_LED", "pattern": n} for n in ["*VIN_RAW", "*VIN_FUSED", "+12V", "PGND", "*LED_K"]
        ] + [{"netclass": "PWR_5V", "pattern": n} for n in ["+5V", "VSYS", "+5V_AUD", "*BUCK_SW", "+3V3", "VBUS", "*SPK_*"]]
          + [{"netclass": "USB", "pattern": n} for n in ["*USB_DP", "*USB_DN"]]},
    "sheets": [[ROOT_UUID, "Root"]],
    "text_variables": {},
}
# fusion avec le projet existant (on ne touche qu'aux classes de nets et aux regles minimales)
pp = os.path.join(OUT, f'{PROJECT}.kicad_pro')
if os.path.exists(pp):
    cur = json.load(open(pp))
    cur.setdefault('net_settings', {}).update({k: pro['net_settings'][k] for k in ('classes', 'netclass_patterns')})
    cur.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {}).update(pro['board']['design_settings']['rules'])
    pro = cur
json.dump(pro, open(pp, 'w'), indent=2)
print('OK ->', OUT, '| nets globaux :', len(GLOBAL))
