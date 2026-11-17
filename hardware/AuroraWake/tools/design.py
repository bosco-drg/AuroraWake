# -*- coding: utf-8 -*-
"""AuroraWake V2 -- description complete de la conception (composants + nets).
Chaque composant : (ref, lib_id, valeur, empreinte, {pin_number: net}, extra_props)
net "NC" = broche volontairement non connectee (drapeau no_connect).
"""

FP = dict(
    R0603='Resistor_SMD:R_0603_1608Metric',
    C0603='Capacitor_SMD:C_0603_1608Metric',
    C0805='Capacitor_SMD:C_0805_2012Metric',
    C1206='Capacitor_SMD:C_1206_3216Metric',
    C1210='Capacitor_SMD:C_1210_3225Metric',
    LED0603='LED_SMD:LED_0603_1608Metric',
    FB0805='Inductor_SMD:L_0805_2012Metric',
    TP='TestPoint:TestPoint_Pad_D1.5mm',
    SOD123='Diode_SMD:D_SOD-123',
)

def R(ref, val, a, b, fp=FP['R0603'], **kw):
    return (ref, 'Device:R', val, fp, {'1': a, '2': b}, kw)

def C(ref, val, a, b, fp=FP['C0603'], **kw):
    return (ref, 'Device:C', val, fp, {'1': a, '2': b}, kw)

def CP(ref, val, plus, minus, fp, **kw):
    return (ref, 'Device:C_Polarized', val, fp, {'1': plus, '2': minus}, kw)

def TP(ref, net):
    return (ref, 'Connector:TestPoint', net, FP['TP'], {'1': net}, {})

def LED(ref, val, a, k):
    return (ref, 'Device:LED', val, FP['LED0603'], {'2': a, '1': k}, {})

def FLAG(ref, net):
    return (ref, 'power:PWR_FLAG', 'PWR_FLAG', '', {'1': net}, {})

# Nets realises par des symboles d'alimentation (globaux)
POWER = {
    'GND':     ('power:GND', 'gnd'),
    'PGND':    ('power:GNDPWR', 'gnd'),
    '+12V':    ('power:+12V', 'vcc'),
    '+5V':     ('power:+5V', 'vcc'),
    '+3V3':    ('power:+3V3', 'vcc'),
    'VSYS':    ('power:VCC', 'vcc'),
    'VBUS':    ('power:VBUS', 'vcc'),
    '+5V_AUD': ('power:VCC', 'vcc'),
}

SHEETS = []

def sheet(fname, title, notes, parts):
    SHEETS.append(dict(file=fname, title=title, notes=notes, parts=parts))

