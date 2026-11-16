"""Géométrie de l'alliance torsadée et son maillage fermé.

Le fil est un carré à arêtes rayonnées, décrit dans le plan de section (u, v) :
u le long de l'axe du doigt (Z), v vers l'extérieur (radial). Sans torsion, la
face texturée est le chant u = −a/2 (« chant gauche »). Elle tourne de
`torsion` sur l'arc de torsion, passe face à l'extérieur au sommet, et finit sur
le chant opposé.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import empreinte as E


@dataclass
class Profil:
    uv: np.ndarray      # (N, 2) points du carré rayonné, sens trigonométrique
    nrm: np.ndarray     # (N, 2) normales sortantes
    face: np.ndarray    # (N,) numéro de face plate (0..3), −1 sur les arêtes
    t: np.ndarray       # (N,) abscisse sur la face plate, 0 au milieu


def profil_carre(a, r, n_face, n_coin) -> Profil:
    """Quatre faces de `n_face` points (extrémités comprises, aux points de
    tangence) et quatre arcs de `n_coin` points intérieurs. Le nombre total est
    multiple de 4 : un demi-tour décale exactement les indices de N/2."""
    b = a / 2 - r
    uv, nrm, face, t = [], [], [], []
    for k in range(4):
        psi = np.pi + k * np.pi / 2                 # normale : gauche, bas, droite, haut
        nk = np.array([np.cos(psi), np.sin(psi)])
        tau = np.array([-nk[1], nk[0]])             # sens trigonométrique
        for tt in np.linspace(-b, b, n_face):
            uv.append(nk * (a / 2) + tau * tt); nrm.append(nk); face.append(k); t.append(tt)
        n2 = np.array([np.cos(psi + np.pi / 2), np.sin(psi + np.pi / 2)])
        c = (nk + n2) * b
        for ang in psi + np.linspace(0, np.pi / 2, n_coin + 2)[1:-1]:
            d = np.array([np.cos(ang), np.sin(ang)])
            uv.append(c + r * d); nrm.append(d); face.append(-1); t.append(0.0)
    return Profil(np.array(uv), np.array(nrm), np.array(face), np.array(t))


def loi_torsion(phi, p):
    """Angle de rotation de la section en fonction de φ (0 au sommet).

    Vitesse constante sur l'arc, avec une rampe en cosinus sur une petite part
    `adouci` à chaque bout : pas de plateau, pas de torsion concentrée au
    milieu. Intégrale exacte, normalisée pour donner `torsion` au total."""
    A = np.radians(p["arc_torsion_deg"]) / 2
    T = np.radians(p["torsion_deg"])
    e = float(p["adouci"])
    x = np.clip((np.asarray(phi) + A) / (2 * A), 0, 1)
    if e <= 0:
        return T * x

    def R(x):
        return np.where(x < e, 0.5 * (x - e / np.pi * np.sin(np.pi * x / e)), e / 2 + (x - e))

    r = np.where(x <= 0.5, R(x), (1 - e) - R(1 - x))
    return T * r / (1 - e)


def _abs_lisse(x, d):
    """|x|, arrondi en parabole sous d : jamais en dessous de |x|, raccord C1."""
    ax = np.abs(x)
    if d <= 0:
        return ax
    return np.where(ax >= d, ax, 0.5 * (x * x / d + d))


def rayon_centre(alpha, a, r, lissage):
    """Où poser le centre de la section pour que l'intérieur touche le doigt.

    ⚠️ LE PLI AU SOMMET VENAIT D'ICI. La demi-hauteur exacte
    b·(|cos α| + |sin α|) + r a un angle vif à α = 90° — pile au sommet, là où
    la torsion tourne le plus vite. Toute la section y prenait une cassure,
    visible de face comme un pli sur le chant (Thomas, 16/11/2026). On arrondit
    |cos α| sous `lissage` : l'intérieur s'écarte alors du doigt d'au plus
    b·lissage/2 au sommet (0,03 mm par défaut) et le touche partout ailleurs.

    |sin α| n'est pas arrondi : il ne passe par zéro qu'aux deux bouts de la
    torsion, où l'adouci ramène déjà la vitesse à zéro, donc sans cassure — et
    l'arrondir écarterait l'intérieur du doigt sur toute la partie droite."""
    b = a / 2 - r
    return b * (_abs_lisse(np.cos(alpha), lissage) + np.abs(np.sin(alpha))) + r


def demi_hauteur(alpha, a, r):
    """Demi-étendue radiale (et axiale) du carré rayonné tourné de alpha."""
    b = a / 2 - r
    return b * (np.abs(np.cos(alpha)) + np.abs(np.sin(alpha))) + r


@dataclass
class Maillage:
    V: np.ndarray
    F: np.ndarray
    M: int
    N: int
    phi: np.ndarray
    alpha: np.ndarray
    Rc: np.ndarray
    profil: Profil
    k0: int                 # face texturée
    s: np.ndarray           # abscisse curviligne de la face texturée, par section
    relief: np.ndarray      # (M, n_face) hauteur posée sur la face texturée
    signe_W: float


def _sections(p, prof, k0, H=None):
    """Positions 3D de toutes les sections, avec le relief H (M, n_face)."""
    M = p["n_sections"]
    a, r, R_in = p["cote"], p["rayon_arete"], p["diametre_interieur"] / 2
    sig = p["sens"]
    phi = -np.pi + 2 * np.pi * np.arange(M) / M
    alpha = loi_torsion(phi, p)
    Rc = R_in + rayon_centre(alpha, a, r, p.get("lissage_sommet", 0.0))
    uv = np.broadcast_to(prof.uv, (M,) + prof.uv.shape).copy()
    if H is not None:
        idx = np.nonzero(prof.face == k0)[0]
        uv[:, idx, :] += H[:, :, None] * prof.nrm[idx][None]
    c, s_ = np.cos(sig * alpha)[:, None], np.sin(sig * alpha)[:, None]
    u = uv[..., 0] * c + uv[..., 1] * s_
    v = -uv[..., 0] * s_ + uv[..., 1] * c
    rad = Rc[:, None] + v
    V = np.stack([rad * np.sin(phi)[:, None], rad * np.cos(phi)[:, None], u], -1)
    return V, phi, alpha, Rc


def _normale_3d(n2, alpha, phi, sens):
    """Normale du profil (u, v) tournée avec la section puis posée en 3D."""
    n2 = np.asarray(n2, float)
    c, s_ = np.cos(sens * alpha), np.sin(sens * alpha)
    nu = n2[..., 0] * c + n2[..., 1] * s_
    nv = -n2[..., 0] * s_ + n2[..., 1] * c
    return np.stack([nv * np.sin(phi), nv * np.cos(phi), nu], -1)


def construire(p, emp: E.Empreinte | None) -> Maillage:
    prof = profil_carre(p["cote"], p["rayon_arete"], p["n_face"], p["n_coin"])
    N, M = len(prof.uv), p["n_sections"]
    # Sens +1 : le chant gauche (face 0) monte par la rotation −α. Sens −1 : le
    # chant droit (face 2) monte par la rotation +α. Dans les deux cas c'est la
    # face qui passe au sommet qui porte l'empreinte.
    k0 = 0 if p["sens"] > 0 else 2
    V0, phi, alpha, Rc = _sections(p, prof, k0)
    idx = np.nonzero(prof.face == k0)[0]

    # Abscisse curviligne du milieu de la face texturée, 0 au sommet.
    centre = 0.5 * (V0[:, idx[0]] + V0[:, idx[-1]])
    ds = np.linalg.norm(np.diff(centre, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(ds)])
    s -= s[M // 2]

    # Sens de lecture : (L × W)·n > 0 vu de l'extérieur, au sommet.
    j = M // 2
    dPds = centre[j + 1] - centre[j - 1]
    dPdt = V0[j, idx[-1]] - V0[j, idx[0]]
    n_out = _normale_3d(prof.nrm[idx[0]], alpha[j], phi[j], p["sens"])
    signe_W = float(np.sign(np.dot(np.cross(dPds, dPdt), n_out)))

    H = np.zeros((M, len(idx)))
    if emp is not None:
        demi = emp.bande.longueur_mm / 2
        js = np.nonzero(np.abs(s) <= demi)[0]
        L = s[js][:, None] * np.ones((1, len(idx)))
        W = signe_W * prof.t[idx][None, :] * np.ones((len(js), 1))
        H[js] = p["hauteur_relief"] * E.echantillonner(emp, L, W)
    V, *_ = _sections(p, prof, k0, H)

    F = trianguler(M, N)
    Vf = V.reshape(-1, 3)
    if volume_signe(Vf, F) < 0:
        F = F[:, [0, 2, 1]]
    return Maillage(Vf, F, M, N, phi, alpha, Rc, prof, k0, s, H, signe_W)


def trianguler(M, N):
    """Bandes de quadrilatères entre sections. La dernière se raccorde à la
    première décalée de N/2 : après un demi-tour la section est la même, aux
    indices près."""
    J = np.arange(M)[:, None]
    I = np.arange(N)[None, :]
    jn = (J + 1) % M
    dec = np.where(J == M - 1, N // 2, 0)
    a = J * N + I
    b = J * N + (I + 1) % N
    c = jn * N + (I + 1 + dec) % N
    d = jn * N + (I + dec) % N
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3),
                        np.stack([a, c, d], -1).reshape(-1, 3)])
    return F.astype(np.int64)


def volume_signe(V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) / 6.0)


def ecart_raccord(p, m: Maillage) -> float:
    """Section recalculée à φ = +π, comparée à la première décalée de N/2."""
    prof = m.profil
    a, r = p["cote"], p["rayon_arete"]
    alpha = float(loi_torsion(np.pi, p))
    Rc = p["diametre_interieur"] / 2 + rayon_centre(alpha, a, r, p.get("lissage_sommet", 0.0))
    c, s_ = np.cos(p["sens"] * alpha), np.sin(p["sens"] * alpha)
    u = prof.uv[:, 0] * c + prof.uv[:, 1] * s_
    v = -prof.uv[:, 0] * s_ + prof.uv[:, 1] * c
    rad = Rc + v
    fin = np.stack([rad * np.sin(np.pi), rad * np.cos(np.pi), u], -1)
    debut = m.V[: m.N][(np.arange(m.N) + m.N // 2) % m.N]
    return float(np.max(np.linalg.norm(fin - debut, axis=1)))


def controler(p, m: Maillage, complet=True) -> dict:
    """`complet=False` pour l'aperçu : volume et cotes seulement. L'étanchéité
    et les normales ne dépendent pas des choix du client (le maillage a la même
    topologie à chaque fois) et sont vérifiées sur le fichier de fabrication."""
    V, F = m.V, m.F
    if not complet:
        rad = np.hypot(V[:, 0], V[:, 1])
        vol = volume_signe(V, F)
        s_rel = m.s[np.nonzero(m.relief.max(1) > 0.02 * p["hauteur_relief"])[0]]
        return {
            "diametre_interieur_min": float(2 * rad.min()),
            "diametre_exterieur_max": float(2 * rad.max()),
            "largeur_max": float(2 * demi_hauteur(m.alpha, p["cote"], p["rayon_arete"]).max()),
            "volume_mm3": vol,
            "poids_or_750_g": vol / 1000 * p["densite_or"],
            "poids_argent_925_g": vol / 1000 * p["densite_argent"],
            "longueur_arc_relief_mm": float(np.ptp(s_rel)) if len(s_rel) else 0.0,
        }
    # Étanchéité : chaque arête non orientée vue exactement deux fois, et
    # chaque arête orientée une seule fois (orientation cohérente).
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    nv = len(V)
    cle_o = e[:, 0] * nv + e[:, 1]
    cle = np.minimum(e[:, 0], e[:, 1]) * nv + np.maximum(e[:, 0], e[:, 1])
    _, cpt = np.unique(cle, return_counts=True)
    _, cpt_o = np.unique(cle_o, return_counts=True)
    etanche = bool(np.all(cpt == 2) and np.all(cpt_o == 1))

    # Normales : comparées à la normale du profil lisse au premier sommet.
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    nt = np.cross(b - a, c - a)
    j, i = F[:, 0] // m.N, F[:, 0] % m.N
    nref = _normale_3d(m.profil.nrm[i], m.alpha[j], m.phi[j], p["sens"])
    sortantes = float(np.mean(np.einsum("ij,ij->i", nt, nref) > 0))
    aires = 0.5 * np.linalg.norm(nt, axis=1)

    rad = np.hypot(V[:, 0], V[:, 1])
    vol = volume_signe(V, F)
    s_rel = m.s[np.nonzero(m.relief.max(1) > 0.02 * p["hauteur_relief"])[0]]
    return {
        "etanche": etanche,
        "aretes_non_partagees_par_2": int(np.sum(cpt != 2)),
        "normales_sortantes": sortantes,
        "triangles_degeneres": int(np.sum(aires < 1e-10)),
        "diametre_interieur_min": float(2 * rad.min()),
        "diametre_interieur_cote": p["diametre_interieur"],
        "diametre_exterieur_max": float(2 * rad.max()),
        "largeur_max": float(2 * demi_hauteur(m.alpha, p["cote"], p["rayon_arete"]).max()),
        "ecart_raccord": ecart_raccord(p, m),
        "volume_mm3": vol,
        "poids_or_750_g": vol / 1000 * p["densite_or"],
        "poids_argent_925_g": vol / 1000 * p["densite_argent"],
        "longueur_arc_relief_mm": float(np.ptp(s_rel)) if len(s_rel) else 0.0,
        "pas_tour_mm": float(2 * np.pi * (p["diametre_interieur"] / 2 + p["cote"]) / m.M),
        "pas_face_mm": float(p["largeur_utile"] / (p["n_face"] - 1)),
        "sommets": int(len(V)),
        "triangles": int(len(F)),
    }


def ecrire_grille(chemin, m: Maillage):
    """L'aperçu pour le navigateur : en-tête int32 (M, N, sens des triangles)
    puis les sommets en float32, section par section. Le navigateur refait la
    triangulation de `trianguler`, raccord décalé de N/2 compris."""
    # `trianguler` commence par (0, 1, N+1) ; `construire` a permuté les deux
    # derniers sommets si le volume sortait négatif.
    inverse = 0 if int(m.F[0][1]) == 1 else 1
    with open(chemin, "wb") as f:
        f.write(np.array([m.M, m.N, inverse], dtype="<i4").tobytes())
        f.write(m.V.astype("<f4").tobytes())


def ecrire_stl(chemin, V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
    rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("x", "<u2")])
    rec["n"] = n
    rec["v"] = np.stack([a, b, c], 1)
    with open(chemin, "wb") as f:
        f.write(b"Alliance torsadee - empreinte en relief".ljust(80, b" "))
        f.write(np.uint32(len(F)).tobytes())
        f.write(rec.tobytes())
