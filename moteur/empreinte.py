"""De l'image d'empreinte à la carte de relief de la bande.

Convention : toutes les coordonnées d'image sont en « y vers le haut » (la
première ligne lue est retournée au chargement). C'est ce qui permet de dire
qu'un repère (e, n) avec n = e tourné de +90° est direct, donc que l'empreinte
n'est pas inversée quand on la plaque sur la bague avec la même orientation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

TAILLE_MAX_ENTREE = 1400      # px, côté le plus long accepté avant réduction
PIXELS_MAX_AGRANDI = 24e6     # au-delà, l'agrandissement est réduit (et signalé)


@dataclass
class Bande:
    angle: float          # rad, direction de la bande dans l'image (y en haut)
    e: np.ndarray         # vecteur unitaire le long de la bande
    n: np.ndarray         # e tourné de +90°
    centre: np.ndarray    # px image d'origine, milieu de la bande
    largeur_px: float
    longueur_mm: float
    l_min_px: float       # bornes le long de e, depuis le centre
    l_max_px: float
    alignement: float     # 0..1, part des crêtes parallèles à la bande
    decalage_px: float = 0.0  # depuis le milieu de l'empreinte, selon n
    auto: bool = False


@dataclass
class Empreinte:
    gris: np.ndarray              # image d'origine, y en haut, 0 noir 1 blanc
    support: np.ndarray           # masque de l'empreinte, résolution d'origine
    periode_px: float
    mm_par_px: float
    orientation: np.ndarray       # rad, orientation des crêtes
    coherence: np.ndarray
    relief: np.ndarray            # 0..1, crêtes à 1, agrandi
    support_agrandi: np.ndarray
    origine: tuple                # (x0, y0) du recadrage, px d'origine
    facteur: float                # agrandissement effectif
    bande: Bande
    avertissements: list


# — Chargement ———————————————————————————————————————————————————

def charger_gris(chemin) -> tuple[np.ndarray, list]:
    avert = []
    im = Image.open(chemin)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        fond = Image.new("RGBA", im.size, (255, 255, 255, 255))
        fond.alpha_composite(im)
        im = fond
    im = im.convert("L")
    w, h = im.size
    f = max(w, h) / TAILLE_MAX_ENTREE
    if f > 1:
        im = im.resize((round(w / f), round(h / f)), Image.LANCZOS)
        avert.append(f"Image réduite de {w}×{h} à {im.size[0]}×{im.size[1]} px.")
    g = np.asarray(im, dtype=np.float64) / 255.0
    return g[::-1].copy(), avert


# — Analyse à la résolution d'origine ————————————————————————————————

def _plus_grande_composante(m: np.ndarray) -> np.ndarray:
    lab, n = ndi.label(m)
    if n <= 1:
        return m
    tailles = ndi.sum(m, lab, index=np.arange(1, n + 1))
    return lab == (1 + int(np.argmax(tailles)))


def masque_support(cretes: np.ndarray) -> np.ndarray:
    """Là où l'image a du contraste de crêtes. Un masque dur : hors empreinte il
    n'y a pas de crête, on n'adoucit pas le contour."""
    sig = max(4.0, min(cretes.shape) / 50)
    m = ndi.gaussian_filter(cretes, sig)
    v = ndi.gaussian_filter(cretes ** 2, sig) - m ** 2
    s = np.sqrt(np.clip(v, 0, None))
    fg = s > 0.3 * np.percentile(s, 99.5)
    fg = ndi.binary_closing(fg, iterations=int(sig))
    fg = ndi.binary_fill_holes(fg)
    fg = _plus_grande_composante(fg)
    if fg.sum() < 100:
        raise ValueError("Aucune empreinte détectée dans l'image.")
    return fg


def periode_cretes(cretes: np.ndarray, fg: np.ndarray) -> float:
    """Période dominante par le spectre de puissance, moyenné en anneaux."""
    ys, xs = np.nonzero(fg)
    c = cretes[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = fg[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    c = (c - c[m].mean()) * m
    c = c * np.outer(np.hanning(c.shape[0]), np.hanning(c.shape[1]))
    N = int(2 ** np.ceil(np.log2(max(c.shape) * 2)))
    P = np.abs(np.fft.fftshift(np.fft.fft2(c, (N, N)))) ** 2
    yy, xx = np.indices(P.shape)
    r = np.hypot(yy - N // 2, xx - N // 2).astype(int)
    prof = np.bincount(r.ravel(), P.ravel()) / np.maximum(np.bincount(r.ravel()), 1)
    rmin, rmax = int(N / 60), int(N / 3)          # périodes de 3 à 60 px
    k = rmin + int(np.argmax(prof[rmin:rmax]))
    # raffinement parabolique du pic
    if 1 <= k < len(prof) - 1:
        a, b, cc = np.log(prof[k - 1:k + 2] + 1e-30)
        k = k + 0.5 * (a - cc) / (a - 2 * b + cc)
    return N / k


def champ_orientation(cretes: np.ndarray, periode: float):
    gx = ndi.gaussian_filter(cretes, 1.0, order=(0, 1))
    gy = ndi.gaussian_filter(cretes, 1.0, order=(1, 0))
    s = 1.5 * periode
    jxx = ndi.gaussian_filter(gx * gx, s)
    jyy = ndi.gaussian_filter(gy * gy, s)
    jxy = ndi.gaussian_filter(gx * gy, s)
    theta_grad = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
    coh = np.hypot(jxx - jyy, 2 * jxy) / (jxx + jyy + 1e-12)
    return theta_grad + np.pi / 2, coh


def _repere(angle):
    e = np.array([np.cos(angle), np.sin(angle)])
    return e, np.array([-e[1], e[0]])


def chercher_bande(fg, theta, coh, largeur_px):
    """Angle et décalage de la bande où les crêtes filent le mieux en long.

    Le décalage se compte depuis le milieu de l'empreinte, perpendiculairement
    à la bande. Pour une boucle ou un tourbillon, une bande qui passe par le
    centre coupe les crêtes partout à angle droit : il faut chercher de côté.

    Score : part pondérée par la cohérence de cos²(crête − bande), multipliée
    par le carré du remplissage et la racine de la longueur relative — un bout
    de bord très court ou à moitié vide ne doit pas l'emporter sur une vraie
    traversée."""
    ys, xs = np.nonzero(fg)
    pas = max(1, int(np.sqrt(len(xs) / 60000)))
    pts = np.stack([xs[::pas], ys[::pas]], 1).astype(float)
    th, co = theta[ys[::pas], xs[::pas]], coh[ys[::pas], xs[::pas]]
    ext = np.ptp(pts, 0).max()
    q = 4                                   # tranches par largeur de bande
    h = largeur_px / q
    meilleur = (-1, 0.0, 0.0, 0.0)
    for a in np.radians(np.arange(0, 180, 1.0)):
        e, n = _repere(a)
        W, L = pts @ n, pts @ e
        w0 = W.min()
        k = ((W - w0) / h).astype(int)
        nb = k.max() + 1
        if nb < q:
            continue
        num = np.bincount(k, co * np.cos(th - a) ** 2, nb)
        den = np.bincount(k, co, nb)
        lmin = np.full(nb, np.inf); np.minimum.at(lmin, k, L)
        lmax = np.full(nb, -np.inf); np.maximum.at(lmax, k, L)
        noyau = np.ones(q)
        N_ = np.convolve(num, noyau, "valid")
        D_ = np.convolve(den, noyau, "valid")
        fen = np.lib.stride_tricks.sliding_window_view
        lo = fen(lmin, q).min(1)
        hi = fen(lmax, q).max(1)
        longueur = np.where(np.isfinite(lo) & np.isfinite(hi), hi - lo, 0)
        # Remplissage : une bande posée sur le bord de l'empreinte laisse une
        # moitié de face lisse, ce que la largeur « bord à bord » interdit.
        compte = np.convolve(np.bincount(k, None, nb), noyau, "valid") * pas
        remplissage = np.clip(compte / (np.maximum(longueur, 1) * largeur_px), 0, 1)
        score = (N_ / (D_ + 1e-12) * remplissage ** 2
                 * np.sqrt(np.clip(longueur / ext, 0, 1)))
        score[longueur < 0.35 * ext] = -1
        i = int(np.argmax(score))
        if score[i] > meilleur[0]:
            centre_w = w0 + (i + q / 2) * h
            meilleur = (score[i], a, centre_w - 0.5 * (W.min() + W.max()), N_[i] / (D_[i] + 1e-12))
    if meilleur[0] < 0:
        raise ValueError("Empreinte trop petite pour y placer une bande.")
    return meilleur[1], meilleur[2]


def placer_bande(fg, theta, coh, angle, largeur_px, decalage_px, mm_par_px) -> Bande:
    ys, xs = np.nonzero(fg)
    pts = np.stack([xs, ys], 1).astype(float)
    e, n = _repere(angle)
    W = pts @ n
    d = 0.5 * (W.min() + W.max()) + decalage_px
    dedans = np.abs(W - d) <= largeur_px / 2
    if dedans.sum() < 20:
        raise ValueError("La bande sort de l'empreinte : réduire le décalage.")
    L = pts[dedans] @ e
    lc = 0.5 * (L.min() + L.max())
    th, co = theta[ys[dedans], xs[dedans]], coh[ys[dedans], xs[dedans]]
    al = float(np.sum(co * np.cos(th - angle) ** 2) / (np.sum(co) + 1e-12))
    return Bande(angle=float(angle), e=e, n=n, centre=lc * e + d * n,
                 largeur_px=largeur_px, longueur_mm=float(np.ptp(L) * mm_par_px),
                 l_min_px=float(L.min() - lc), l_max_px=float(L.max() - lc),
                 alignement=al)


# — Traitement agrandi ——————————————————————————————————————————————

def traiter_agrandi(g, fg, periode_px, mm_par_px, p, avert):
    """Agrandissement, léger flou, seuillage doux, retrait des points isolés.

    Rendu : carte 0..1 (crêtes à 1) et masque dur, sur le recadrage de
    l'empreinte agrandi."""
    ys, xs = np.nonzero(fg)
    marge = int(2 * periode_px) + 2
    y0, y1 = max(0, ys.min() - marge), min(g.shape[0], ys.max() + marge + 1)
    x0, x1 = max(0, xs.min() - marge), min(g.shape[1], xs.max() + marge + 1)
    crop = g[y0:y1, x0:x1]
    f = float(p["agrandissement"])
    if crop.size * f * f > PIXELS_MAX_AGRANDI:
        f2 = float(np.sqrt(PIXELS_MAX_AGRANDI / crop.size))
        avert.append(f"Agrandissement ramené de ×{f:g} à ×{f2:.1f} (image trop grande).")
        f = f2
    up = ndi.zoom(crop, f, order=3, grid_mode=True, mode="nearest")
    fg_up = ndi.zoom(fg[y0:y1, x0:x1].astype(np.uint8), f, order=0, grid_mode=True,
                     mode="nearest").astype(bool)
    f_eff = up.shape[1] / crop.shape[1]
    P = periode_px * f_eff
    c = 1.0 - up if p["cretes_noires"] else up.copy()
    if p["flou"] > 0:
        c = ndi.gaussian_filter(c, p["flou"] * P)
    lo, hi = np.percentile(c[fg_up], [1, 99])
    plage = max(hi - lo, 1e-3)
    m = ndi.gaussian_filter(c, 0.7 * P)
    # Seuil local borné : sur un scan inégal il suit la moyenne, mais dans le
    # blanc autour de l'empreinte il ne descend pas à zéro — sinon le vide
    # sortirait à mi-hauteur au lieu de rester à la cote de la face.
    t = np.clip(m, lo + 0.3 * plage, lo + 0.7 * plage)
    soft = 1.0 / (1.0 + np.exp(-(c - t) / (p["douceur"] * plage)))
    soft = np.clip((soft - 0.03) / 0.94, 0, 1)

    # Points isolés trop petits pour la fonte, crêtes comme creux.
    mm_up = mm_par_px / f_eff
    aire_min = p["aire_min_mm2"] / mm_up ** 2
    bin_ = soft > 0.5
    lab, nb = ndi.label(bin_)
    if nb:
        aires = ndi.sum(bin_, lab, index=np.arange(1, nb + 1))
        petits = np.isin(lab, 1 + np.nonzero(aires < aire_min)[0])
        garde = bin_ & ~petits
        zone = ndi.binary_dilation(garde, iterations=max(1, int(0.25 * P)))
        soft = soft * zone
        retires = int(np.sum(aires < aire_min))
    else:
        retires = 0
    trous = ~bin_ & fg_up
    lab, nb = ndi.label(trous)
    if nb:
        aires = ndi.sum(trous, lab, index=np.arange(1, nb + 1))
        petits = np.isin(lab, 1 + np.nonzero(aires < aire_min)[0])
        soft[petits] = 1.0
    soft = soft * fg_up
    return soft, fg_up, (x0, y0), f_eff, retires