# ---------------------------------------------------------------- 1. ALIMENTATION
sheet('power.kicad_sch', 'Alimentation 12 V -> 5 V -> 3,3 V', [
    "ALIMENTATION - choix et risques",
    "* J101 : jack CUI PJ-063AH (8 A, broche 2,0 mm, fiche 5,5x2,1). Charge totale max ~4,9 A (panneau 50 W + logique).",
    "* F101 : fusible 5x20 temporise T6,3A (remplacable). Panneau 60 W => passer en T8A (marge jack reduite).",
    "* Q101 : P-MOSFET en anti-inversion (perte ~0,35 W a 4,9 A au lieu de ~2,5 W pour une Schottky).",
    "  D101 Zener 15 V limite Vgs (Vgs max +-20 V). D102 TVS SMBJ15A apres Q101 : ecrete les surtensions.",
    "* NT101 : UNIQUE point de liaison PGND (retour LED) <-> GND (logique), place au pied de C101/J101.",
    "* U101 AP63205WU : buck 5 V/2 A, Vin max 32 V. EN par pont 100k/15k => demarrage a ~9 V (UVLO).",
    "* D103/D104 : OU de diodes 5V_buck / VBUS USB -> VSYS : programmation possible par USB seul (sans 12 V).",
    "* U102 AP7361C-33E : LDO 1 A, chute 0,36 V @1 A -> fonctionne des VSYS = 3,7 V (AMS1117 trop juste).",
    "* VIN_SENSE : pont 100k/15k -> 1,57 V a 12 V, 3,1 V a 24 V (ecretage TVS) -> ADC1 GPIO1.",
], [
    ('J101', 'Connector:Barrel_Jack', 'Jack 12V 8A (PJ-063AH)', 'Connector_BarrelJack:BarrelJack_CUI_PJ-063AH_Horizontal',
        {'1': 'VIN_RAW', '2': 'PGND'}, {'MPN': 'CUI PJ-063AH'}),
    ('F101', 'Device:Fuse', 'T6.3A 5x20', 'Fuse:Fuseholder_Cylinder-5x20mm_Schurter_0031_8201_Horizontal_Open',
        {'1': 'VIN_RAW', '2': 'VIN_FUSED'}, {'MPN': 'Porte-fusible Schurter 0031.8201 + fusible T6.3A 250V'}),
    ('Q101', 'Transistor_FET:Q_PMOS_GDS', 'AOD4185', 'Package_TO_SOT_SMD:TO-252-2',
        {'1': 'PFET_G', '2': 'VIN_FUSED', '3': '+12V'}, {'MPN': 'AOD4185 (P-MOS -40V -40A, ~15mOhm)'}),
    R('R101', '10k', 'PFET_G', 'PGND'),
    ('D101', 'Device:D_Zener', 'BZT52C15', FP['SOD123'], {'1': '+12V', '2': 'PFET_G'}, {}),
    ('D102', 'Device:D_Zener', 'SMBJ15A', 'Diode_SMD:D_SMB', {'1': '+12V', '2': 'PGND'}, {'MPN': 'SMBJ15A (TVS unidirectionnelle 600 W)'}),
    CP('C101', '470uF 35V', '+12V', 'PGND', 'Capacitor_SMD:CP_Elec_10x10.5'),
    C('C102', '10uF 35V X7R', '+12V', 'PGND', FP['C1210']),
    ('NT101', 'Device:NetTie_2', 'NetTie PGND-GND', 'NetTie:NetTie-2_SMD_Pad2.0mm', {'1': 'PGND', '2': 'GND'}, {}),
    ('U101', 'Regulator_Switching:AP63205WU', 'AP63205WU-7', 'Package_TO_SOT_SMD:TSOT-23-6',
        {'3': '+12V', '2': 'BUCK_EN', '4': 'GND', '5': 'BUCK_SW', '6': 'BUCK_BST', '1': '+5V'}, {'MPN': 'Diodes AP63205WU-7'}),
    R('R102', '100k', '+12V', 'BUCK_EN'),
    R('R103', '15k', 'BUCK_EN', 'GND'),
    C('C103', '10uF 35V X7R', '+12V', 'GND', FP['C1210']),
    C('C104', '100nF 50V', '+12V', 'GND'),
    C('C105', '100nF', 'BUCK_BST', 'BUCK_SW'),
    ('L101', 'Device:L', '4.7uH 3.5A', 'Inductor_SMD:L_Bourns_SRN6045TA', {'1': 'BUCK_SW', '2': '+5V'}, {'MPN': 'Bourns SRN6045TA-4R7M (Isat >= 3,5 A)'}),
    C('C106', '22uF 10V X5R', '+5V', 'GND', FP['C1206']),
    C('C107', '22uF 10V X5R', '+5V', 'GND', FP['C1206']),
    ('D103', 'Diode:SS34', 'SS34', 'Diode_SMD:D_SMA', {'2': '+5V', '1': 'VSYS'}, {}),
    ('D104', 'Diode:SS34', 'SS34', 'Diode_SMD:D_SMA', {'2': 'VBUS', '1': 'VSYS'}, {}),
    ('U102', 'Regulator_Linear:AP7361C-33E', 'AP7361C-33E', 'Package_TO_SOT_SMD:SOT-223-3_TabPin2',
        {'1': 'VSYS', '2': 'GND', '3': '+3V3'}, {'MPN': 'Diodes AP7361C-33E-13'}),
    C('C108', '10uF 16V', 'VSYS', 'GND', FP['C0805']),
    C('C109', '10uF 16V', '+3V3', 'GND', FP['C0805']),
    C('C110', '100nF', '+3V3', 'GND'),
    R('R104', '1k', '+3V3', 'PWRLED_A'),
    LED('D105', 'Vert', 'PWRLED_A', 'GND'),
    R('R105', '100k', '+12V', 'VIN_SENSE'),
    R('R106', '15k', 'VIN_SENSE', 'GND'),
    C('C111', '100nF', 'VIN_SENSE', 'GND'),
    TP('TP101', '+12V'), TP('TP102', '+5V'), TP('TP103', 'VSYS'), TP('TP104', '+3V3'),
    TP('TP105', 'GND'), TP('TP106', 'PGND'),
    FLAG('#FLG0101', 'GND'), FLAG('#FLG0102', 'PGND'), FLAG('#FLG0103', '+12V'),
    FLAG('#FLG0104', '+5V'), FLAG('#FLG0105', 'VSYS'),
])

