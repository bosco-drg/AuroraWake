# AuroraWake — BOM V1

## 1. Contrôle / Microcontrôleur

| Référence | Composant | Valeur / Modèle | Qté | Fonction |
|---|---|---|---:|---|
| U1 | Module ESP32 | ESP32-WROOM-32E | 1 | Microcontrôleur, Wi-Fi, Bluetooth |
| U2 | RTC | DS3231M | 1 | Gestion précise de l'heure |
| OLED1 | Écran OLED | 0,91" — 128×32 — SSD1306 — I²C | 1 | Affichage de l'heure et de l'état de l'alarme |
| SW1 | Bouton poussoir | Tactile | 1 | Navigation / réglage |
| SW2 | Bouton poussoir | Tactile | 1 | Navigation / réglage |
| SW3 | Bouton poussoir | Tactile | 1 | Navigation / réglage |
| SW4 | Bouton poussoir | Tactile | 1 | Navigation / réglage |
| R1-R4 | Résistance | 10 kΩ | 4 | Pull-up / Pull-down des boutons |

---

## 2. Éclairage LED 12 V / 100 W

| Référence | Composant | Valeur / Modèle | Qté | Fonction |
|---|---|---|---:|---|
| LED1 | Panneau LED COB | 12V 15W | 1 | Éclairage principal |

---

## 4. Conversion 12 V → 3,3 V

| Référence | Composant | Valeur / Modèle | Qté | Fonction |
|---|---|---|---:|---|
| U3 | Convertisseur Buck | 12 V → 5 V, ≥2 A | 1 | Première conversion de tension |
| U4 | Régulateur LDO | 5 V → 3,3 V, ≥500 mA | 1 | Alimentation logique |

---

## 5. Audio

| Référence | Composant | Valeur / Modèle | Qté | Fonction |
|---|---|---|---:|---|
| U5 | Amplificateur audio | MAX98357A | 1 | Amplification audio I²S |
| SPK1 | Haut-parleur | 4 Ω / 3 W | 1 | Sonnerie / réveil |

---