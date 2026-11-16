"""Chevalière à empreinte : une chevalière existante de la bibliothèque de
rainbowantworkshop.fr, et l'empreinte en relief sur son plateau.

La bibliothèque : `catalog-chevaliere.json` (formes, contours du plateau et du
godet, volumes) et un maillage par variante,
`rings/<forme>/<plateau>/<creuse|pleine>/<doigt>/<lisse|creux>.jrm`.
`lisse` a le plateau plein, `creux` le plateau creusé d'un godet.

Repère des maillages : le dessus du plateau est à y = 0, l'anneau pend vers
−y, l'axe du doigt est Z. Le plateau se décrit en millimètres « SVG » (x vers
la droite, y vers le bas, origine en haut à gauche) ; centré en (u, v), il se
pose en x = −u, z = −v. C'est ce qui garde l'empreinte à l'endroit vue de
dessus (vérifié sur l'écu, dont la pointe est en −z).

⚠️ `shared/chevaliere.ts` est la traduction de ce fichier pour le navigateur.
Toute retouche de l'un se refait dans l'autre : `npm test` les compare.
"""
from __future__ import annotations

import json
import os
import struct
import urllib.request
from pathlib import Path

import numpy as np

BIBLIO = os.environ.get("NUXT_BIBLIO_URL", "https://rainbowantworkshop.fr/biblio/assets").rstrip("/")
CACHE = Path(os.environ.get("NUXT_DOSSIER_BIBLIO") or Path.cwd() / ".data" / "biblio")
PAS_FABRICATION = 0.03       # mm entre deux points du relief, fichier de l'atelier
EPAISSEUR_ANCRAGE = 0.2      # mm de relief noyés dans le métal, pour une union franche
MARGE_PLEIN = 0.4            # mm laissés lisses au bord d'un plateau plein


# — Bibliothèque ——————————————————————————————————————————————————

def _telecharger(chemin: str) -> bytes:
    """Les fichiers de la bibliothèque sont immuables : un chemin désigne
    toujours la même géométrie. On les garde sur disque, sans expiration."""
    local = CACHE / chemin
    if local.exists():
        return local.read_bytes()
    req = urllib.request.Request(f"{BIBLIO}/{chemin}", headers={"User-Agent": "alliance-empreinte"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_suffix(local.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(local)
    return data


def catalogue() -> dict:
    return json.loads(_telecharger("catalog-chevaliere.json"))["products"][0]


def lire_jrm(data: bytes):
    """Format JRM1 : en-tête (nb sommets, nb indices, drapeaux), boîte (min,
    taille), positions quantifiées u16, normales i8×4, indices u16 ou u32.
    Les sommets sont dédoublés aux arêtes vives (normales) : on les soude."""
    if data[:4] != b"JRM1":
        raise ValueError("Maillage illisible.")
    nv, ni, _ = struct.unpack_from("<3I", data, 4)
    mn = np.array(struct.unpack_from("<3f", data, 16))
    sz = np.array(struct.unpack_from("<3f", data, 28))
    q = np.frombuffer(data, "<u2", nv * 3, 40).reshape(-1, 3)
    o = 40 + nv * 6 + nv * 4
    F = np.frombuffer(data, "<u2" if nv < 65536 else "<u4", ni, o).reshape(-1, 3).astype(np.int64)
    V = mn + q / 65535.0 * sz
    cle = np.round(V / 1e-5).astype(np.int64)
    _, inv = np.unique(cle, axis=0, return_inverse=True)
    inv = inv.ravel()
    Vw = np.zeros((inv.max() + 1, 3))
    Vw[inv] = V
    Fw = inv[F]
    Fw = Fw[(Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 0] != Fw[:, 2])]
    return Vw, Fw


def chemin_maillage(forme, plateau, remplissage, doigt_mesh, surface):
    fichier = "creux" if surface == "godet" else "lisse"
    return f"rings/{forme}/{int(plateau)}/{remplissage}/{doigt_mesh}/{fichier}.jrm"


def variante(cat, forme, plateau):
    f = next((s for s in cat["shapes"] if s["id"] == forme), None)
    if f is None:
        raise ValueError(f"Forme inconnue : {forme}")
    t = next((s for s in f["sizes"] if int(s["mm"]) == int(plateau)), None)
    if t is None:
        raise ValueError(f"Plateau de {plateau} mm indisponible pour cette forme.")
    return f, t


def contour_centre(taille, quoi="plateau"):
    """Contour (u, v) centré sur le plateau, en mm, v vers le bas."""
    src = taille if quoi == "plateau" else taille["cup"]
    pts = np.array(src["points"], float).reshape(-1, 2)
    return pts - np.array([taille["width"] / 2, taille["height"] / 2])


# — Géométrie du relief ———————————————————————————————————————————

def dans_polygone(P, poly):
    """Pair-impair, vectorisé. P (n, 2), poly (m, 2)."""
    x, y = P[:, 0], P[:, 1]
    dedans = np.zeros(len(P), bool)
    xj, yj = poly[-1]
    for xi, yi in poly:
        croise = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-300) + xi)
        dedans ^= croise
        xj, yj = xi, yi
    return dedans


