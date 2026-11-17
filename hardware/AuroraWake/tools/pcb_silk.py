# -*- coding: utf-8 -*-
"""Placement automatique des textes de serigraphie (references + textes de carte) sans chevauchement.
Pour chaque texte, on essaie des positions candidates autour de son composant (ou de sa position
souhaitee) et on garde la premiere qui ne touche ni pad, ni trait de serigraphie, ni autre texte,
ni le bord de carte. Sans solution : la reference est masquee en serigraphie (reste sur F.Fab).
"""
import math
import pcbnew

CLEAR_PAD = 0.25      # texte <-> pad (ouverture de masque)
CLEAR_SILK = 0.15     # texte <-> serigraphie
EDGE = 0.6            # texte <-> bord de carte
REF_H = 0.8           # hauteur des references (mm) -- minimum conseille JLCPCB
HIDE_REFS = ('H',)    # trous de fixation : pas de repere

def _mm(v): return pcbnew.ToMM(v)

def _seg_rect(ax, ay, bx, by, r):
    """segment [a,b] intersecte le rectangle r=(x0,y0,x1,y1) ? (Liang-Barsky)"""
    x0, y0, x1, y1 = r
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0: return False
        else:
            t = q / p
            if p < 0:
                if t > t1: return False
                t0 = max(t0, t)
            else:
                if t < t0: return False
                t1 = min(t1, t)
    return True

