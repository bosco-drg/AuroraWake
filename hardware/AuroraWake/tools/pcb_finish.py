# -*- coding: utf-8 -*-
"""Finition d'un PCB deja route (ex. apres Freerouting), SANS toucher au placement :
  1. pistes plus fines que le minimum -> elargies a 0,2 mm ; pistes pendantes supprimees
  2. connectivite calculee par net (pads / pistes / vias / plans)
  3. routeur A* sur grille (2 couches) pour relier les groupes d'un meme net encore separes
  4. pads de plan (GND / PGND) isoles -> piste courte + via vers le plan de la face arriere
  5. vias de couture GND entre les deux faces
  6. remplissage des zones, sauvegarde
Usage (depuis hardware/AuroraWake) : python3 tools/pcb_finish.py
Une copie de sauvegarde AuroraWake.kicad_pcb.bak est ecrite avant modification.
"""
import heapq, math, shutil, sys, os
import pcbnew

PCB = 'AuroraWake.kicad_pcb'
OX, OY, BW, BH = 100.0, 100.0, 100.0, 80.0           # contour carte (mm, absolu) -- OX/OY relus dans main()
RES = 0.1                                             # pas de grille (mm)
NX, NY = int(BW / RES) + 1, int(BH / RES) + 1
EDGE = 0.5                                            # distance cuivre <-> bord
MIN_W = 0.2
VIA_D, VIA_DRILL = 0.6, 0.3
PWR_LED = {'+12V', 'PGND', '/VIN_RAW', '/VIN_FUSED', '/LED_K'}
PGND_REGION = [(0.3, 0.3), (44.3, 0.3), (44.3, 42.3), (14.0, 42.3), (14.0, 35.3), (8.0, 35.3), (8.0, 40.0), (0.3, 40.0)]
ANTENNA = (44.5, 0.0, 92.5, 6.9)                      # zone interdite antenne (coords locales)
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)

mm, MM = pcbnew.ToMM, pcbnew.FromMM

def clearance_of(net):
    return 0.25 if net in PWR_LED else 0.2
NPTH_CLEAR = 0.3

def in_poly(x, y, poly):
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside

def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def rect_dist(px, py, r):
    dx = max(r[0] - px, 0, px - r[2]); dy = max(r[1] - py, 0, py - r[3])
    return math.hypot(dx, dy)

# ------------------------------------------------------------------ geometrie des objets cuivre
class Obj:
    """objet cuivre simplifie : kind 'seg' (ax,ay,bx,by,halfw) / 'rect' (x0,y0,x1,y1) / 'circ' (cx,cy,r)"""
    __slots__ = ('kind', 'g', 'layers', 'net', 'item')
    def __init__(s, kind, g, layers, net, item):
        s.kind, s.g, s.layers, s.net, s.item = kind, g, layers, net, item
    def dist(s, x, y):
        g = s.g
        if s.kind == 'seg': return seg_dist(x, y, g[0], g[1], g[2], g[3]) - g[4]
        if s.kind == 'rect': return rect_dist(x, y, g)
        return math.hypot(x - g[0], y - g[1]) - g[2]
    def bbox(s):
        g = s.g
        if s.kind == 'seg':
            return (min(g[0], g[2]) - g[4], min(g[1], g[3]) - g[4], max(g[0], g[2]) + g[4], max(g[1], g[3]) + g[4])
        if s.kind == 'rect': return g
        return (g[0] - g[2], g[1] - g[2], g[0] + g[2], g[1] + g[2])

def collect(board):
    objs = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            lay = tuple(l for l in LAYERS if p.IsOnLayer(l))
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                lay = LAYERS
            if not lay: continue
            b = p.GetBoundingBox()
            g = (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()))
            if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
                c = p.GetPosition(); objs.append(Obj('circ', (mm(c.x), mm(c.y), (g[2] - g[0]) / 2), lay, p.GetNetname(), p))
            else:
                objs.append(Obj('rect', g, lay, p.GetNetname(), p))
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            c = t.GetPosition(); objs.append(Obj('circ', (mm(c.x), mm(c.y), mm(t.GetWidth(pcbnew.F_Cu)) / 2), LAYERS, t.GetNetname(), t))
        else:
            a, b = t.GetStart(), t.GetEnd()
            objs.append(Obj('seg', (mm(a.x), mm(a.y), mm(b.x), mm(b.y), mm(t.GetWidth()) / 2), (t.GetLayer(),), t.GetNetname(), t))
    return objs