# ---------------------------------------------------------------- 2. MICROCONTROLEUR
mcu_pins = {
    '3': 'ESP_EN', '27': 'ESP_IO0', '39': 'VIN_SENSE', '38': 'RTC_INT', '15': 'NC',
    '4': 'BTN_SET', '5': 'BTN_UP', '6': 'BTN_DOWN', '7': 'BUZZER',
    '12': 'I2C_SDA', '17': 'I2C_SCL',
    '18': 'SD_CS', '19': 'SD_MOSI', '20': 'SD_SCK', '21': 'SD_MISO', '22': 'SD_DET',
    '8': 'I2S_BCLK', '9': 'I2S_LRCLK', '10': 'I2S_DIN', '11': 'AMP_SD',
    '2': '+3V3', '1': 'GND',
    '37': 'UART_TX', '36': 'UART_RX', '13': 'USB_DN', '14': 'USB_DP', '23': 'LED_PWM',
    '28': 'NC', '29': 'NC', '30': 'NC',          # IO35-37 : PSRAM octale (N16R8)
    '31': 'STATUS_LED',
    '32': 'EXP_IO39', '33': 'EXP_IO40', '34': 'EXP_IO41', '35': 'EXP_IO42',
    '26': 'NC', '16': 'NC',                      # IO45 / IO46 : strapping
    '24': 'EXP_IO47', '25': 'EXP_IO48',
}
sheet('mcu.kicad_sch', 'Microcontroleur ESP32-S3-WROOM-1', [
    "MICROCONTROLEUR - choix et risques",
    "* U201 ESP32-S3-WROOM-1-N16R8 : 16 Mo flash, 8 Mo PSRAM octale => IO35/36/37 INDISPONIBLES (NC).",
    "* Antenne : le module deborde du bord de carte ou zone sans cuivre >= 15 mm sous/autour de l'antenne.",
    "* Strapping IO0/IO3/IO45/IO46 : IO0 = bouton BOOT seulement ; IO3/IO45/IO46 laisses NC.",
    "* Programmation : USB natif (IO19/IO20, USB-Serial-JTAG integre) + header UART0 de secours (J202).",
    "* EN : RC 10k/1uF (recommandation Espressif) + bouton RESET. USBLC6 : ESD sur D+/D-/VBUS.",
    "* J203 : extension / JTAG externe (IO39 MTCK, IO40 MTDO, IO41 MTDI, IO42 MTMS) + IO47/IO48.",
    "* Decouplage : 22uF + 100nF au plus pres de la broche 3V3 du module.",
], [
    ('U201', 'RF_Module:ESP32-S3-WROOM-1', 'ESP32-S3-WROOM-1-N16R8', 'RF_Module:ESP32-S3-WROOM-1', mcu_pins,
        {'MPN': 'Espressif ESP32-S3-WROOM-1-N16R8'}),
    C('C201', '22uF 10V', '+3V3', 'GND', FP['C0805']),
    C('C202', '100nF', '+3V3', 'GND'),
    R('R201', '10k', '+3V3', 'ESP_EN'),
    C('C203', '1uF', 'ESP_EN', 'GND'),
    ('SW201', 'Switch:SW_Push', 'RESET', 'Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92', {'1': 'ESP_EN', '2': 'GND'}, {}),
    R('R202', '10k', '+3V3', 'ESP_IO0'),
    ('SW202', 'Switch:SW_Push', 'BOOT', 'Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92', {'1': 'ESP_IO0', '2': 'GND'}, {}),
    ('J201', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C (prog/debug)', 'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
        {'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS', 'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND',
         'S1': 'USB_SHIELD', 'A5': 'USB_CC1', 'B5': 'USB_CC2', 'A7': 'USB_DN', 'B7': 'USB_DN',
         'A6': 'USB_DP', 'B6': 'USB_DP', 'A8': 'NC', 'B8': 'NC'}, {'MPN': 'HRO TYPE-C-31-M-12'}),
    R('R203', '5.1k', 'USB_CC1', 'GND'),
    R('R204', '5.1k', 'USB_CC2', 'GND'),
    R('R205', '1M', 'USB_SHIELD', 'GND'),
    C('C204', '4.7nF 100V', 'USB_SHIELD', 'GND'),
    ('U202', 'Power_Protection:USBLC6-2SC6', 'USBLC6-2SC6', 'Package_TO_SOT_SMD:SOT-23-6',
        {'1': 'USB_DP', '6': 'USB_DP', '3': 'USB_DN', '4': 'USB_DN', '5': 'VBUS', '2': 'GND'}, {}),
    ('J202', 'Connector_Generic:Conn_01x06', 'UART0 / prog', 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',
        {'1': 'GND', '2': 'UART_TX', '3': 'UART_RX', '4': 'ESP_EN', '5': 'ESP_IO0', '6': '+3V3'}, {}),
    ('J203', 'Connector_Generic:Conn_01x08', 'Extension / JTAG', 'Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical',
        {'1': '+3V3', '2': 'EXP_IO39', '3': 'EXP_IO40', '4': 'EXP_IO41', '5': 'EXP_IO42', '6': 'EXP_IO47', '7': 'EXP_IO48', '8': 'GND'}, {}),
    R('R206', '1k', 'STATUS_LED', 'STAT_A'),
    LED('D201', 'Bleu', 'STAT_A', 'GND'),
    TP('TP201', 'ESP_EN'), TP('TP202', 'ESP_IO0'),
    FLAG('#FLG0201', 'VBUS'),
])

