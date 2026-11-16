"""Le masque complet avec le cadre de la bande, et la bande déroulée."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import empreinte as E

VERT_TEXTE = "#485D27"
ROSE = "#C47396"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 9,
                     "axes.edgecolor": "#E6E6E6", "axes.labelcolor": "#33373D",
                     "xtick.color": "#A6A6A6", "ytick.color": "#A6A6A6"})


def figure_masque(emp: E.Empreinte, chemin):
    R = emp.relief
    pas = max(1, int(max(R.shape) / 1400))
    R = R[::pas, ::pas]
    x0, y0 = emp.origine
    f = emp.facteur
    # étendue en px d'origine, pour tracer le cadre dans le même repère
    ext = [x0 - 0.5, x0 - 0.5 + emp.relief.shape[1] / f, y0 - 0.5, y0 - 0.5 + emp.relief.shape[0] / f]
    k = emp.mm_par_px
    ext_mm = [v * k for v in ext]
    fig, ax = plt.subplots(figsize=(6.5, 6.5 * R.shape[0] / R.shape[1] + 0.4), dpi=170)
    ax.imshow(R, cmap="gray_r", origin="lower", extent=ext_mm, vmin=0, vmax=1, interpolation="antialiased")
    b = emp.bande
    demi_l = 0.5 * b.longueur_mm / k
    demi_w = 0.5 * b.largeur_px
    coins = [b.centre + sl * demi_l * b.e + sw * demi_w * b.n
             for sl, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
    coins = np.array(coins) * k
    ax.plot(coins[:, 0], coins[:, 1], color=ROSE, lw=1.4)
    c = b.centre * k
    ax.plot(*c, "o", color=ROSE, ms=4)
    ax.annotate("", xy=c + b.e * demi_l * k * 0.45, xytext=c,
                arrowprops=dict(arrowstyle="->", color=ROSE, lw=1.2))
    ax.text(*(c + b.n * (demi_w * k + 0.25)), "sommet", color=ROSE, ha="center", va="bottom", fontsize=8)
    ax.set_xlabel("mm"); ax.set_ylabel("mm")
    ax.set_title(f"Bande {np.degrees(b.angle):.0f}° · {b.longueur_mm:.2f} × {b.largeur_px * k:.2f} mm · "
                 f"crêtes alignées à {100 * b.alignement:.0f} %", color="#33373D", fontsize=9, loc="left")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(chemin, facecolor="white")
    plt.close(fig)


def bande_deroulee(emp: E.Empreinte, largeur_mm, pas_mm=0.005):
    b = emp.bande
    L = np.arange(-b.longueur_mm / 2, b.longueur_mm / 2 + pas_mm, pas_mm)
    W = np.arange(-largeur_mm / 2, largeur_mm / 2 + pas_mm / 2, pas_mm)
    return L, W, E.echantillonner(emp, L[None, :], W[:, None])


def figure_bande(emp: E.Empreinte, p, chemin):
    L, W, H = bande_deroulee(emp, p["largeur_utile"])
    H = H * p["hauteur_relief"]
    lg = L[-1] - L[0]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 2.6 + 10 * (W[-1] - W[0]) / lg),
                                  dpi=170, gridspec_kw={"height_ratios": [W[-1] - W[0], 0.6]})
    ax.imshow(H, cmap="gray_r", origin="lower", extent=[L[0], L[-1], W[0], W[-1]],
              vmin=0, vmax=p["hauteur_relief"], interpolation="antialiased")
    ax.axvline(0, color=ROSE, lw=0.8, ls=":")
    ax.set_aspect("equal")
    ax.set_ylabel("largeur, mm")
    ax.set_title("Bande déroulée vue de l'extérieur — sommet de la bague au trait pointillé",
                 color="#33373D", fontsize=9, loc="left")
    j = len(L) // 2
    ax2.fill_between(W, 0, H[:, j], color="#A3C471", lw=0)
    ax2.plot(W, H[:, j], color=VERT_TEXTE, lw=0.8)
    ax2.set_xlim(W[0], W[-1]); ax2.set_ylim(0, p["hauteur_relief"] * 1.3)
    ax2.set_xlabel("coupe au sommet, en travers de la face (mm)"); ax2.set_ylabel("mm")
    ax2.set_aspect("equal")
    ax.set_xlabel("le long de la bague, mm")
    fig.tight_layout()
    fig.savefig(chemin, facecolor="white")
    plt.close(fig)