def touches(a, b):
    if not set(a.layers) & set(b.layers): return False
    ab, bb = a.bbox(), b.bbox()
    if ab[2] < bb[0] - 0.01 or bb[2] < ab[0] - 0.01 or ab[3] < bb[1] - 0.01 or bb[3] < ab[1] - 0.01: return False
    # echantillonnage de a, distance a b
    pts = []
    g = a.g
    if a.kind == 'seg':
        n = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.05))
        pts = [(g[0] + (g[2] - g[0]) * i / n, g[1] + (g[3] - g[1]) * i / n, g[4]) for i in range(n + 1)]
    elif a.kind == 'circ':
        pts = [(g[0], g[1], g[2])]
    else:
        cx, cy = (g[0] + g[2]) / 2, (g[1] + g[3]) / 2
        pts = [(cx, cy, min(g[2] - g[0], g[3] - g[1]) / 2)]
        if b.kind != 'rect':
            return b.dist(*_clamp(b, g)) <= 0.001 if False else _rect_obj_touch(g, b)
        return not (g[2] < b.g[0] or b.g[2] < g[0] or g[3] < b.g[1] or b.g[3] < g[1])
    return any(b.dist(x, y) <= r + 0.001 for (x, y, r) in pts)

def _clamp(b, g): return (0, 0)
def _rect_obj_touch(g, b):
    if b.kind == 'circ':
        return rect_dist(b.g[0], b.g[1], g) <= b.g[2] + 0.001
    # segment vs rectangle : echantillonnage du segment
    s = b.g; n = max(2, int(math.hypot(s[2] - s[0], s[3] - s[1]) / 0.05))
    return any(rect_dist(s[0] + (s[2] - s[0]) * i / n, s[1] + (s[3] - s[1]) * i / n, g) <= s[4] + 0.001 for i in range(n + 1))

def clusters(objs, net, plane_polys=None):
    """composantes connexes des objets d'un net ; plane_polys = {layer: SHAPE_POLY_SET} (zones remplies)"""
    items = [o for o in objs if o.net == net]
    parent = list(range(len(items)))
    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if f(i) != f(j) and touches(items[i], items[j]):
                parent[f(i)] = f(j)
    # plans : chaque ilot de zone remplie fusionne les objets qui le touchent
    if plane_polys:
        for lay, ps in plane_polys.items():
            for k in range(ps.OutlineCount()):
                isl = pcbnew.SHAPE_POLY_SET(); isl.AddOutline(ps.Outline(k))
                for h in range(ps.HoleCount(k)): isl.AddHole(ps.Hole(k, h))
                hit = []
                for i, o in enumerate(items):
                    if lay not in o.layers: continue
                    cx, cy = _center(o)
                    if isl.Contains(pcbnew.VECTOR2I(MM(cx), MM(cy))) or _pad_in_zone(o, isl):
                        hit.append(i)
                for i in hit[1:]:
                    parent[f(i)] = f(hit[0])
    groups = {}
    for i, o in enumerate(items):
        groups.setdefault(f(i), []).append(o)
    return list(groups.values())

def _center(o):
    g = o.g
    if o.kind == 'seg': return (g[0], g[1])
    if o.kind == 'circ': return (g[0], g[1])
    return ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)

def _pad_in_zone(o, isl):
    """pad relie a un ilot par rayons thermiques : un point juste a l'exterieur du pad est dans l'ilot"""
    if o.kind == 'seg':
        g = o.g; return isl.Contains(pcbnew.VECTOR2I(MM(g[2]), MM(g[3])))
    g = o.bbox(); cx, cy = (g[0] + g[2]) / 2, (g[1] + g[3]) / 2
    for (x, y) in ((g[0] - 0.3, cy), (g[2] + 0.3, cy), (cx, g[1] - 0.3), (cx, g[3] + 0.3)):
        if isl.Contains(pcbnew.VECTOR2I(MM(x), MM(y))):
            return True
    return False