def vers_agrandi(pts_px, origine, f):
    """px d'origine (x, y) → indices (ligne, colonne) de l'image agrandie."""
    x0, y0 = origine
    xu = (pts_px[..., 0] - x0 + 0.5) * f - 0.5
    yu = (pts_px[..., 1] - y0 + 0.5) * f - 0.5
    return yu, xu


def echantillonner(emp: Empreinte, L_mm, W_mm):
    """Relief 0..1 aux coordonnées de bande (mm, depuis le centre)."""
    b = emp.bande
    k = 1.0 / emp.mm_par_px
    pts = (b.centre + (np.asarray(L_mm)[..., None] * k) * b.e
           + (np.asarray(W_mm)[..., None] * k) * b.n)
    yu, xu = vers_agrandi(pts, emp.origine, emp.facteur)
    return ndi.map_coordinates(emp.relief, [yu, xu], order=1, mode="constant", cval=0.0)


def borner_bande(emp: Empreinte, largeur_mm):
    """Resserre la longueur sur les crêtes réelles, sans rogner la dernière :
    on sonde toute la largeur de la bande et on garde une demi-période de plus."""
    b = emp.bande
    pas = emp.mm_par_px / emp.facteur
    marge = 2 * emp.periode_px * emp.mm_par_px
    L = np.arange(b.l_min_px * emp.mm_par_px - marge, b.l_max_px * emp.mm_par_px + marge, pas)
    W = np.linspace(-largeur_mm / 2, largeur_mm / 2, 25)
    H = echantillonner(emp, L[:, None], W[None, :])
    cols = np.nonzero(H.max(1) > 0.05)[0]
    if len(cols) == 0:
        raise ValueError("Aucune crête dans la bande.")
    demi = 0.5 * emp.periode_px * emp.mm_par_px
    lmin, lmax = L[cols[0]] - demi, L[cols[-1]] + demi
    # recentre : le milieu des deux bords devient le sommet de la bague
    lc = 0.5 * (lmin + lmax)
    b.centre = b.centre + (lc / emp.mm_par_px) * b.e
    b.longueur_mm = float(lmax - lmin)
    b.l_min_px = -0.5 * b.longueur_mm / emp.mm_par_px
    b.l_max_px = +0.5 * b.longueur_mm / emp.mm_par_px


