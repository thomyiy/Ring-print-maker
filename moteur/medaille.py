"""Médaille à empreinte : les médailles du configurateur de
rainbowantworkshop.fr (`catalog-medaille.json`), construites ici depuis leur
contour, et l'empreinte en relief sur la face.

Le configurateur n'a pas de maillage de médaille : il les fabrique depuis le
contour. On fait de même, réglé sur ce que le catalogue publie :
- épaisseur `thickness` (1,4 mm) ;
- trou de bélière de Ø 1,5 mm au point `bail` — l'« aire utile » du
  catalogue est exactement l'aire du contour moins ce trou ;
- bord adouci (congé de `RAYON_BORD`).
Le catalogue compte aussi l'anneau de bélière (≈ 6,5 mm³, constant d'une taille
à l'autre) ; il n'est pas modélisé ici, l'atelier le pose au montage.

Repère : face gravée à y = 0, épaisseur vers −y ; contour centré (u, v) posé
en x = −u, z = −v, comme le plateau des chevalières.

⚠️ `shared/medaille.ts` construit la même médaille dans le navigateur ;
`npm test` compare les volumes et les reliefs.
"""
from __future__ import annotations

import numpy as np

from . import chevaliere as C

RAYON_BORD = 0.25        # mm, congé des deux faces
TROU_BELIERE = 1.5       # mm de diamètre
MARGE_FACE = 0.3         # mm laissés lisses entre le relief et le bord adouci
MARGE_TROU = 0.4         # mm laissés lisses autour du trou
TRANCHES = 8             # marches de l'arrondi dans le fichier de fabrication


def catalogue() -> dict:
    import json
    return json.loads(C._telecharger("catalog-medaille.json"))["products"][0]


def variante(cat, forme, taille_mm):
    f = next((s for s in cat["shapes"] if s["id"] == forme), None)
    if f is None:
        raise ValueError(f"Forme inconnue : {forme}")
    t = next((s for s in f["sizes"] if int(s["mm"]) == int(taille_mm)), None)
    if t is None:
        raise ValueError(f"Taille {taille_mm} mm indisponible pour cette forme.")
    return f, t


def contour_centre(t):
    pts = np.array(t["points"], float).reshape(-1, 2)
    return pts - np.array([t["width"] / 2, t["height"] / 2])


def trou_centre(t, forme=None):
    """(u, v, rayon) du trou : la bélière (Ø 1,5 mm) près du bord, ou, pour une
    forme à bélière « center » (le Cercle), l'évidement du milieu où passe la
    chaîne — Ø un quart de la taille, ce que l'aire utile du catalogue donne
    exactement (3, 4 et 5 mm pour 12, 16 et 20 mm)."""
    if forme is not None and forme.get("bail") == "center":
        return (0.0, 0.0, t["mm"] / 8)
    if not t.get("bail"):
        return None
    return (t["bail"][0] - t["width"] / 2, t["bail"][1] - t["height"] / 2, TROU_BELIERE / 2)


def zone_relief(t):
    return C.retrecir(contour_centre(t), RAYON_BORD + MARGE_FACE)


def corps(t, epaisseur, forme=None):
    """Le corps de la médaille en Manifold : tranches pour l'arrondi des deux
    faces (marches de RAYON_BORD/TRANCHES, sous le pas d'une imprimante
    résine), puis le trou de bélière."""
    import manifold3d as mf
    pq = -contour_centre(t)                  # (p, q) = (x, z) = (−u, −v)
    cs = mf.CrossSection([pq.tolist()], mf.FillRule.EvenOdd)
    r = min(RAYON_BORD, epaisseur / 2 - 0.05)
    morceaux = [mf.Manifold.extrude(cs, epaisseur - 2 * r).translate((0, 0, r))]
    for i in range(TRANCHES):
        s0, s1 = r * i / TRANCHES, r * (i + 1) / TRANCHES
        sm = (s0 + s1) / 2
        retrait = r - np.sqrt(max(r * r - (r - sm) ** 2, 0.0))
        tr = cs.offset(-retrait, mf.JoinType.Round)
        morceaux.append(mf.Manifold.extrude(tr, s1 - s0).translate((0, 0, s0)))
        morceaux.append(mf.Manifold.extrude(tr, s1 - s0).translate((0, 0, epaisseur - s1)))
    m = mf.Manifold.batch_boolean(morceaux, mf.OpType.Add)
    trou = trou_centre(t, forme)
    if trou:
        cyl = mf.Manifold.cylinder(epaisseur + 2, trou[2], trou[2], 64).translate((-trou[0], -trou[1], -1))
        m = m - cyl
    # (p, q, c) → (x, y, z) = (p, −c, q) : la face c = 0 devient le dessus, y = 0.
    return m.transform([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0]])


def construire(p, emp):
    import manifold3d as mf
    cat = catalogue()
    forme, t = variante(cat, p["forme"], p["taille"])
    ep = float(cat.get("thickness", 1.4))
    m = corps(t, ep, forme)
    mm_par_px = p["periode_mm"] / emp.periode_px
    lire = C.lecteur_relief(emp, p["placement_px"], mm_par_px)
    zone = zone_relief(t)
    trou = trou_centre(t, forme)
    trou_marge = (trou[0], trou[1], trou[2] + MARGE_TROU) if trou else None
    h = float(p["hauteur_relief"])
    Vr, Fr, vol_relief = C.relief_solide(zone, zone, lambda u, v: h * lire(u, v), 0.0,
                                         p.get("pas_relief", C.PAS_FABRICATION), trou_marge)
    total = m + mf.Manifold(mf.Mesh(Vr.astype(np.float32), Fr.astype(np.uint32)))
    mesh = total.to_mesh()
    return {
        "V": np.asarray(mesh.vert_properties)[:, :3].astype(float),
        "F": np.asarray(mesh.tri_verts).astype(np.int64),
        "statut": str(total.status()),
        "volume_base_mm3": float(m.volume()),
        "volume_mm3": float(total.volume()),
        "volume_relief_mm3": vol_relief,
        "forme": forme["name"],
        "volume_catalogue_mm3": t["volumeMm3"]["nu"],
    }