# ------------------------------------------------------------------ grille d'obstacles
def gidx(x, y): return int(round((y - OY) / RES)) * NX + int(round((x - OX) / RES))
def gxy(i): return (OX + (i % NX) * RES, OY + (i // NX) * RES)

def build_maps(objs, net, halfw, avoid_pgnd, margin=0.03):
    """blocked[layer] pour une piste (demi-largeur halfw) ; vblk : via interdite"""
    maps = {l: bytearray(NX * NY) for l in LAYERS}
    vblk = bytearray(NX * NY)
    for o in objs:
        if o.net == net and o.net != '': continue
        c = max(clearance_of(o.net), clearance_of(net))
        if o.item is not None and isinstance(o.item, pcbnew.PAD) and o.item.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            c = NPTH_CLEAR
        for (r, target) in ((c + halfw + margin, 'trk'), (c + VIA_D / 2 + 0.03, 'via')):
            b = o.bbox()
            i0, i1 = int((b[0] - r - OX) / RES) - 1, int((b[2] + r - OX) / RES) + 2
            j0, j1 = int((b[1] - r - OY) / RES) - 1, int((b[3] + r - OY) / RES) + 2
            for j in range(max(0, j0), min(NY, j1)):
                y = OY + j * RES
                for i in range(max(0, i0), min(NX, i1)):
                    x = OX + i * RES
                    if o.dist(x, y) < r:
                        if target == 'trk':
                            for l in o.layers: maps[l][j * NX + i] = 1
                        else:
                            vblk[j * NX + i] = 1
    # bords, antenne, zone de puissance (sauf nets de puissance)
    for j in range(NY):
        y = j * RES
        for i in range(NX):
            x = i * RES
            k = j * NX + i
            bad = (x < EDGE + halfw or y < EDGE + halfw or x > BW - EDGE - halfw or y > BH - EDGE - halfw
                   or (ANTENNA[0] <= x <= ANTENNA[2] and ANTENNA[1] <= y <= ANTENNA[3]))
            if not bad and avoid_pgnd and in_poly(x, y, PGND_REGION):
                bad = True
            if bad:
                maps[LAYERS[0]][k] = maps[LAYERS[1]][k] = 1; vblk[k] = 1
    # trous existants : distance trou-trou >= 0,5 mm
    for (hx, hy, hr) in HOLES:
        r = hr + VIA_DRILL / 2 + 0.55
        for j in range(int((hy - r - OY) / RES), int((hy + r - OY) / RES) + 2):
            for i in range(int((hx - r - OX) / RES), int((hx + r - OX) / RES) + 2):
                if 0 <= i < NX and 0 <= j < NY and math.hypot(OX + i * RES - hx, OY + j * RES - hy) < r:
                    vblk[j * NX + i] = 1
    # zones interdites (rule areas) de la carte et des empreintes
    for (x0, y0, x1, y1, notrk) in RULE_AREAS:
        for j in range(max(0, int((y0 - OY) / RES) - 4), min(NY, int((y1 - OY) / RES) + 5)):
            for i in range(max(0, int((x0 - OX) / RES) - 4), min(NX, int((x1 - OX) / RES) + 5)):
                vblk[j * NX + i] = 1
                if notrk: maps[LAYERS[0]][j * NX + i] = maps[LAYERS[1]][j * NX + i] = 1
    for k in range(NX * NY):
        if maps[LAYERS[0]][k] or maps[LAYERS[1]][k]: vblk[k] = 1
    return maps, vblk

HOLES, RULE_AREAS = [], []
def collect_holes(board):
    HOLES.clear(); RULE_AREAS.clear()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                c = p.GetPosition(); HOLES.append((mm(c.x), mm(c.y), mm(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2))
        for z in fp.Zones():
            if z.GetIsRuleArea():
                b = z.GetBoundingBox()
                RULE_AREAS.append((mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()), z.GetDoNotAllowTracks()))
    for z in board.Zones():
        if z.GetIsRuleArea():
            b = z.GetBoundingBox()
            RULE_AREAS.append((mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()), z.GetDoNotAllowTracks()))
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            c = t.GetPosition(); HOLES.append((mm(c.x), mm(c.y), mm(t.GetDrillValue()) / 2))

def cells_of(group, layers=LAYERS):
    out = set()
    for o in group:
        b = o.bbox()
        for j in range(int((b[1] - OY) / RES), int((b[3] - OY) / RES) + 2):
            for i in range(int((b[0] - OX) / RES), int((b[2] - OX) / RES) + 2):
                if 0 <= i < NX and 0 <= j < NY and o.dist(OX + i * RES, OY + j * RES) <= 0.0:
                    for l in o.layers:
                        if l in layers: out.add((l, j * NX + i))
    return out

def astar(maps, vblk, starts, goal, goal_pts, b_cost=1.6, via_cost=60):
    """goal : fonction (layer, idx) -> bool ; goal_pts : points pour l'heuristique"""
    def h(k):
        x, y = k % NX, k // NX
        return min(max(abs(x - gx), abs(y - gy)) + 0.414 * min(abs(x - gx), abs(y - gy)) for gx, gy in goal_pts)
    openh, best, prev = [], {}, {}
    starts = [s for s in starts if not maps[s[0]][s[1]]]
    for s in starts:
        best[s] = 0.0; heapq.heappush(openh, (h(s[1]), 0.0, s))
    D = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    n = 0
    while openh:
        f, g, s = heapq.heappop(openh)
        if g > best.get(s, 1e18): continue
        if goal(s):
            path = [s]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path[::-1]
        n += 1
        if n > 3_000_000: return None
        l, k = s
        x, y = k % NX, k // NX
        mul = b_cost if l == pcbnew.B_Cu else 1.0
        for dx, dy, c in D:
            nx_, ny_ = x + dx, y + dy
            if not (0 <= nx_ < NX and 0 <= ny_ < NY): continue
            nk = ny_ * NX + nx_
            if maps[l][nk]: continue
            if dx and dy and (maps[l][y * NX + nx_] or maps[l][ny_ * NX + x]): continue
            ns = (l, nk); ng = g + c * mul
            if ng < best.get(ns, 1e18):
                best[ns] = ng; prev[ns] = s; heapq.heappush(openh, (ng + h(nk), ng, ns))
        if not vblk[k]:
            ol = LAYERS[1] if l == LAYERS[0] else LAYERS[0]
            ns = (ol, k); ng = g + via_cost
            if ng < best.get(ns, 1e18) and not maps[ol][k]:
                best[ns] = ng; prev[ns] = s; heapq.heappush(openh, (ng + h(k), ng, ns))
    return None

def emit(board, path, net, w, endvia=False):
    ni = board.FindNet(net)
    pts = [(l, gxy(k)) for l, k in path]
    segs, vias = [], []
    cur = [pts[0]]
    for p in pts[1:]:
        if p[0] != cur[-1][0]:
            segs.append(cur); vias.append(p[1]); cur = [p]
        else:
            cur.append(p)
    segs.append(cur)
    added = 0
    for s in segs:
        # simplification : on garde les points de changement de direction
        keep = [s[0]]
        for a, b, c in zip(s, s[1:], s[2:]):
            d1 = (round((b[1][0] - a[1][0]) / RES), round((b[1][1] - a[1][1]) / RES))
            d2 = (round((c[1][0] - b[1][0]) / RES), round((c[1][1] - b[1][1]) / RES))
            if d1 != d2: keep.append(b)
        if len(s) > 1: keep.append(s[-1])
        for a, b in zip(keep, keep[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(a[1][0]), MM(a[1][1]))); t.SetEnd(pcbnew.VECTOR2I(MM(b[1][0]), MM(b[1][1])))
            t.SetWidth(MM(w)); t.SetLayer(a[0]); t.SetNet(ni); board.Add(t); added += 1
    if endvia:
        vias.append(pts[-1][1])
    uniq = []
    existing = [(mm(t.GetPosition().x), mm(t.GetPosition().y)) for t in board.GetTracks()
                if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == net]
    for v in vias:
        if all(math.hypot(v[0] - u[0], v[1] - u[1]) > 0.9 for u in uniq + existing): uniq.append(v)
    vias = uniq
    for (x, y) in vias:
        v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL)); v.SetNet(ni); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        board.Add(v)
    return added, len(vias)

