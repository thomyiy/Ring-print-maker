"""Rendus de contrôle sans dépendance 3D : un tramage de triangles en numpy.

Chaque triangle visible est échantillonné en coordonnées barycentriques assez
serré pour ne pas laisser de trou, puis un tampon de profondeur garde le plus
proche. Projection orthographique : c'est un rendu de contrôle, pas une photo.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

OR = np.array([0.83, 0.68, 0.38])
FOND = np.array([1.0, 1.0, 1.0])


def camera(direction, haut):
    f = -np.asarray(direction, float)
    f /= np.linalg.norm(f)
    r = np.cross(f, haut)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return f, r, u


def rendre(V, F, direction, haut, largeur_px=1200, centre=None, champ=None,
           couleur=OR, rayon_lumiere=None):
    f, r, u = camera(direction, haut)
    x, y, z = V @ r, V @ u, -(V @ f)          # z : vers la caméra
    a, b, c = F[:, 0], F[:, 1], F[:, 2]
    n = np.cross(V[b] - V[a], V[c] - V[a])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
    vis = (n @ -f) > 0
    if centre is None:
        cx, cy = 0.5 * (x.min() + x.max()), 0.5 * (y.min() + y.max())
        w = 1.08 * max(np.ptp(x), np.ptp(y))
    else:
        cx, cy = np.asarray(centre, float) @ r, np.asarray(centre, float) @ u
        w = champ
    px = largeur_px / w
    H = W = largeur_px
    sx, sy = (x - cx) * px + W / 2, (cy - y) * px + H / 2
    dedans = vis & (np.minimum(np.minimum(sx[a], sx[b]), sx[c]) < W) \
        & (np.maximum(np.maximum(sx[a], sx[b]), sx[c]) >= 0) \
        & (np.minimum(np.minimum(sy[a], sy[b]), sy[c]) < H) \
        & (np.maximum(np.maximum(sy[a], sy[b]), sy[c]) >= 0)
    T = np.nonzero(dedans)[0]

    # Éclairage : une clé, un contre, une ambiance ; une pointe spéculaire.
    L1 = 0.4 * r + 0.75 * u - 0.55 * f; L1 /= np.linalg.norm(L1)
    L2 = -0.6 * r - 0.2 * u - 0.3 * f; L2 /= np.linalg.norm(L2)
    nT = n[T]
    d1 = np.clip(nT @ L1, 0, None)
    d2 = np.clip(nT @ L2, 0, None)
    hv = L1 - f; hv /= np.linalg.norm(hv)
    spec = np.clip(nT @ hv, 0, None) ** 40
    ombre = 0.22 + 0.62 * d1 + 0.22 * d2
    teinte = np.clip(couleur[None] * ombre[:, None] + 0.45 * spec[:, None], 0, 1)

    img = np.ones((H, W, 3)) * FOND
    prof = np.full(H * W, -np.inf)
    # Échantillonnage : k pas par arête, selon la plus grande arête projetée.
    tx = np.stack([sx[a[T]], sx[b[T]], sx[c[T]]], 1)
    ty = np.stack([sy[a[T]], sy[b[T]], sy[c[T]]], 1)
    tz = np.stack([z[a[T]], z[b[T]], z[c[T]]], 1)
    taille = np.max(np.hypot(tx - np.roll(tx, 1, 1), ty - np.roll(ty, 1, 1)), 1)
    k_tri = np.clip(np.ceil(taille * 1.5).astype(int), 1, 40)
    toutes_pix, toutes_z, toutes_c = [], [], []
    for k in np.unique(k_tri):
        sel = np.nonzero(k_tri == k)[0]
        i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1))
        m = (i + j) <= k
        w1, w2 = (i[m] / k), (j[m] / k)
        w0 = 1 - w1 - w2
        X = tx[sel, 0, None] * w0 + tx[sel, 1, None] * w1 + tx[sel, 2, None] * w2
        Y = ty[sel, 0, None] * w0 + ty[sel, 1, None] * w1 + ty[sel, 2, None] * w2
        Z = tz[sel, 0, None] * w0 + tz[sel, 1, None] * w1 + tz[sel, 2, None] * w2
        ix, iy = X.astype(int).ravel(), Y.astype(int).ravel()
        ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
        toutes_pix.append((iy * W + ix)[ok])
        toutes_z.append(Z.ravel()[ok])
        toutes_c.append(np.repeat(sel, m.sum())[ok])
    pix = np.concatenate(toutes_pix)
    zz = np.concatenate(toutes_z)
    cc = np.concatenate(toutes_c)
    ordre = np.lexsort((-zz, pix))
    pix, cc = pix[ordre], cc[ordre]
    premier = np.concatenate([[True], pix[1:] != pix[:-1]])
    flat = img.reshape(-1, 3)
    flat[pix[premier]] = teinte[cc[premier]]
    return Image.fromarray((img * 255).astype(np.uint8))


def rendus_controle(m, p, dossier):
    V, F = m.V, m.F
    sorties = {}
    # Vue générale, trois quarts.
    im = rendre(V, F, direction=(0.9, 0.75, 1.25), haut=(0, 1, 0), largeur_px=1400)
    im.save(dossier / "rendu_general.png"); sorties["general"] = "rendu_general.png"
    # Vue de dessus, bague portée : on regarde le sommet depuis +Y, le doigt
    # vertical dans l'image.
    im = rendre(V, F, direction=(0, 1, 0), haut=(0, 0, -1), largeur_px=1400)
    im.save(dossier / "rendu_dessus.png"); sorties["dessus"] = "rendu_dessus.png"
    # Gros plan du relief, même axe.
    R = p["diametre_interieur"] / 2 + p["cote"]
    L = max(np.ptp(m.s[np.nonzero(m.relief.max(1) > 0)[0]]) if m.relief.max() > 0 else 6, 3)
    im = rendre(V, F, direction=(0, 1, 0), haut=(0, 0, -1), largeur_px=1600,
                centre=(0, R, 0), champ=1.1 * L)
    im.save(dossier / "rendu_relief.png"); sorties["relief"] = "rendu_relief.png"
    return sorties
