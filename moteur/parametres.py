"""Les paramètres, leurs valeurs par défaut et leurs bornes.

Une seule table : le site la lit (via `python -m moteur schema`) pour construire
son formulaire, donc une borne changée ici se voit là-bas sans autre geste.
"""
from __future__ import annotations

import math

# nom: (défaut, min, max, pas, unité, libellé, groupe)
TABLE = {
    # — Forme ——————————————————————————————————————————
    "taille": (54.0, 40.0, 75.0, 0.5, "", "Taille de doigt (tour en mm)", "forme"),
    "diametre_interieur": (17.2, 12.0, 24.0, 0.01, "mm", "Diamètre intérieur", "forme"),
    "cote": (1.8, 1.2, 3.0, 0.05, "mm", "Côté du fil carré", "forme"),
    "rayon_arete": (0.15, 0.05, 0.4, 0.01, "mm", "Rayon des arêtes", "forme"),
    "torsion_deg": (180.0, 90.0, 360.0, 90.0, "°", "Torsion", "forme"),
    "arc_torsion_deg": (170.0, 60.0, 300.0, 1.0, "°", "Arc de la torsion", "forme"),
    "adouci": (0.08, 0.0, 0.3, 0.01, "", "Adouci aux raccords (part de l'arc)", "forme"),
    "sens": (1, -1, 1, 2, "", "Sens de la torsion", "forme"),
    # — Empreinte ———————————————————————————————————————
    "hauteur_relief": (0.18, 0.08, 0.4, 0.01, "mm", "Hauteur des crêtes", "empreinte"),
    "cretes_largeur": (7.0, 2.5, 10.0, 0.5, "", "Crêtes dans la largeur", "empreinte"),
    "angle_bande_deg": (None, 0.0, 180.0, 1.0, "°", "Angle de la bande (vide = auto)", "empreinte"),
    "decalage_bande": (0.0, -6.0, 6.0, 0.05, "mm", "Décalage de la bande", "empreinte"),
    "cretes_noires": (True, None, None, None, "", "Crêtes noires sur l'image", "empreinte"),
    "miroir": (False, None, None, None, "", "Retourner l'empreinte (miroir)", "empreinte"),
    "agrandissement": (6.0, 2.0, 8.0, 1.0, "×", "Agrandissement", "empreinte"),
    "flou": (0.12, 0.0, 0.4, 0.01, "période", "Flou", "empreinte"),
    "douceur": (0.08, 0.02, 0.3, 0.01, "", "Douceur du seuil (pente des flancs)", "empreinte"),
    "aire_min_mm2": (0.01, 0.0, 0.05, 0.001, "mm²", "Points isolés retirés sous", "empreinte"),
    # — Maillage ————————————————————————————————————————
    "n_sections": (1440, 180, 2880, 10, "", "Sections sur le tour", "maillage"),
    "n_face": (50, 10, 80, 1, "", "Points sur une face", "maillage"),
    "n_coin": (8, 3, 16, 1, "", "Points par arête rayonnée", "maillage"),
    # — Métal ——————————————————————————————————————————
    "densite_or": (15.5, None, None, None, "g/cm³", "Or 750", "metal"),
    "densite_argent": (10.36, None, None, None, "g/cm³", "Argent 925", "metal"),
}


def defauts() -> dict:
    return {k: v[0] for k, v in TABLE.items()}


def diametre_depuis_taille(taille: float) -> float:
    """Taille française = tour de doigt en mm. 54 → 17,19 mm, arrondi à 17,2."""
    return round(taille / math.pi, 1)


def normaliser(brut: dict | None) -> dict:
    """Complète, convertit et borne. Une valeur hors bornes est ramenée, pas
    refusée : le formulaire borne déjà, et un appel en ligne de commande ne doit
    pas échouer pour un centième."""
    p = defauts()
    brut = dict(brut or {})
    # La taille pilote le diamètre, sauf si le diamètre est donné seul.
    if "taille" in brut and "diametre_interieur" not in brut:
        brut["diametre_interieur"] = diametre_depuis_taille(float(brut["taille"]))
    for k, v in brut.items():
        if k not in TABLE or v is None or v == "":
            if k in TABLE:
                p[k] = None if TABLE[k][0] is None else p[k]
            continue
        d, lo, hi = TABLE[k][0], TABLE[k][1], TABLE[k][2]
        if isinstance(TABLE[k][0], bool) or k in ("cretes_noires", "miroir"):
            p[k] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "oui", "on")
            continue
        x = float(v)
        if lo is not None:
            x = min(max(x, lo), hi)
        p[k] = int(round(x)) if isinstance(d, int) and not isinstance(d, bool) else x
    # La bande posée à la main dans l'éditeur : ses deux bouts, en pixels de
    # l'image d'édition (origine en haut à gauche, y vers le bas).
    bp = brut.get("bande_px")
    p["bande_px"] = None
    if isinstance(bp, (list, tuple)) and len(bp) == 4:
        try:
            p["bande_px"] = [float(x) for x in bp]
        except (TypeError, ValueError):
            pass
    p["bord_a_bord"] = str(brut.get("bord_a_bord", True)).lower() not in ("false", "0", "non", "off")
    p["sens"] = 1 if p["sens"] >= 0 else -1
    # Le profil doit rester symétrique au demi-tour : nombre de sections pair.
    p["n_sections"] += p["n_sections"] % 2
    p["rayon_arete"] = min(p["rayon_arete"], p["cote"] / 2 - 0.05)
    p["largeur_utile"] = p["cote"] - 2 * p["rayon_arete"]
    # L'échelle peut aussi se donner par la période des crêtes sur la bague
    # (mm d'une crête à la suivante). C'est ce que règle la page client : la
    # taille de l'empreinte ne bouge plus quand on change la largeur du fil.
    if brut.get("periode_mm"):
        per = min(max(float(brut["periode_mm"]), 0.15), 0.8)
        p["cretes_largeur"] = p["largeur_utile"] / per
    return p