# ------------------------------------------------------------------ etapes
def widen(board):
    n = 0
    for t in board.GetTracks():
        if not isinstance(t, pcbnew.PCB_VIA) and mm(t.GetWidth()) < MIN_W - 1e-4:
            t.SetWidth(MM(MIN_W)); n += 1
    return n

def widen_conflicts(board, widened_nets):
    objs = collect(board)
    segs = [o for o in objs if o.kind == 'seg']
    bad = set()
    for a in segs:
        if a.net not in widened_nets: continue
        for b in objs:
            if b.net == a.net or not set(a.layers) & set(b.layers): continue
            ab, bb = a.bbox(), b.bbox()
            c = max(clearance_of(a.net), clearance_of(b.net))
            if ab[2] + c < bb[0] or bb[2] + c < ab[0] or ab[3] + c < bb[1] or bb[3] + c < ab[1]: continue
            g = a.g; n = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.05))
            if any(b.dist(g[0] + (g[2] - g[0]) * i / n, g[1] + (g[3] - g[1]) * i / n) < g[4] + c - 0.001 for i in range(n + 1)):
                cnt = lambda nn: sum(1 for o in segs if o.net == nn)
                victim = a.net if (b.kind != 'seg' or cnt(a.net) <= cnt(b.net)) else b.net
                if victim.startswith('/'): bad.add(victim)
    return bad

def remove_dangling(board):
    removed = 0
    while True:
        objs = collect(board)
        dead = []
        for o in objs:
            if o.kind != 'seg': continue
            g = o.g
            for (ex, ey) in ((g[0], g[1]), (g[2], g[3])):
                end = Obj('circ', (ex, ey, 0.01), o.layers, o.net, None)
                if not any(p is not o and p.net == o.net and set(p.layers) & set(o.layers) and p.dist(ex, ey) <= 0.01 for p in objs):
                    dead.append(o.item); break
        if not dead: return removed
        for it in dead: board.Delete(it)     # Delete (et non Remove : Remove corrompt les types SWIG)
        removed += len(dead)

