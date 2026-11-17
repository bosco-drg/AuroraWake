# -*- coding: utf-8 -*-
"""Placement AuroraWake V2 : coordonnees locales carte (origine coin haut-gauche, mm, y vers le bas).
Chaque entree : (x, y, rotation_deg[, 'B'])  -- 'B' = face inferieure.

Organisation (vue de dessus) :
  haut-gauche  : entree 12 V + pilotage panneau LED (zone PGND), connecteurs sur les bords gauche/haut
  haut-centre  : module ESP32-S3, antenne au bord superieur
  haut-droite  : USB-C (bord droit), RESET/BOOT
  milieu-gauche: buck 5 V + LDO 3,3 V (une rangee alignee), rangee de passifs en dessous
  milieu       : RTC (pile CR2032 au dos), centre-droit : audio
  bas          : boutons (bord bas), microSD (bord bas), haut-parleur (bord bas), barrettes (bord droit)
Tous les passifs d'un meme bloc ont la meme orientation et sont alignes sur un pas regulier.
"""
BOARD_W, BOARD_H = 100.0, 80.0
ORIGIN = (100.0, 100.0)

PLACE = {}
def put(ref, x, y, rot=0, side=None):
    PLACE[ref] = (x, y, rot) if side is None else (x, y, rot, side)
def row(refs, x0, y, pitch, rot=0):
    for i, r in enumerate(refs):
        if r: put(r, round(x0 + i * pitch, 3), y, rot)
def col(refs, x, y0, pitch, rot=0):
    for i, r in enumerate(refs):
        if r: put(r, x, round(y0 + i * pitch, 3), rot)

# ---------------- trous M3, symetriques ----------------
put('H1', 3.5, 3.5); put('H2', 96.5, 3.5); put('H3', 3.5, 76.5); put('H4', 96.5, 76.5)

# ---------------- ENTREE 12 V (zone PGND) ----------------
put('J101', 13.0, 14.5, 270)          # jack, ouverture bord gauche
put('F101', 20.5, 5.0, 0)             # fusible CMS NANO2
put('Q101', 27.0, 16.0, 90)           # P-MOS anti-inversion (languette = drain en haut)
col(['D101', 'R101'], 19.5, 15.0, 5.0, 90)
put('C304', 28.0, 3.5, 0)
put('C101', 7.5, 27.5, 0)             # 470 uF
put('C102', 17.0, 26.5, 90)
put('D102', 21.5, 27.0, 90)           # TVS
put('NT101', 8.0, 37.5, 0)            # point unique PGND <-> GND

# ---------------- PANNEAU LED (zone PGND) ----------------
put('J301', 35.0, 6.9, 0)             # bornier, entree des fils vers le bord haut
put('D301', 37.5, 16.3, 0)            # roue libre : K sous LED+, A sous LED-
put('Q301', 39.0, 25.0, 0)            # N-MOS, languette (LED_K) a droite
put('U301', 28.5, 26.0, 180)          # driver : sorties cote Q301
col(['R302', 'R301', 'R303'], 31.6, 24.0, 3.3, 90)
put('R304', 24.8, 26.5, 90)
row(['C301', 'C302'], 25.5, 30.0, 3.0, 90)
put('C303', 37.7, 37.0, 180)          # 100 uF : '-' a gauche, sous la source de Q301

# ---------------- BUCK 5 V + LDO 3,3 V : rangee alignee y = 48,5 ----------------
put('C103', 5.0, 48.5, 270)
put('U101', 10.0, 48.5, 0)
put('C104', 10.0, 51.8, 0)
row(['R102', None, 'R103'], 7.8, 44.6, 2.2, 0)
put('C105', 13.5, 48.0, 90)
put('L101', 19.5, 48.5, 0)
row(['C106', 'C107'], 25.0, 48.5, 3.0, 90)
put('D103', 32.0, 48.5, 90)
put('U102', 39.5, 48.5, 0)
# rangee de passifs y = 55,5 (pas 3,4 mm)
row(['R105', 'R106', 'C111', 'R104', 'D105'], 8.5, 55.5, 3.4, 0)
put('D104', 28.0, 55.5, 0)
row(['C108', 'C109', 'C110'], 34.5, 55.5, 3.75, 0)

# ---------------- ECRAN + BOUTONS (bas-gauche) ----------------
put('J701', 3.5, 57.0, 0)
row(['C701', 'C702'], 7.0, 60.0, 2.1, 90)
for i, (sw, rpu, c, rs) in enumerate([('SW801', 'R801', 'C801', 'R802'),
                                      ('SW802', 'R803', 'C802', 'R804'),
                                      ('SW803', 'R805', 'C803', 'R806')]):
    cx = 14.0 + 13.0 * i                 # centre du bouton
    put(sw, cx - 3.25, 69.0, 0)          # origine = broche 1
    row([rpu, c, rs], cx - 2.5, 61.5, 2.5, 90)

# ---------------- MICROCONTROLEUR ----------------
put('U201', 68.5, 13.25, 0)           # module, antenne au bord haut
col(['C201', 'C202', 'R201', 'C203'], 55.8, 9.3, 2.1, 0)
put('J201', 95.5, 15.0, 90)           # USB-C, ouverture bord droit
put('U202', 86.0, 15.0, 0)
row(['R205', 'C204'], 84.3, 10.5, 3.4, 90)
row(['R203', 'R204'], 84.3, 19.5, 3.4, 90)
put('SW201', 88.0, 28.0, 0)
put('SW202', 88.0, 36.0, 0)
col(['R202', 'R206', 'D201'], 80.5, 24.5, 4.0, 90)
put('J203', 93.5, 44.0, 0)            # extension / JTAG
put('J202', 97.5, 44.0, 0)            # UART

# ---------------- RTC (pile au dos) ----------------
put('U601', 54.5, 44.5, 0)
row(['R601', 'R602', 'R603', 'C601'], 50.0, 36.5, 3.0, 90)   # au-dessus de U601
put('BT601', 53.0, 45.0, 0, 'B')

# ---------------- MICRO SD (bord bas) ----------------
put('J501', 56.0, 70.0, 180)
row(['R501', 'R502', 'R503', 'R504', 'R505', 'R506', 'R507', 'R508'], 45.5, 57.5, 3.0, 90)
col(['U501', 'C502', 'C501'], 66.5, 63.5, 3.3, 0)   # a droite du connecteur

# ---------------- BUZZER (sous le module ESP32) ----------------
put('BZ401', 67.6, 33.5, 0)
put('D401', 69.0, 42.5, 0)
put('Q401', 80.5, 41.0, 0)
row(['R402', 'R403'], 75.5, 44.5, 3.0, 90)

# ---------------- AUDIO (centre-droit) ----------------
put('U401', 73.0, 50.0, 0)
put('R401', 69.0, 50.0, 90)
put('C402', 73.0, 54.0, 0)
put('C401', 73.0, 56.5, 0)
put('FB401', 77.5, 56.5, 0)
col(['FB403', 'FB402'], 79.0, 49.0, 2.6, 0)   # OUTN (broche 10) au-dessus de OUTP (broche 9) : pas de croisement
col(['C405', 'C404'], 84.0, 49.0, 2.6, 0)
put('C403', 75.0, 62.0, 0)
put('J401', 83.0, 75.5, 0)            # haut-parleur, bord bas

# Tout est place explicitement : la legalisation ne fait que signaler les conflits.
FIXED = set(PLACE)
# Zones interdites a tout composant (hors proprietaire) : antenne ESP32 (coords locales)
KEEPOUT = [((44.5, 0.0, 92.5, 6.7), 'U201')]