# ---------------------------------------------------------------- 3. PANNEAU LED
sheet('led_driver.kicad_sch', 'Pilotage panneau LED 12 V (PWM)', [
    "PANNEAU LED - choix et risques",
    "* Commutation bas-cote : Q301 AOD4184A (40 V, ~9 mOhm @ Vgs 4,5 V) en TO-252 -> ~0,2 W a 4,2 A.",
    "* Le GPIO 3,3 V ne suffit pas a saturer un MOSFET de puissance : driver U301 UCC27511A alimente en 5 V",
    "  (Vgs = 5 V, toujours < 20 V meme si le 12 V monte a 24 V ; entrees TTL compatibles 3,3 V).",
    "* R301 10 Ohm (montee) / R302 4,7 Ohm (descente) : fronts maitrises -> CEM. R303 10k : grille a 0 si driver non alimente.",
    "* R304 100k : LED_PWM tire a 0 pendant le boot de l'ESP32 => panneau eteint au demarrage.",
    "* D301 SS54 : roue libre sur l'inductance du cable du panneau. C303/C304 : reservoir local pour les fronts PWM.",
    "* PWM recommandee : 20-25 kHz (inaudible), LEDC 11 bits ; pertes de commutation ~25 mW.",
    "* TOUT ce circuit est sur PGND : boucle 12V -> J301 -> Q301 -> PGND -> J101 sans traverser le plan GND logique.",
], [
    ('J301', 'Connector:Screw_Terminal_01x02', 'Panneau LED 12V <=50W', 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-3-2-5.08_1x02_P5.08mm_Horizontal',
        {'1': '+12V', '2': 'LED_K'}, {'MPN': 'Bornier 5,08 mm >= 15 A'}),
    ('Q301', 'Transistor_FET:Q_NMOS_GDS', 'AOD4184A', 'Package_TO_SOT_SMD:TO-252-2',
        {'1': 'GATE', '2': 'LED_K', '3': 'PGND'}, {'MPN': 'AOD4184A (N-MOS 40V 50A)'}),
    ('U301', 'Driver_FET:UCC27511ADBV', 'UCC27511ADBVR', 'Package_TO_SOT_SMD:SOT-23-6',
        {'6': 'LED_PWM', '5': 'PGND', '1': '+5V', '4': 'PGND', '2': 'GATE_H', '3': 'GATE_L'}, {'MPN': 'TI UCC27511ADBVR'}),
    R('R301', '10R', 'GATE_H', 'GATE'),
    R('R302', '4.7R', 'GATE_L', 'GATE'),
    R('R303', '10k', 'GATE', 'PGND'),
    R('R304', '100k', 'LED_PWM', 'GND'),
    C('C301', '1uF', '+5V', 'PGND'),
    C('C302', '100nF', '+5V', 'PGND'),
    ('D301', 'Device:D_Schottky', 'SS54', 'Diode_SMD:D_SMC', {'1': '+12V', '2': 'LED_K'}, {'MPN': 'SS54 (5 A 40 V)'}),
    CP('C303', '100uF 35V', '+12V', 'PGND', 'Capacitor_SMD:CP_Elec_8x10.5'),
    C('C304', '1uF 50V X7R', '+12V', 'PGND', FP['C1206']),
    TP('TP301', 'LED_PWM'), TP('TP302', 'GATE'), TP('TP303', 'LED_K'),
])