def fill(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

def zone_polys(board, net):
    out = {}
    for z in board.Zones():
        if z.GetNetname() == net and not z.GetIsRuleArea():
            for l in LAYERS:
                if z.IsOnLayer(l):
                    out.setdefault(l, pcbnew.SHAPE_POLY_SET()).Append(z.GetFilledPolysList(l))
    return out

def route_net(board, net, w):
    objs = collect(board)
    planes = zone_polys(board, net)
    groups = clusters(objs, net, planes)
    if len(groups) <= 1: return 0
    # un net dont un pad est dans la zone de puissance doit pouvoir y entrer
    pin_in_pgnd = any(o.kind != 'seg' and in_poly(_center(o)[0] - OX, _center(o)[1] - OY, PGND_REGION)
                      for o in objs if o.net == net)
    avoid = net not in PWR_LED and net != 'GND' and not pin_in_pgnd
    maps, vblk = build_maps(objs, net, w / 2, avoid); mw = (w, 0.03)
    groups.sort(key=len, reverse=True)
    main = groups[0]; done = 0
    for g in groups[1:]:
        A = cells_of(g); B = cells_of(main)
        if not A or not B:
            print(f'   {net}: groupe sans cellule, ignore'); continue
        Bk = set(B)
        pts = [(k % NX, k // NX) for _, k in list(B)[::max(1, len(B) // 30)]]
        path = None
        for ww, mg in [(w, 0.03)] + [(x, 0.03) for x in (0.3, 0.2) if x < w] + [(0.2, 0.0)]:
            if (ww, mg) != mw:                 # grille toujours calculee pour la largeur utilisee
                maps, vblk = build_maps(objs, net, ww / 2, avoid, mg); mw = (ww, mg)
            path = astar(maps, vblk, list(A), lambda s: s in Bk, pts)
            if path: break
        if not path:
            desc = ', '.join((f'{o.item.GetParentFootprint().GetReference()}.{o.item.GetNumber()}' if isinstance(o.item, pcbnew.PAD)
                              else f'{o.kind}@({_center(o)[0]-OX:.1f},{_center(o)[1]-OY:.1f})') for o in g[:4])
            print(f'   {net}: ECHEC du routage d un groupe ({len(g)} objets : {desc})'); continue
        a, v = emit(board, path, net, ww)
        collect_holes(board)
        print(f'   {net}: groupe relie ({a} segments, {v} vias)')
        main = main + g; done += 1
    return done

def pad_to_plane(board, ref, padnum, net, w=0.4, near=None):
    """relie un pad CMS (face avant) au plan de la face arriere par une piste courte + via
    near = (x, y) locaux pour choisir parmi plusieurs pads de meme numero"""
    objs = collect(board)
    planes = zone_polys(board, net)
    if pcbnew.B_Cu not in planes: return False
    pl = planes[pcbnew.B_Cu]
    cands = [o for o in objs if o.kind != 'seg' and o.item is not None and isinstance(o.item, pcbnew.PAD)
             and o.item.GetParentFootprint().GetReference() == ref and o.item.GetNumber() == padnum]
    if near:
        cands.sort(key=lambda o: math.hypot(_center(o)[0] - OX - near[0], _center(o)[1] - OY - near[1]))
    pad = cands[0]
    starts = [s for s in cells_of([pad], (pcbnew.F_Cu,))]
    def goal(s):
        l, k = s
        if l != pcbnew.F_Cu or vblk[k]: return False
        x, y = gxy(k)
        return all(pl.Contains(pcbnew.VECTOR2I(MM(x + dx), MM(y + dy))) for dx, dy in
                   ((0, 0), (0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5)))
    c = _center(pad)
    path = None
    for ww, mg in ((w, 0.03), (0.2, 0.03), (0.2, 0.0)):
        maps, vblk = build_maps(objs, net, ww / 2, False, mg)
        path = astar(maps, vblk, starts, goal, [(int((c[0] - OX) / RES), int((c[1] - OY) / RES))], via_cost=1e9)
        if path: w = ww; break
    if not path:
        print(f'   {ref}.{padnum}: pas de place pour une via vers {net}'); return False
    emit(board, path, net, w, endvia=True)
    collect_holes(board)
    print(f'   {ref}.{padnum} -> via {net}')
    return True

def stitch(board, net='GND', pitch=5.0):
    """vias de couture la ou les deux faces sont remplies de GND (hors zone de puissance)"""
    objs = collect(board)
    planes = zone_polys(board, net)
    if len(planes) < 2: return 0
    maps, vblk = build_maps(objs, net, 0.1, True)
    n = 0
    y = 2.0
    while y < BH - 1.0:
        x = 2.0
        while x < BW - 1.0:
            best = None
            for dy in (0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5):
                for dx in (0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5):
                    px, py = OX + x + dx, OY + y + dy
                    k = gidx(px, py)
                    if 0 <= k < NX * NY and not vblk[k] and all(
                            planes[l].Contains(pcbnew.VECTOR2I(MM(px + ex), MM(py + ey)))
                            for l in LAYERS for ex, ey in ((0, 0), (0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6))):
                        best = (px, py); break
                if best: break
            if best:
                v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(best[0]), MM(best[1])))
                v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL)); v.SetNet(board.FindNet(net))
                v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v); n += 1
                HOLES.append((best[0], best[1], VIA_DRILL / 2))
                # bloque les cellules autour de cette via
                for j in range(-12, 13):
                    for i in range(-12, 13):
                        kk = gidx(best[0] + i * RES, best[1] + j * RES)
                        if 0 <= kk < NX * NY: vblk[kk] = 1
            x += pitch
        y += pitch
    return n