def preparer(chemin_image, p) -> Empreinte:
    g, avert = charger_gris(chemin_image)
    if p.get("miroir"):
        g = g[:, ::-1].copy()
    cretes = 1.0 - g if p["cretes_noires"] else g
    fg = masque_support(cretes)
    per = periode_cretes(cretes, fg)
    if per < 4:
        avert.append(f"Scan peu résolu : {per:.1f} px par crête, les flancs seront approximatifs.")
    mm_par_px = (p["largeur_utile"] / p["cretes_largeur"]) / per
    theta, coh = champ_orientation(cretes, per)
    largeur_px = p["largeur_utile"] / mm_par_px
    dec_px = p["decalage_bande"] / mm_par_px
    auto = p.get("angle_bande_deg") is None
    if auto:
        angle, dec_px = chercher_bande(fg, theta, coh, largeur_px)
    else:
        angle = np.radians(p["angle_bande_deg"])
    bande = placer_bande(fg, theta, coh, angle, largeur_px, dec_px, mm_par_px)
    bande.decalage_px, bande.auto = float(dec_px), auto
    relief, fg_up, origine, f, retires = traiter_agrandi(g, fg, per, mm_par_px, p, avert)
    if retires:
        avert.append(f"{retires} point(s) isolé(s) trop petit(s) pour la fonte retiré(s).")
    emp = Empreinte(g, fg, per, mm_par_px, theta, coh, relief, fg_up, origine, f, bande, avert)
    borner_bande(emp, p["largeur_utile"])
    return emp
