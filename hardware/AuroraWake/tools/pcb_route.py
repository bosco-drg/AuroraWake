# -*- coding: utf-8 -*-
"""Cuivre de puissance, plans, vias et serigraphie (coordonnees locales carte, mm).
Un point de piste peut etre un tuple (x, y) ou une reference de pad 'REF.PAD' (ex. 'Q101.2'),
eventuellement decalee : ('Q101.2', dx, dy). Les signaux restants sont routes a la main.
"""
import pcbnew

# Region de puissance PGND (12 V entree + panneau LED) -- coords locales
# NT101 : pad 1 (PGND) a gauche dans la region, pad 2 (GND) a droite hors region.
PGND_REGION = [(0.3, 0.3), (44.3, 0.3), (44.3, 42.3), (14.0, 42.3), (14.0, 35.3),
               (8.0, 35.3), (8.0, 40.0), (0.3, 40.0)]
BOARD_REGION = [(0.3, 0.3), (99.7, 0.3), (99.7, 79.7), (0.3, 79.7)]

# Pistes de puissance : (net, largeur mm, couche, [points])
TRACKS = [
    ('/VIN_RAW',   2.5, 'F', ['J101.1', ('J101.1', 0, -4.5), 'F101.1']),
    ('/VIN_FUSED', 2.5, 'F', ['F101.2', ('Q101.2', 0, -5.0), 'Q101.2']),
    ('/LED_K',     2.5, 'F', ['J301.2', 'D301.2']),
    ('/LED_K',     2.5, 'F', ['D301.2', ('Q301.2', -0.4, -5.0), 'Q301.2']),
    ('+12V',       2.5, 'F', ['J301.1', 'D301.1']),
    ('PGND',       2.0, 'F', ['Q301.3', ('C303.2', 0, -4.0), 'C303.2']),          # source Q301 -> C303(-)
    ('+12V',       1.0, 'F', ['C101.1', (1.8, 31.0), (1.8, 45.2), 'C103.1']),     # vers le buck
    ('+12V',       0.6, 'F', ['C103.1', (7.2, 'C103.1'), (7.2, 'U101.3'), 'U101.3']),
    ('+12V',       0.6, 'F', ['U101.3', ('U101.3', 0, 2.35), 'C104.1']),
]
# Vias PGND (0,8/0,4) : (net, point, raccordement depuis)
VIAS = [
    ('PGND', ('C303.2', 0, -2.4), None), ('PGND', ('C303.2', 0, -1.2), None),
    ('PGND', ('C101.2', 0, 2.6), 'C101.2'), ('PGND', ('C101.2', 1.4, 2.6), 'C101.2'),
    ('PGND', ('C102.2', 0, -1.6), 'C102.2'),
    ('PGND', ('D102.2', 0, -2.0), 'D102.2'),
    ('PGND', ('R101.2', -1.5, 0), 'R101.2'),
    ('PGND', ('C304.2', 0, 1.6), 'C304.2'),
    ('PGND', ('NT101.1', -2.0, 0), 'NT101.1'),
]
TEXTS = [
    ('12V DC', 6.5, 22.0, 1.0),
    ('LED+', 35.0, 1.3, 0.9), ('LED-', 40.1, 1.3, 0.9),
    ('PGND', 26.0, 33.5, 0.8),
    ('SET', 14.0, 77.6, 1.0), ('UP', 27.0, 77.6, 1.0), ('DOWN', 40.0, 77.6, 1.0),
    ('SPK', 84.0, 72.0, 0.9),
    ('OLED', 3.5, 53.8, 0.9),
    ('UART', 97.5, 40.6, 0.8), ('EXT', 93.5, 40.6, 0.8),
    ('RESET', 88.0, 23.4, 0.8), ('BOOT', 88.0, 31.4, 0.8),
]
BACK_TEXTS = [('AuroraWake V2 - reveil ESP32-S3 - 2026', 50.0, 30.0, 1.5)]

def apply(board, nets, P, mm):
    layer = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pads.setdefault(f'{fp.GetReference()}.{p.GetNumber()}', p.GetPosition())

    def loc(pt):
        """tuple (x,y) / 'REF.PAD' / ('REF.PAD', dx, dy) / (x, 'REF.PAD') / ('REF.PAD', y) -> VECTOR2I"""
        if isinstance(pt, str):
            return pads[pt]
        if isinstance(pt[0], str) and len(pt) == 3:
            v = pads[pt[0]]; return pcbnew.VECTOR2I(v.x + mm(pt[1]), v.y + mm(pt[2]))
        x = pads[pt[0]].x if isinstance(pt[0], str) else P(pt[0], 0).x
        y = pads[pt[1]].y if isinstance(pt[1], str) else P(0, pt[1]).y
        return pcbnew.VECTOR2I(x, y)

    def add_track(net, a, b, w, ly):
        if a == b:
            return
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a); t.SetEnd(b); t.SetWidth(mm(w)); t.SetLayer(layer[ly]); t.SetNet(nets[net])
        board.Add(t)

    for net, w, ly, pts in TRACKS:
        vs = [loc(p) for p in pts]
        for a, b in zip(vs, vs[1:]):
            add_track(net, a, b, w, ly)

    for net, pt, frm in VIAS:
        v = pcbnew.PCB_VIA(board)
        pos = loc(pt)
        v.SetPosition(pos); v.SetWidth(mm(0.8)); v.SetDrill(mm(0.4)); v.SetNet(nets[net])
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        board.Add(v)
        if frm:
            add_track(net, loc(frm), pos, 0.8, 'F')

    def zone(net, ly, poly, prio, conn):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer[ly]); z.SetNet(nets[net])
        ol = z.Outline(); ol.NewOutline()
        for (x, y) in poly:
            p = P(x, y); ol.Append(p.x, p.y)
        z.SetAssignedPriority(prio)
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(conn)
        z.SetThermalReliefGap(mm(0.4))
        z.SetThermalReliefSpokeWidth(mm(0.8))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetZoneName(f'{net}_{ly}')
        board.Add(z)

    THT_TH = pcbnew.ZONE_CONNECTION_THT_THERMAL      # CMS en plein, traversants en thermique
    zone('GND', 'B', BOARD_REGION, 0, THT_TH)
    zone('GND', 'F', BOARD_REGION, 0, THT_TH)
    zone('PGND', 'B', PGND_REGION, 5, THT_TH)
    zone('+12V', 'F', PGND_REGION, 5, THT_TH)

    texts = []
    for (txt, x, y, h), back in [(t, False) for t in TEXTS] + [(t, True) for t in BACK_TEXTS]:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt); t.SetPosition(P(x, y))
        t.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
        t.SetMirrored(back)
        t.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h))); t.SetTextThickness(mm(max(0.15, h * 0.15)))
        t.SetTextAngleDegrees(0)
        board.Add(t)
        texts.append(t)
    return texts