def retrecir(poly, d):
    """Décale un contour vers l'intérieur de d (approché par les sommets :
    suffisant pour des contours lisses et des marges de quelques dixièmes)."""
    c = poly.mean(0)
    n = len(poly)
    out = np.empty_like(poly)
    for i in range(n):
        a, b = poly[i - 1], poly[(i + 1) % n]
        t = b - a
        nrm = np.array([t[1], -t[0]]) / (np.hypot(*t) + 1e-12)
        if np.dot(nrm, c - poly[i]) < 0:
            nrm = -nrm
        out[i] = poly[i] + d * nrm
    return out


def _sans_diagonales(cel):
    """Deux cellules qui ne se touchent que par un coin feraient un sommet non
    manifold : on comble l'un des deux voisins."""
    while True:
        a, b = cel[:-1, :-1], cel[1:, 1:]
        c, d = cel[1:, :-1], cel[:-1, 1:]
        diag1 = a & b & ~c & ~d
        diag2 = c & d & ~a & ~b
        if not (diag1.any() or diag2.any()):
            return cel
        cel[1:, :-1] |= diag1
        cel[:-1, :-1] |= diag2


def relief_solide(zone, emprise, hauteur_de, base, pas):
    """Le relief en solide fermé, sur une grille de pas `pas`.

    zone     : contour (u, v) où les crêtes peuvent monter ;
    emprise  : contour (u, v) des cellules gardées (≥ zone : au-delà, hauteur 0,
               noyé dans le métal) ;
    hauteur_de(u, v) → hauteur en mm au-dessus de `base` (y du fond).
    Rendu : V (n, 3) dans le repère du maillage, F (m, 3), volume au-dessus de
    `base`."""
    umin, vmin = emprise.min(0) - pas
    umax, vmax = emprise.max(0) + pas
    nu = int(np.ceil((umax - umin) / pas)) + 1
    nv = int(np.ceil((vmax - vmin) / pas)) + 1
    U, Vv = np.meshgrid(umin + pas * np.arange(nu), vmin + pas * np.arange(nv), indexing="ij")
    P = np.stack([U.ravel(), Vv.ravel()], 1)
    dans_emprise = dans_polygone(P, emprise).reshape(nu, nv)
    dans_zone = dans_polygone(P, zone).reshape(nu, nv)
    cel = dans_emprise[:-1, :-1] & dans_emprise[1:, :-1] & dans_emprise[:-1, 1:] & dans_emprise[1:, 1:]
    cel = _sans_diagonales(cel)

    H = np.zeros((nu, nv))
    H[dans_zone] = hauteur_de(U[dans_zone], Vv[dans_zone])

    # Nœuds utilisés : coins des cellules gardées.
    utilise = np.zeros((nu, nv), bool)
    for di in (0, 1):
        for dj in (0, 1):
            utilise[di:nu - 1 + di, dj:nv - 1 + dj] |= cel
    num = -np.ones((nu, nv), np.int64)
    num[utilise] = np.arange(utilise.sum())
    n = int(utilise.sum())
    uu, vv, hh = U[utilise], Vv[utilise], H[utilise]
    haut = np.stack([-uu, base + hh, -vv], 1)
    bas = np.stack([-uu, np.full(n, base - EPAISSEUR_ANCRAGE), -vv], 1)
    V = np.concatenate([haut, bas])

    ci, cj = np.nonzero(cel)
    a, b = num[ci, cj], num[ci + 1, cj]
    c, d = num[ci + 1, cj + 1], num[ci, cj + 1]
    F = [np.stack([a, b, c], 1), np.stack([a, c, d], 1),            # dessus
         np.stack([a, c, b], 1) + n, np.stack([a, d, c], 1) + n]    # dessous
    # Flancs : arêtes de cellule qui ne bordent qu'une cellule.
    pad = np.pad(cel, 1)
    for (di, dj, p0, p1) in (
        (0, -1, (0, 0), (1, 0)),   # bord v bas de la cellule
        (1, 0, (1, 0), (1, 1)),    # bord u haut
        (0, 1, (1, 1), (0, 1)),    # bord v haut
        (-1, 0, (0, 1), (0, 0)),   # bord u bas
    ):
        voisin = pad[1 + di:1 + di + cel.shape[0], 1 + dj:1 + dj + cel.shape[1]]
        bi, bj = np.nonzero(cel & ~voisin)
        s0 = num[bi + p0[0], bj + p0[1]]
        s1 = num[bi + p1[0], bj + p1[1]]
        F += [np.stack([s0, s1 + n, s1], 1), np.stack([s0, s0 + n, s1 + n], 1)]
    F = np.concatenate(F)
    vol_signe = np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6
    if vol_signe < 0:
        F = F[:, [0, 2, 1]]
    hc = 0.25 * (H[:-1, :-1] + H[1:, :-1] + H[:-1, 1:] + H[1:, 1:])
    return V, F, float((hc * cel).sum() * pas * pas)


