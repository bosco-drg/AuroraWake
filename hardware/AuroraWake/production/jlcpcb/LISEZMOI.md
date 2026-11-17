# AuroraWake V2 — dossier de fabrication JLCPCB

Généré le 17/11/2026 depuis `AuroraWake.kicad_pcb` (KiCad 9.0.8).

DRC : 0 erreur, 0 connexion manquante, 0 écart avec le schéma. Il reste un avertissement voulu : l'empreinte ESP32-S3-WROOM-1 diffère de la bibliothèque, parce que ses vias thermiques sont passées de 0,2 à 0,3 mm pour respecter le perçage minimum JLCPCB en 2 couches.

## Fichiers

| Fichier | Où l'utiliser chez JLCPCB |
|---|---|
| `AuroraWake_gerbers_JLCPCB.zip` | « Add gerber file » : 9 couches Gerber et 2 fichiers de perçage (PTH et NPTH) |
| `AuroraWake_BOM_JLCPCB.csv` | Assembly → « Add BOM File » |
| `AuroraWake_CPL_JLCPCB.csv` | Assembly → « Add CPL File » |
| `a_souder_a_la_main.csv` | Non envoyé : les 11 pièces à souder toi-même (traversants + BT601 au dos) |
| `gerbers/` | Le contenu du zip, non compressé |
| `docs/` | Plans d'assemblage (dessus et dessous), carte des perçages, schéma PDF, rapport DRC |

## Paramètres de commande du PCB

| Option | Valeur |
|---|---|
| Base Material | FR-4 |
| Layers | 2 |
| Dimensions | 100 × 80 mm (détectées depuis Edge.Cuts) |
| PCB Thickness | 1,6 mm |
| **Outer Copper Weight** | **2 oz**, indispensable pour les ~5 A du panneau LED. Les pistes et espacements de 0,2 mm respectent le minimum JLCPCB de 8 mil en 2 oz. |
| Surface Finish | ENIG conseillé : plus plat pour le QFN 3×3 de l'ampli et l'USON de la protection ESD. HASL sans plomb fonctionne aussi. |
| Min via hole / diameter | 0,3 mm / 0,6 mm (standard) |
| Solder mask / silkscreen | Au choix (vert et blanc par défaut) |
| Remove Order Number | « Specify a location » ou option payante. Sinon JLCPCB imprime un numéro sur la sérigraphie. |

## Assemblage (PCBA)

- **PCBA Type** : Standard, **Assemble top side** uniquement. La BOM et le CPL ne contiennent que les 96 composants CMS de la face avant.
- **Références LCSC** : renseignées pour les 96 composants. Elles viennent soit de lcsc.com, soit des propositions de l'outil JLCPCB après vérification. Corrections faites par rapport à la proposition automatique :
  - U102 → **C500795** (AP7361C-33**E**-13). La version -33**ER** proposée a un brochage inversé et aurait détruit la carte.
  - D105 → C12624 (LED **verte**, au lieu de la rouge proposée).
  - D201 → C2288 (LED **bleue**).
  - Q301 → C99124 (AOD4184A d'Alpha & Omega, en stock).
  - SW201/SW202 → C221880 (PTS645SM43SMTR92, empreinte conforme).
  - Composants ajoutés : F101 C99548, L101 C2044594, FB401 C41384117, FB402/FB403 C85840, J201 C165948, J501 C114218.
- **À vérifier dans l'outil** : le stock au moment de la commande, ainsi que les dimensions des condensateurs électrolytiques C303 (C2992597, 8 × 10,5 mm attendu) et C403 (C5155334, 6,3 × 5,4 mm attendu).
- **Soudure manuelle** (`a_souder_a_la_main.csv`) : J101, J202, J203, J301, J401, J701, SW801–SW803, BZ401 et BT601 (au dos).
- **Rotations** : les angles du CPL sont ceux de KiCad. JLCPCB utilise ses propres conventions pour certains boîtiers (SOT-23, SOT-223, TO-252, QFN, SOIC). **Vérifie l'aperçu 3D de JLCPCB** avant de valider, notamment le point 1 de U101, U102, U202, U301, U401, U501, U601, Q101, Q301, Q401 et des LED D105/D201, et corrige les rotations dans l'interface si besoin.
- **Hors assemblage** : la pile CR2032, le module OLED (sur J701), le panneau LED, le haut-parleur et le bloc d'alimentation 12 V.

## Régénérer ce dossier

Depuis `hardware/AuroraWake/`, après toute modification du PCB :

```bash
python3 tools/jlc_export.py
```

Le script lance d'abord le DRC et s'arrête s'il reste une erreur ou une connexion manquante. Il produit ensuite les Gerber, les perçages, le zip, la BOM et le CPL JLCPCB, puis les PDF. Pour remplir les références LCSC une fois choisies, ajoute un champ `LCSC` aux symboles du schéma : le script le reporte dans la colonne `LCSC Part #`.