def fp_of(board, ref):
    return [f for f in board.GetFootprints() if f.GetReference() == ref][0]

def pad_of(board, ref, num):
    return [p for p in fp_of(board, ref).Pads() if p.GetNumber() == num][0]

def fix_audio_crossing(board):
    """OUTP (broche 9) est sous OUTN (broche 10) : la ferrite de OUTP doit etre sous celle de OUTN"""
    p9, p10 = pad_of(board, 'U401', '9').GetPosition(), pad_of(board, 'U401', '10').GetPosition()
    f2, f3 = fp_of(board, 'FB402'), fp_of(board, 'FB403')
    if (p9.y > p10.y) == (f2.GetPosition().y > f3.GetPosition().y):
        return False
    for a, b in (('FB402', 'FB403'), ('C404', 'C405')):
        fa, fb = fp_of(board, a), fp_of(board, b)
        pa, pb = fa.GetPosition(), fb.GetPosition()
        ra, rb = fa.Reference().GetPosition(), fb.Reference().GetPosition()
        fa.SetPosition(pb); fb.SetPosition(pa)
        fa.Reference().SetPosition(rb); fb.Reference().SetPosition(ra)   # les reperes restent en place
    for t in [t for t in board.GetTracks() if t.GetNetname() in ('/SPK_P_RAW', '/SPK_N_RAW', '/SPK_P', '/SPK_N')]:
        board.Delete(t)
    return True

def stub(board, ref, num, target_ref, target_num, w=0.2):
    """piste droite d'un pad vers le centre d'un autre pad du meme net (ex. broche GND -> pad central)"""
    a, b = pad_of(board, ref, num), pad_of(board, target_ref, target_num)
    pa, pb = a.GetPosition(), b.GetPosition()
    end = pcbnew.VECTOR2I(pb.x, pa.y) if abs(pa.x - pb.x) > abs(pa.y - pb.y) else pcbnew.VECTOR2I(pa.x, pb.y)
    t = pcbnew.PCB_TRACK(board); t.SetStart(pa); t.SetEnd(end); t.SetWidth(MM(w)); t.SetLayer(pcbnew.F_Cu)
    t.SetNet(a.GetNet()); board.Add(t)