def _shape_segments(sh):
    """decompose un PCB_SHAPE en segments (x1,y1,x2,y2,demi-largeur)"""
    w = _mm(sh.GetWidth()) / 2
    t = sh.GetShape()
    if t == pcbnew.SHAPE_T_SEGMENT:
        a, b = sh.GetStart(), sh.GetEnd()
        return [(_mm(a.x), _mm(a.y), _mm(b.x), _mm(b.y), w)]
    if t == pcbnew.SHAPE_T_RECT:
        a, b = sh.GetStart(), sh.GetEnd()
        x0, y0, x1, y1 = _mm(a.x), _mm(a.y), _mm(b.x), _mm(b.y)
        out = [(x0, y0, x1, y0, w), (x1, y0, x1, y1, w), (x1, y1, x0, y1, w), (x0, y1, x0, y0, w)]
        if sh.IsFilled():
            out.append(('fill', min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
        return out
    if t in (pcbnew.SHAPE_T_CIRCLE, pcbnew.SHAPE_T_ARC):
        c = sh.GetCenter(); cx, cy = _mm(c.x), _mm(c.y); R = _mm(sh.GetRadius())
        if t == pcbnew.SHAPE_T_CIRCLE:
            a0, a1 = 0.0, 2 * math.pi
        else:
            s, e = sh.GetStart(), sh.GetEnd()
            a0 = math.atan2(_mm(s.y) - cy, _mm(s.x) - cx)
            a1 = a0 + math.radians(sh.GetArcAngle().AsDegrees())
        n = 24
        pts = [(cx + R * math.cos(a0 + (a1 - a0) * i / n), cy + R * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        out = [(p[0], p[1], q[0], q[1], w) for p, q in zip(pts, pts[1:])]
        if t == pcbnew.SHAPE_T_CIRCLE and sh.IsFilled():
            out.append(('fill', cx - R, cy - R, cx + R, cy + R))
        return out
    if t == pcbnew.SHAPE_T_POLY:
        b = sh.GetBoundingBox()
        return [('fill', _mm(b.GetLeft()), _mm(b.GetTop()), _mm(b.GetRight()), _mm(b.GetBottom()))]
    b = sh.GetBoundingBox()
    return [('fill', _mm(b.GetLeft()), _mm(b.GetTop()), _mm(b.GetRight()), _mm(b.GetBottom()))]

def _text_rect(t):
    b = t.GetEffectiveTextShape().BBox()     # trace reel des caracteres (sans interligne)
    return (_mm(b.GetLeft()), _mm(b.GetTop()), _mm(b.GetRight()), _mm(b.GetBottom()))

def _inter(a, b, g):
    return not (a[2] + g <= b[0] or b[2] + g <= a[0] or a[3] + g <= b[1] or b[3] + g <= a[1])

class Obstacles:
    def __init__(self, board, ORIGIN, W, H, side):
        self.segs, self.rects_pad, self.rects_txt, self.court = [], [], [], []
        self.ox, self.oy, self.W, self.H = ORIGIN[0], ORIGIN[1], W, H
        silk = pcbnew.F_SilkS if side == 'F' else pcbnew.B_SilkS
        cu = pcbnew.F_Cu if side == 'F' else pcbnew.B_Cu
        for fp in board.GetFootprints():
            for g in fp.GraphicalItems():
                if g.GetLayer() == silk and isinstance(g, pcbnew.PCB_SHAPE):
                    self.segs += _shape_segments(g)
            for p in fp.Pads():
                if p.IsOnLayer(cu) or p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                    b = p.GetBoundingBox()
                    self.rects_pad.append((_mm(b.GetLeft()), _mm(b.GetTop()), _mm(b.GetRight()), _mm(b.GetBottom())))
            if fp.IsFlipped() == (side == 'B'):
                cy = fp.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)
                if cy.OutlineCount():
                    b = cy.BBox()
                    self.court.append((fp.GetReference(), (_mm(b.GetLeft()), _mm(b.GetTop()), _mm(b.GetRight()), _mm(b.GetBottom()))))
        for t in board.GetTracks():   # vias : ouvertures de masque possibles
            if isinstance(t, pcbnew.PCB_VIA):
                b = t.GetBoundingBox()
                self.rects_pad.append((_mm(b.GetLeft()), _mm(b.GetTop()), _mm(b.GetRight()), _mm(b.GetBottom())))

    def ok(self, r, owner=None, strict=True):
        x0, y0 = self.ox + EDGE, self.oy + EDGE
        if r[0] < x0 or r[1] < y0 or r[2] > self.ox + self.W - EDGE or r[3] > self.oy + self.H - EDGE:
            return False
        for p in self.rects_pad:
            if _inter(r, p, CLEAR_PAD): return False
        for t in self.rects_txt:
            if _inter(r, t, CLEAR_SILK): return False
        g = CLEAR_SILK
        rr = (r[0] - g, r[1] - g, r[2] + g, r[3] + g)
        for s in self.segs:
            if s[0] == 'fill':
                if _inter(r, s[1:], g): return False
            else:
                w = s[4]
                if _seg_rect(s[0], s[1], s[2], s[3], (rr[0] - w, rr[1] - w, rr[2] + w, rr[3] + w)): return False
        if strict:   # eviter de passer sous le boitier d'un autre composant
            for ref, c in self.court:
                if ref != owner and _inter(r, c, 0): return False
        return True

def _candidates(cb, tw, th):
    """positions de centre autour de la boite cb=(x0,y0,x1,y1) pour un texte tw x th"""
    x0, y0, x1, y1 = cb
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    for d in (0.25, 0.6, 1.0, 1.5, 2.0, 2.8):
        for (px, py) in [(cx, y0 - th / 2 - d), (cx, y1 + th / 2 + d),
                         (x0 - tw / 2 - d, cy), (x1 + tw / 2 + d, cy),
                         (x0 + tw / 2, y0 - th / 2 - d), (x1 - tw / 2, y0 - th / 2 - d),
                         (x0 + tw / 2, y1 + th / 2 + d), (x1 - tw / 2, y1 + th / 2 + d),
                         (x0 - tw / 2 - d, y0 + th / 2), (x1 + tw / 2 + d, y0 + th / 2),
                         (x0 - tw / 2 - d, y1 - th / 2), (x1 + tw / 2 + d, y1 - th / 2)]:
            out.append((px, py))
    out.append((cx, cy))
    return out

def _place(text, cb, obs, owner, angles=(0,)):   # tous les textes horizontaux, lisibles depuis le bas
    for strict in (True, False):
        for ang in angles:
            text.SetTextAngleDegrees(ang)
            text.SetPosition(pcbnew.VECTOR2I(0, 0))
            r = _text_rect(text)
            tw, th = r[2] - r[0], r[3] - r[1]
            # decalage entre position d'ancrage et centre de la boite
            offx, offy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            for (px, py) in _candidates(cb, tw, th):
                text.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(px - offx), pcbnew.FromMM(py - offy)))
                rr = _text_rect(text)
                if obs.ok(rr, owner, strict):
                    obs.rects_txt.append(rr)
                    return True
    return False

def apply(board, ORIGIN, W, H, board_texts):
    """board_texts : liste de PCB_TEXT deja ajoutes (positions souhaitees)."""
    obsF = Obstacles(board, ORIGIN, W, H, 'F')
    obsB = Obstacles(board, ORIGIN, W, H, 'B')
    hidden = []
    # 1) textes de carte (prioritaires, autour de leur position souhaitee)
    for t in board_texts:
        p = t.GetPosition(); x, y = _mm(p.x), _mm(p.y)
        obs = obsB if t.GetLayer() == pcbnew.B_SilkS else obsF
        if not _place(t, (x, y, x, y), obs, None, angles=(0,)):
            hidden.append(t.GetText()); board.Remove(t)
    # 2) references : gros composants d'abord
    fps = sorted(board.GetFootprints(), key=lambda f: -f.GetArea() if hasattr(f, 'GetArea') else 0)
    def area(fp):
        b = fp.GetBoundingBox(False); return b.GetWidth() * b.GetHeight()
    fps = sorted(board.GetFootprints(), key=area, reverse=True)
    for fp in fps:
        ref = fp.Reference()
        if fp.GetReference().startswith(HIDE_REFS):
            ref.SetVisible(False); continue
        ref.SetVisible(True)
        side = 'B' if fp.IsFlipped() else 'F'
        ref.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(REF_H), pcbnew.FromMM(REF_H)))
        ref.SetTextThickness(pcbnew.FromMM(0.15))
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)
        b = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
        cb = (_mm(b.GetLeft()), _mm(b.GetTop()), _mm(b.GetRight()), _mm(b.GetBottom()))
        if fp.GetReference() == 'U201':       # module : texte dans le corps, sous l'antenne
            p = fp.GetPosition(); cb = (_mm(p.x) - 6, _mm(p.y) - 6, _mm(p.x) + 6, _mm(p.y) - 2)
        if not _place(ref, cb, obsB if side == 'B' else obsF, fp.GetReference()):
            ref.SetVisible(False)
            hidden.append(fp.GetReference())
    return hidden