# ---------------------------------------------------------------- 4. AUDIO
sheet('audio.kicad_sch', 'Audio I2S MAX98357A + buzzer de secours', [
    "AUDIO - choix et risques",
    "* U401 MAX98357A : classe D I2S, 3,2 W / 4 Ohm sous 5 V, sans filtre LC (filterless).",
    "* FB401 + C401..C403 : 5 V audio isole du 5 V logique (ferrite), decouplage 10uF+100nF+100uF au plus pres.",
    "* GAIN_SLOT a GND = 12 dB. ~SD_MODE pilote par GPIO via 10k (pull-down interne 100k) :",
    "  GPIO=0 -> arret (aussi pendant le boot), GPIO=1 -> ~3 V => canal GAUCHE (le firmware envoie le son sur L).",
    "* FB402/FB403 + C404/C405 : filtre CEM pour fils de HP > 10 cm.",
    "* Masse : l'ampli reste sur GND (ses entrees I2S y sont referencees) mais dans une zone dediee ;",
    "  les courants de sortie bouclent localement HP <-> ampli <-> C403 et ne traversent pas la zone ESP32.",
    "* Buzzer passif BZ401 (secours si SD absente/illisible), Q401 AO3400A + D401 roue libre, PWM ~2,7 kHz.",
], [
    ('FB401', 'Device:FerriteBead_Small', '600R@100MHz 2A', FP['FB0805'], {'1': '+5V', '2': '+5V_AUD'}, {}),
    ('U401', 'Audio:MAX98357A', 'MAX98357AETE+T', 'Package_DFN_QFN:TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm',
        {'1': 'I2S_DIN', '16': 'I2S_BCLK', '14': 'I2S_LRCLK', '4': 'AMP_SDMODE', '2': 'GND',
         '3': 'GND', '11': 'GND', '15': 'GND', '7': '+5V_AUD', '8': '+5V_AUD', '17': 'GND',
         '9': 'SPK_P_RAW', '10': 'SPK_N_RAW'}, {'MPN': 'Analog Devices MAX98357AETE+T'}),
    R('R401', '10k', 'AMP_SD', 'AMP_SDMODE'),
    C('C401', '10uF 10V', '+5V_AUD', 'GND', FP['C0805']),
    C('C402', '100nF', '+5V_AUD', 'GND'),
    CP('C403', '100uF 16V', '+5V_AUD', 'GND', 'Capacitor_SMD:CP_Elec_6.3x5.4'),
    ('FB402', 'Device:FerriteBead_Small', '220R@100MHz 2A', FP['FB0805'], {'1': 'SPK_P_RAW', '2': 'SPK_P'}, {}),
    ('FB403', 'Device:FerriteBead_Small', '220R@100MHz 2A', FP['FB0805'], {'1': 'SPK_N_RAW', '2': 'SPK_N'}, {}),
    C('C404', '1nF', 'SPK_P', 'GND'),
    C('C405', '1nF', 'SPK_N', 'GND'),
    ('J401', 'Connector_Generic:Conn_01x02', 'HP 4-8 Ohm 3W', 'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',
        {'1': 'SPK_P', '2': 'SPK_N'}, {}),
    ('BZ401', 'Device:Buzzer', 'Buzzer passif 5V', 'Buzzer_Beeper:Buzzer_12x9.5RM7.6', {'1': '+5V', '2': 'BUZ_D'}, {}),
    ('Q401', 'Transistor_FET:AO3400A', 'AO3400A', 'Package_TO_SOT_SMD:SOT-23', {'1': 'BUZ_G', '3': 'BUZ_D', '2': 'GND'}, {}),
    R('R402', '100R', 'BUZZER', 'BUZ_G'),
    R('R403', '100k', 'BUZ_G', 'GND'),
    ('D401', 'Device:D', '1N4148W', FP['SOD123'], {'1': '+5V', '2': 'BUZ_D'}, {}),
    TP('TP401', 'I2S_BCLK'), TP('TP402', 'I2S_LRCLK'), TP('TP403', 'I2S_DIN'),
    FLAG('#FLG0401', '+5V_AUD'),
])