# — Placement de l'empreinte ——————————————————————————————————————

def lecteur_relief(emp, placement, mm_par_px):
    """(u, v) du plateau → relief 0..1. `placement` = [cx, cy, angle°] en
    pixels de l'image d'édition (y vers le bas), comme l'éditeur les pose."""
    from . import empreinte as E
    cx, cy, ang = placement
    a = np.radians(ang)
    ca, sa = np.cos(a), np.sin(a)
    H = emp.gris.shape[0]

    def lire(u, v):
        x = cx + (ca * u - sa * v) / mm_par_px
        y_bas = cy + (sa * u + ca * v) / mm_par_px
        pts = np.stack([x, H - 1 - y_bas], -1)
        yu, xu = E.vers_agrandi(pts, emp.origine, emp.facteur)
        from scipy import ndimage as ndi
        return ndi.map_coordinates(emp.relief, [yu, xu], order=1, mode="constant", cval=0.0)
    return lire


def construire(p, emp):
    """La chevalière entière, en un seul solide fermé (union par manifold3d)."""
    import manifold3d as mf

    cat = catalogue()
    forme, taille = variante(cat, p["forme"], p["plateau"])
    i = cat["fingerSizes"].index(int(p["doigt"]))
    doigt_mesh = cat["fingerMeshes"][i]
    surface = p["surface"]
    Vb, Fb = lire_jrm(_telecharger(chemin_maillage(p["forme"], p["plateau"], p["remplissage"], doigt_mesh, surface)))

    plateau = contour_centre(taille, "plateau")
    if surface == "godet":
        zone = contour_centre(taille, "cup")
        emprise = retrecir(plateau, 0.3)
        base = -float(taille["cupDepth"])
        hauteur = float(taille["cupDepth"])     # les crêtes affleurent au bord
    else:
        zone = retrecir(plateau, MARGE_PLEIN)
        emprise = zone
        base = 0.0
        hauteur = float(p["hauteur_relief"])
    mm_par_px = p["periode_mm"] / emp.periode_px
    lire = lecteur_relief(emp, p["placement_px"], mm_par_px)
    Vr, Fr, vol_relief = relief_solide(zone, emprise, lambda u, v: hauteur * lire(u, v), base,
                                       p.get("pas_relief", PAS_FABRICATION))
    m = mf.Manifold(mf.Mesh(Vb.astype(np.float32), Fb.astype(np.uint32))) + \
        mf.Manifold(mf.Mesh(Vr.astype(np.float32), Fr.astype(np.uint32)))
    mesh = m.to_mesh()
    V = np.asarray(mesh.vert_properties)[:, :3].astype(float)
    F = np.asarray(mesh.tri_verts).astype(np.int64)
    return {
        "V": V, "F": F, "statut": str(m.status()),
        "volume_base_mm3": float(mf.Manifold(mf.Mesh(Vb.astype(np.float32), Fb.astype(np.uint32))).volume()),
        "volume_mm3": float(m.volume()),
        "volume_relief_mm3": vol_relief,
        "forme": forme["name"], "doigt_mesh": doigt_mesh,
    }