def route_pad(board, ref, num, net, w, targets=None):
    """relie un pad isole (ex. dans un ilot de zone) a d'autres objets de son net (targets = ['REF.PAD', ...])"""
    objs = collect(board)
    pad = [o for o in objs if o.kind != 'seg' and isinstance(o.item, pcbnew.PAD)
           and o.item.GetParentFootprint().GetReference() == ref and o.item.GetNumber() == num][0]
    if targets:
        others = [o for o in objs if o.kind != 'seg' and isinstance(o.item, pcbnew.PAD)
                  and f'{o.item.GetParentFootprint().GetReference()}.{o.item.GetNumber()}' in targets]
    else:
        others = [o for o in objs if o.net == net and o is not pad]
    B = set(cells_of(others)); A = cells_of([pad])
    maps, vblk = build_maps(objs, net, w / 2, False)
    pts = [(k % NX, k // NX) for _, k in list(B)[::max(1, len(B) // 40)]]
    path = astar(maps, vblk, list(A), lambda s: s in B, pts)
    if not path:
        print(f'   {ref}.{num}: echec'); return
    emit(board, path, net, w); collect_holes(board)
    print(f'   {ref}.{num} relie a {net}')

def stitch_islands(board, net='GND'):
    """via dans chaque ilot de zone de la face avant sans via ni trou traversant"""
    objs = collect(board)
    planes = zone_polys(board, net)
    maps, vblk = build_maps(objs, net, 0.1, False)
    fpl = planes.get(pcbnew.F_Cu); bpl = planes.get(pcbnew.B_Cu)
    n = 0
    for k in range(fpl.OutlineCount()):
        isl = pcbnew.SHAPE_POLY_SET(); isl.AddOutline(fpl.Outline(k))
        for h in range(fpl.HoleCount(k)): isl.AddHole(fpl.Hole(k, h))
        if any(len(o.layers) == 2 and isl.Contains(pcbnew.VECTOR2I(MM(_center(o)[0]), MM(_center(o)[1])))
               for o in objs if o.net == net and o.kind != 'seg'):
            continue
        bb = fpl.Outline(k).BBox()
        found = None
        y = mm(bb.GetTop())
        while y < mm(bb.GetBottom()) and not found:
            x = mm(bb.GetLeft())
            while x < mm(bb.GetRight()):
                kk = gidx(x, y)
                if 0 <= kk < NX * NY and not vblk[kk] and all(
                        isl.Contains(pcbnew.VECTOR2I(MM(x + ex), MM(y + ey))) and bpl.Contains(pcbnew.VECTOR2I(MM(x + ex), MM(y + ey)))
                        for ex, ey in ((0, 0), (0.45, 0), (-0.45, 0), (0, 0.45), (0, -0.45))):
                    found = (x, y); break
                x += RES
            y += RES
        if found:
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(found[0]), MM(found[1])))
            v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL)); v.SetNet(board.FindNet(net))
            v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v); n += 1
            HOLES.append((found[0], found[1], VIA_DRILL / 2))
            for j in range(-12, 13):
                for i in range(-12, 13):
                    kk = gidx(found[0] + i * RES, found[1] + j * RES)
                    if 0 <= kk < NX * NY: vblk[kk] = 1
    return n