# ---------------------------------------------------------------- 5. CARTE SD
sheet('sd_card.kicad_sch', 'Lecteur microSD (SPI)', [
    "MICRO SD - choix et risques",
    "* La carte SD fonctionne en 3,3 V comme l'ESP32 : AUCUN translateur de niveau necessaire",
    "  (ne pas utiliser les modules SD 5 V avec regulateur + 74LVC125 : inutiles ici et sources de bugs MISO).",
    "* Bus SPI sur les broches IO_MUX FSPI (IO10..13) : jusqu'a 40-80 MHz sans passer par la matrice GPIO.",
    "* Pull-up 10k sur CMD, DAT0..DAT3 (spec SD : aucune ligne flottante, DAT1/DAT2 inutilisees en SPI).",
    "* R501/R502 22 Ohm : amortissement des fronts CLK/MOSI. U501 TPD4E05U06 : ESD au plus pres du connecteur.",
    "* Detection de carte (DET_A/DET_B) sur SD_DET avec pull-up 10k.",
], [
    ('J501', 'Connector:Micro_SD_Card_Det2', 'microSD Hirose DM3AT', 'Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5',
        {'1': 'SD_DAT2', '2': 'SD_CS', '3': 'SD_CMD_C', '4': '+3V3', '5': 'SD_CLK_C', '6': 'GND',
         '7': 'SD_MISO', '8': 'SD_DAT1', '10': 'SD_DET', '9': 'GND', '11': 'GND'}, {'MPN': 'Hirose DM3AT-SF-PEJM5'}),
    R('R501', '22R', 'SD_SCK', 'SD_CLK_C'),
    R('R502', '22R', 'SD_MOSI', 'SD_CMD_C'),
    R('R503', '10k', '+3V3', 'SD_CMD_C'),
    R('R504', '10k', '+3V3', 'SD_MISO'),
    R('R505', '10k', '+3V3', 'SD_DAT1'),
    R('R506', '10k', '+3V3', 'SD_DAT2'),
    R('R507', '10k', '+3V3', 'SD_CS'),
    R('R508', '10k', '+3V3', 'SD_DET'),
    ('U501', 'Power_Protection:TPD4E05U06DQA', 'TPD4E05U06DQAR', 'Package_SON:USON-10_2.5x1.0mm_P0.5mm',
        {'1': 'SD_CLK_C', '2': 'SD_CMD_C', '4': 'SD_MISO', '5': 'SD_CS', '3': 'GND', '8': 'GND',
         '6': 'NC', '7': 'NC', '9': 'NC', '10': 'NC'}, {}),
    C('C501', '10uF 10V', '+3V3', 'GND', FP['C0805']),
    C('C502', '100nF', '+3V3', 'GND'),
    TP('TP501', 'SD_SCK'), TP('TP502', 'SD_MISO'),
])

