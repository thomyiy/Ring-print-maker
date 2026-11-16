"""De l'image d'empreinte à la carte de relief de la bande.

Convention : toutes les coordonnées d'image sont en « y vers le haut » (la
première ligne lue est retournée au chargement). C'est ce qui permet de dire
qu'un repère (e, n) avec n = e tourné de +90° est direct, donc que l'empreinte
n'est pas inversée quand on la plaque sur la bague avec la même orientation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    """L'image en gris, recadrée sur l'empreinte, éclairage aplani, y en haut.

    ⚠️ ON RECADRE AVANT DE RÉDUIRE. Une photo de téléphone fait 2160 × 3840 px
    et l'empreinte n'en occupe qu'un tiers : réduite d'un bloc à 1 400 px, les
    crêtes tombaient à 4 px, le moteur prenait les taches d'encre pour des
    crêtes (période lue : 61 px) et l'empreinte sortait douze fois trop petite,
    en pâté sur la bague (Thomas, 16/11/2026, empreinte encrée sur papier). On
    repère l'encre sur une vignette, on recadre l'original avec une marge, et on
    ne réduit ce recadrage que s'il dépasse encore la taille maximale."""
    from PIL import ImageOps
    avert = []
    im = Image.open(chemin)
    im = ImageOps.exif_transpose(im)        # photo de téléphone : le bon sens
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        fond = Image.new("RGBA", im.size, (255, 255, 255, 255))
        fond.alpha_composite(im)
        im = fond
    im = im.convert("L")
    W, H = im.size

    # Où est l'encre : vignette, papier aplani, seuil d'Otsu, plus grande tache.
    k = max(W, H) / 400
    if k > 1:
        v = np.asarray(im.resize((round(W / k), round(H / k)), Image.BILINEAR), float) / 255
        fond_v = ndi.gaussian_filter(v, max(v.shape) / 12)
        n = np.clip(v / np.maximum(fond_v, 1e-3), 0, 1.5)
        hist, bords = np.histogram(n, 128, (0, 1.5))
        w0 = np.cumsum(hist); w1 = w0[-1] - w0
        m0 = np.cumsum(hist * bords[:-1]); mt = m0[-1]
        var = w0 * w1 * (m0 / np.maximum(w0, 1) - (mt - m0) / np.maximum(w1, 1)) ** 2
        seuil = bords[int(np.argmax(var))]
        encre = ndi.binary_closing(n < seuil, iterations=3)
        lab, nb = ndi.label(encre)
        if nb:
            tailles = ndi.sum(encre, lab, range(1, nb + 1))
            tache = lab == 1 + int(np.argmax(tailles))
            ys, xs = np.nonzero(tache)
            # Recadrer seulement si l'encre n'occupe qu'une partie de l'image.
            if ys.size and (np.ptp(ys) + 1) * (np.ptp(xs) + 1) < 0.6 * v.size:
                mx = 0.15 * (np.ptp(xs) + 1); my = 0.15 * (np.ptp(ys) + 1)
                x0 = max(0, int((xs.min() - mx) * k)); x1 = min(W, int((xs.max() + 1 + mx) * k))
                y0 = max(0, int((ys.min() - my) * k)); y1 = min(H, int((ys.max() + 1 + my) * k))
                im = im.crop((x0, y0, x1, y1))
                avert.append(f"Photo recadrée sur l'empreinte ({x1 - x0}×{y1 - y0} px).")

    w, h = im.size
    f = max(w, h) / TAILLE_MAX_ENTREE
    if f > 1:
        im = im.resize((round(w / f), round(h / f)), Image.LANCZOS)
        avert.append(f"Image réduite de {w}×{h} à {im.size[0]}×{im.size[1]} px.")
    g = np.asarray(im, dtype=np.float64) / 255.0
    # Papier aplani : une photo est plus sombre d'un côté que de l'autre, et un
    # seuil unique y mangerait les crêtes du côté clair ou noierait le côté sombre.
    fond = ndi.maximum_filter(ndi.gaussian_filter(g, 2), size=max(15, max(g.shape) // 25))
    fond = ndi.gaussian_filter(fond, max(g.shape) / 30)
    g = np.clip(g / np.maximum(fond, 0.05), 0, 1)
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
    # ⚠️ SEULEMENT DES PÉRIODES DE DOIGT. Une empreinte compte de 18 à 90
    # crêtes sur sa largeur ; sans cette borne, les grandes taches d'une
    # empreinte très encrée l'emportaient sur les crêtes (61 px lus pour 11).
    largeur = max(c.shape)
    pmin, pmax = max(3.0, largeur / 90), max(6.0, largeur / 18)
    rmin, rmax = max(2, int(N / pmax)), min(len(prof) - 2, int(np.ceil(N / pmin)))
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
    # ⚠️ L'AGRANDISSEMENT SUIT LA FINESSE DES CRÊTES, PAS UN CHIFFRE FIXE. ×6
    # servait les scans aux crêtes de 8 px ; une photo de téléphone recadrée en
    # a déjà 20, et ×6 y faisait filtrer 28 millions de pixels — 25 s d'attente
    # au dépôt (16/11/2026). Une crête n'a besoin que d'une cinquantaine de
    # pixels pour que le seuil doux dessine ses flancs.
    f = float(min(p["agrandissement"], max(1.0, 48.0 / periode_px)))
    if crop.size * f * f > PIXELS_MAX_AGRANDI:
        f2 = float(np.sqrt(PIXELS_MAX_AGRANDI / crop.size))
        avert.append(f"Agrandissement ramené de ×{f:g} à ×{f2:.1f} (image trop grande).")
        f = f2
    # float32 : les filtres vont deux fois plus vite, et le cache garde la
    # moitié de la mémoire. La précision dépasse de loin celle d'un scan 8 bits.
    up = ndi.zoom(crop.astype(np.float32), f, order=3, grid_mode=True, mode="nearest")
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
    soft = (1.0 / (1.0 + np.exp(-(c - t) / (p["douceur"] * plage)))).astype(np.float32)
    soft = np.clip((soft - 0.03) / 0.94, 0, 1)

    # Points isolés trop petits pour la fonte, crêtes comme creux.
    mm_up = mm_par_px / f_eff
    aire_min = p["aire_min_mm2"] / mm_up ** 2
    bin_ = soft > 0.5
    # Aires par bincount et tri par table : `ndi.sum` et `np.isin` sur une
    # image agrandie coûtaient plus que tout le reste du seuillage.
    lab, nb = ndi.label(bin_)
    if nb:
        aires = np.bincount(lab.ravel(), minlength=nb + 1)
        petit = aires < aire_min
        petit[0] = False
        garde = bin_ & ~petit[lab]
        k = max(1, int(0.25 * P))
        zone = ndi.maximum_filter(garde.view(np.uint8), size=2 * k + 1).astype(bool)
        soft = soft * zone
        retires = int(petit.sum())
    else:
        retires = 0
    trous = ~bin_ & fg_up
    lab, nb = ndi.label(trous)
    if nb:
        aires = np.bincount(lab.ravel(), minlength=nb + 1)
        petit = aires < aire_min
        petit[0] = False
        soft[petit[lab]] = 1.0
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


# — Cache ——————————————————————————————————————————————————————————
# ⚠️ LE TRAITEMENT DE L'EMPREINTE NE DÉPEND PAS DE LA BAGUE. Il était refait à
# chaque clic sur une taille ou un relief : 4 s sur 6 du recalcul, pour un
# résultat identique. Le processus Python reste chargé côté serveur (voir
# `python -m moteur serveur`), et garde ici les dernières empreintes traitées.
_CACHE: dict = {}
_CACHE_MAX = 4


def _memo(cle, calcul):
    if cle in _CACHE:
        v = _CACHE.pop(cle)
    else:
        v = calcul()
    _CACHE[cle] = v
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    return v


def _base(chemin_image, p):
    """Ce qui ne dépend que de l'image : support, période, orientation."""
    def calcul():
        g, avert = charger_gris(chemin_image)
        if p.get("miroir"):
            g = g[:, ::-1].copy()
        cretes = 1.0 - g if p["cretes_noires"] else g
        fg = masque_support(cretes)
        per = periode_cretes(cretes, fg)
        if per < 4:
            avert.append(f"Scan peu résolu : {per:.1f} px par crête, les flancs seront approximatifs.")
        theta, coh = champ_orientation(cretes, per)
        return g, fg, per, theta, coh, avert
    st = Path(chemin_image).stat()
    return _memo(("base", str(chemin_image), st.st_mtime_ns, st.st_size,
                  bool(p.get("miroir")), bool(p["cretes_noires"])), calcul)


def preparer(chemin_image, p) -> Empreinte:
    g, fg, per, theta, coh, avert0 = _base(chemin_image, p)
    avert = list(avert0)
    mm_par_px = (p["largeur_utile"] / p["cretes_largeur"]) / per
    largeur_px = p["largeur_utile"] / mm_par_px
    dec_px = p["decalage_bande"] / mm_par_px
    st = Path(chemin_image).stat()
    cle = (str(chemin_image), st.st_mtime_ns, st.st_size, bool(p.get("miroir")), bool(p["cretes_noires"]),
           # L'échelle seule compte (pour l'aire minimale des points isolés),
           # pas la largeur du fil qui y mène : changer de fil à échelle égale
           # ne retraite pas l'empreinte.
           round(mm_par_px, 7), p["flou"], p["douceur"],
           p["aire_min_mm2"], p["agrandissement"])
    manuel = p.get("bande_px")
    auto = p.get("angle_bande_deg") is None and not manuel
    if manuel:
        # Les bouts viennent de l'éditeur, y vers le bas : on repasse en y vers
        # le haut, le repère de tout le reste du module.
        ax, ay, bx, by = manuel
        H = g.shape[0]
        A = np.array([ax, H - 1 - ay])
        B = np.array([bx, H - 1 - by])
        if np.linalg.norm(B - A) < 2:
            raise ValueError("La bande posée est trop courte.")
        angle = float(np.arctan2(*(B - A)[::-1]))
        e, n = _repere(angle)
        milieu = 0.5 * (A + B)
        ys, xs = np.nonzero(fg)
        W = np.stack([xs, ys], 1) @ n
        dec_px = float(milieu @ n - 0.5 * (W.min() + W.max()))
    elif auto:
        angle, dec_px = _memo(("bande",) + cle, lambda: chercher_bande(fg, theta, coh, largeur_px))
    else:
        angle = np.radians(p["angle_bande_deg"])
    bande = placer_bande(fg, theta, coh, angle, largeur_px, dec_px, mm_par_px)
    bande.decalage_px, bande.auto = float(dec_px), auto
    def _traiter():
        av = []
        return traiter_agrandi(g, fg, per, mm_par_px, p, av) + (av,)
    relief, fg_up, origine, f, retires, avert_t = _memo(("relief",) + cle, _traiter)
    avert += avert_t
    if retires:
        avert.append(f"{retires} point(s) isolé(s) trop petit(s) pour la fonte retiré(s).")
    emp = Empreinte(g, fg, per, mm_par_px, theta, coh, relief, fg_up, origine, f, bande, avert)
    if manuel and not p.get("bord_a_bord", True):
        # Longueur choisie à la main : on la respecte telle quelle, centrée sur
        # le milieu des deux bouts. Rogner une crête est alors un choix.
        bande.centre = milieu
        bande.longueur_mm = float(np.linalg.norm(B - A) * mm_par_px)
        bande.l_min_px = -0.5 * np.linalg.norm(B - A)
        bande.l_max_px = +0.5 * np.linalg.norm(B - A)
    else:
        borner_bande(emp, p["largeur_utile"])
    return emp


def image_edition(emp: Empreinte, chemin):
    """L'empreinte traitée, à la résolution de l'image d'origine, crêtes en
    noir : c'est sur elle qu'on pose la bande dans l'éditeur. Les coordonnées
    de l'éditeur sont les pixels de cette image, y vers le bas.

    On n'affiche pas la photo envoyée : le navigateur applique l'orientation
    EXIF d'un JPEG, Pillow non — les deux images ne se superposeraient pas."""
    H, W = emp.gris.shape
    pas = emp.facteur
    petit = emp.relief[::max(1, int(round(pas))), ::max(1, int(round(pas)))]
    x0, y0 = emp.origine
    toile = np.zeros((H, W))
    h = min(petit.shape[0], H - y0)
    w = min(petit.shape[1], W - x0)
    toile[y0:y0 + h, x0:x0 + w] = petit[:h, :w]
    img = (255 * (1 - toile[::-1])).astype(np.uint8)
    Image.fromarray(img).save(chemin)
    b = emp.bande
    demi = 0.5 * b.longueur_mm / emp.mm_par_px
    A = b.centre - demi * b.e
    Bp = b.centre + demi * b.e
    return {
        "image": Path(chemin).name,
        "largeur": int(W),
        "hauteur": int(H),
        "a": [float(A[0]), float(H - 1 - A[1])],
        "b": [float(Bp[0]), float(H - 1 - Bp[1])],
        "largeur_bande_px": float(b.largeur_px),
        "mm_par_px": float(emp.mm_par_px),
    }


FACTEUR_TEXTURE = 3.0


def texture_relief(emp: Empreinte, chemin):
    """Le relief traité, pour le navigateur qui construit la bague lui-même.

    L'agrandi ×6 sert au seuillage ; pour échantillonner 40 à 50 points sur
    1,5 mm, ×3 suffit largement et pèse quatre fois moins. PNG 8 bits, ligne 0
    en haut (y le plus grand). Le navigateur passe d'un pixel d'origine (x, y
    vers le haut) à la texture par : col = (x − x0 + ½)·f − ½, ligne
    haut = (y − y0 + ½)·f − ½, ligne PNG = hauteur − 1 − ligne haut."""
    f = min(FACTEUR_TEXTURE, emp.facteur)
    r = ndi.zoom(emp.relief, f / emp.facteur, order=1, grid_mode=True, mode="nearest")
    f_eff = r.shape[1] / (emp.relief.shape[1] / emp.facteur)
    img = (np.clip(r, 0, 1)[::-1] * 255 + 0.5).astype(np.uint8)
    Image.fromarray(img).save(chemin, optimize=True)
    return {"image": Path(chemin).name, "largeur": int(img.shape[1]), "hauteur": int(img.shape[0]),
            "x0": int(emp.origine[0]), "y0": int(emp.origine[1]), "facteur": float(f_eff)}