def main():
    global OX, OY
    shutil.copy(PCB, PCB + '.bak')
    board = pcbnew.LoadBoard(PCB)
    bb = board.GetBoardEdgesBoundingBox()           # la carte a pu etre deplacee dans KiCad
    OX, OY = mm(bb.GetLeft()) + 0.05, mm(bb.GetTop()) + 0.05
    print(f'origine carte : ({OX:.3f}, {OY:.3f}) mm')
    collect_holes(board)
    wn = set(t.GetNetname() for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and mm(t.GetWidth()) < MIN_W - 1e-4)
    print('1. pistes elargies a 0,2 mm :', widen(board))
    redo = widen_conflicts(board, wn)
    for net in sorted(redo):
        for t in [t for t in board.GetTracks() if t.GetNetname() == net]:
            board.Delete(t)
    print('   nets en conflit apres elargissement (rerouts) :', sorted(redo))
    print('   pistes pendantes supprimees :', remove_dangling(board))
    # J202 : rayons thermiques bloques -> connexion pleine
    for fp in board.GetFootprints():
        if fp.GetReference() == 'J202':
            for p in fp.Pads():
                if p.GetNetname() == 'GND': p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    fill(board)
    print('2. vias de plan pour les pads isoles')
    for ref, pad, net in [('C301', '2', 'PGND'), ('C302', '2', 'PGND'), ('R303', '2', 'PGND'),
                          ('U501', '3', 'GND'), ('U501', '8', 'GND')]:
        pad_to_plane(board, ref, pad, net)
    fill(board)
    print('   croisement des sorties audio corrige :', fix_audio_crossing(board))
    for num in ('11', '15'):
        stub(board, 'U401', num, 'U401', '17')
    fill(board)
    print('3. routage des nets incomplets')
    for net in ('/SPK_P_RAW', '/SPK_N_RAW', '/SPK_P', '/SPK_N'):
        route_net(board, net, 0.5)
    for net in sorted(redo):
        route_net(board, net, 0.25)
    for net, w in [('VBUS', 0.5), ('+3V3', 0.4), ('+12V', 0.5), ('/SPK_N_RAW', 0.4), ('/VIN_SENSE', 0.25),
                   ('PGND', 0.4)]:
        route_net(board, net, w)
    fill(board)
    # la zone +12V est coupee par la rangee C102/D102/U301/Q301 : liaison explicite vers le cote principal
    route_pad(board, 'C303', '1', '+12V', 1.0, targets=['D301.1', 'Q101.3', 'J301.1', 'C304.1'])
    fill(board)
    print('4. vias de couture GND :', stitch(board))
    fill(board)
    print('   vias dans les ilots GND isoles :', stitch_islands(board))
    # blindage microSD : la patte '11' (60,3 ; 62,3) est enfermee entre +3V3 et SD_DAT2 ;
    # couloir libre au-dessus -> piste 0,4 mm + via GND placees explicitement (verifiees au DRC)
    if not pad_to_plane(board, 'J501', '11', 'GND', 0.4, near=(60.33, 62.28)):
        sh = sorted([p for p in fp_of(board, 'J501').Pads() if p.GetNumber() == '11'],
                    key=lambda p: math.hypot(mm(p.GetPosition().x) - OX - 60.33, mm(p.GetPosition().y) - OY - 62.28))[0]
        c = sh.GetPosition(); vx, vy = c.x - MM(0.32), c.y - MM(2.88)
        t = pcbnew.PCB_TRACK(board); t.SetStart(c); t.SetEnd(pcbnew.VECTOR2I(vx, vy)); t.SetWidth(MM(0.4))
        t.SetLayer(pcbnew.F_Cu); t.SetNet(sh.GetNet()); board.Add(t)
        v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(vx, vy)); v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL))
        v.SetNet(sh.GetNet()); v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v)
        print('   J501.11 : via de blindage placee explicitement')
    fill(board)
    fill(board)
    print('5. dernieres liaisons GND')
    route_net(board, 'GND', 0.3)
    fill(board)
    # masse de la carte SD (J501.6, VSS) : retour explicite vers la masse des condensateurs de decouplage SD
    route_pad(board, 'J501', '6', 'GND', 0.4, targets=['C501.2', 'C502.2', 'U501.3', 'U501.8'])
    fill(board)
    # si le blindage microSD reste enferme par la boucle +3V3 de Freerouting : on la retire,
    # on relie le blindage, puis on reroute le +3V3 par un autre chemin
    objs = collect(board)
    shield_grp = [g for g in clusters(objs, 'GND', zone_polys(board, 'GND'))
                  if any(isinstance(o.item, pcbnew.PAD) and o.item.GetParentFootprint().GetReference() == 'J501' for o in g)
                  and len(g) < 10]
    if shield_grp:
        box = (OX + 55.0, OY + 58.0, OX + 62.2, OY + 64.2)
        cut = [t for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == '+3V3'
               and all(box[0] <= mm(v.x) <= box[2] and box[1] <= mm(v.y) <= box[3] for v in (t.GetStart(), t.GetEnd()))]
        for t in cut: board.Delete(t)
        print('   boucle +3V3 autour du blindage retiree :', len(cut), 'segments')
        fill(board)
        route_net(board, 'GND', 0.4)
        fill(board)
        route_net(board, '+3V3', 0.8)
        fill(board)
    for fp in board.GetFootprints():
        if fp.GetReference() == 'J501':
            cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            fp.Reference().SetPosition(pcbnew.VECTOR2I(cy.GetCenter().x, cy.GetTop() - MM(0.9)))
    pcbnew.SaveBoard(PCB, board)
    # pistes pendantes signalees par le DRC de KiCad -> supprimees
    import subprocess, re, tempfile
    rpt = os.path.join(tempfile.mkdtemp(), 'drc.rpt')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '-o', rpt, PCB], capture_output=True)
    dang = re.findall(r'track_dangling[^\n]*\n[^\n]*\n\s*@\(([\d.]+) mm, ([\d.]+) mm\): Track \[([^\]]+)\] on (\w\.Cu), length ([\d.]+) mm', open(rpt).read())
    vdang = re.findall(r'via_dangling[^\n]*\n[^\n]*\n\s*@\(([\d.]+) mm, ([\d.]+) mm\): Via \[([^\]]+)\]', open(rpt).read())
    if dang or vdang:
        board = pcbnew.LoadBoard(PCB)
        for (x, y, net) in vdang:
            for t in list(board.GetTracks()):
                if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == net and math.hypot(mm(t.GetPosition().x) - float(x), mm(t.GetPosition().y) - float(y)) < 0.01:
                    board.Delete(t); break
        for (x, y, net, lay, L) in dang:
            for t in list(board.GetTracks()):
                if (not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == net and t.GetLayerName() == lay
                        and abs(mm(t.GetLength()) - float(L)) < 0.002):
                    board.Delete(t); break
        fill(board)
        pcbnew.SaveBoard(PCB, board)
    print('pistes / vias pendantes supprimees en fin de traitement :', len(dang), '/', len(vdang))
    print('PCB sauvegarde.')

if __name__ == '__main__':
    os.chdir(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    main()