# ---------------------------------------------------------------- 6. RTC
sheet('rtc.kicad_sch', 'Horloge temps reel DS3231 + pile CR2032', [
    "RTC - choix et risques",
    "* U601 DS3231SN (TCXO +-2 ppm, ~1 min/an) prefere au DS3231M (MEMS +-5 ppm) ; brochage SO-16 identique.",
    "* Broches 5-12 (N.C.) reliees a GND comme l'exige la datasheet (deja faites dans le symbole).",
    "* VBAT direct depuis la CR2032 (commutation interne). Autonomie pile > 5 ans (~3 uA en sauvegarde).",
    "* ~INT/SQW (drain ouvert) -> RTC_INT (GPIO2, domaine RTC) : alarme materielle + reveil de deep-sleep.",
    "* Pull-up I2C 4,7k UNIQUES sur la carte (adresses : DS3231 0x68, OLED 0x3C). Retirer celles du module OLED si besoin.",
], [
    ('U601', 'Timer_RTC:DS3231M', 'DS3231SN#', 'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
        {'16': 'I2C_SCL', '15': 'I2C_SDA', '4': 'NC', '2': '+3V3', '14': 'VBAT', '13': 'GND',
         '5': 'GND', '6': 'GND', '7': 'GND', '8': 'GND', '9': 'GND', '10': 'GND', '11': 'GND', '12': 'GND',
         '1': 'NC', '3': 'RTC_INT'}, {'MPN': 'Analog Devices DS3231SN#'}),
    ('BT601', 'Device:Battery_Cell', 'CR2032', 'Battery:BatteryHolder_Keystone_3034_1x20mm', {'1': 'VBAT', '2': 'GND'},
        {'MPN': 'Keystone 3034'}),
    C('C601', '100nF', '+3V3', 'GND'),
    R('R601', '10k', '+3V3', 'RTC_INT'),
    R('R602', '4.7k', '+3V3', 'I2C_SDA'),
    R('R603', '4.7k', '+3V3', 'I2C_SCL'),
    TP('TP601', 'I2C_SDA'), TP('TP602', 'I2C_SCL'), TP('TP603', 'RTC_INT'), TP('TP604', 'VBAT'),
    FLAG('#FLG0601', 'VBAT'),
])

# ---------------------------------------------------------------- 7. ECRAN
sheet('display.kicad_sch', 'Ecran OLED SSD1306 128x64 I2C', [
    "ECRAN - choix et risques",
    "* Module OLED 0,96\" SSD1306 128x64 I2C, adresse 0x3C (SA0=0), alimente en 3,3 V (~20 mA, 30 mA tout blanc).",
    "* Brochage du connecteur J701 : GND - VCC - SCL - SDA. ATTENTION : certains modules sont en VCC - GND :",
    "  verifier le module achete avant de souder (inversion = module detruit).",
    "* Les modules embarquent souvent des pull-up 4,7k/10k : en parallele avec R602/R603 => ~2,3 k, acceptable.",
    "* Alternative plus lisible la nuit : SH1106 1,3\" (meme brochage, adresse 0x3C, driver different).",
    "* Pour un reveil : prevoir dans le firmware une luminosite (contraste) minimale la nuit et un mode veille ecran.",
], [
    ('J701', 'Connector_Generic:Conn_01x04', 'OLED SSD1306 128x64 0x3C', 'Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical',
        {'1': 'GND', '2': '+3V3', '3': 'I2C_SCL', '4': 'I2C_SDA'}, {}),
    C('C701', '10uF 10V', '+3V3', 'GND', FP['C0805']),
    C('C702', '100nF', '+3V3', 'GND'),
])

# ---------------------------------------------------------------- 8. BOUTONS
btn_parts = []
for i, (name, lab) in enumerate([('SET', 'MODE/OK'), ('UP', '+'), ('DOWN', '-')]):
    n = 'BTN_%s_N' % name
    btn_parts += [
        ('SW80%d' % (i + 1), 'Switch:SW_Push', lab, 'Button_Switch_THT:SW_PUSH_6mm_H8mm', {'1': n, '2': 'GND'}, {}),
        R('R80%d' % (2 * i + 1), '10k', '+3V3', n),
        C('C80%d' % (i + 1), '100nF', n, 'GND'),
        R('R80%d' % (2 * i + 2), '1k', n, 'BTN_' + name),
    ]
sheet('buttons.kicad_sch', 'Boutons utilisateur (antirebond materiel)', [
    "BOUTONS - choix et risques",
    "* Actif bas : pull-up 10k + 100 nF => tau = 1 ms (antirebond materiel) ; 1k serie = protection ESD/courant du GPIO.",
    "* Le firmware ajoute un antirebond logiciel 20-30 ms et la detection appui long (reglage rapide).",
    "* GPIO4/5/6 sont dans le domaine RTC : reveil de deep-sleep possible par EXT1 (n'importe quel bouton).",
    "* Variante facade : remplacer SW801..803 par un connecteur JST-PH 4 broches vers des boutons de boitier.",
], btn_parts)
