"""Une empreinte synthétique en noir et blanc, pour les essais sans scan."""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def empreinte_synthetique(chemin, largeur=420, hauteur=540, periode=9.0, graine=3):
    rng = np.random.default_rng(graine)
    y, x = np.mgrid[0:hauteur, 0:largeur].astype(float)
    X = (x - largeur * 0.5) / largeur
    Y = (y - hauteur * 0.42) / hauteur
    bruit = ndi.gaussian_filter(rng.normal(size=(hauteur, largeur)), 40)
    bruit /= bruit.std()
    # Boucle : cercles excentrés, qui s'ouvrent vers le bas en arcs.
    r = np.hypot(X * 1.15, Y) + 0.35 * Y + 0.012 * bruit
    phase = r * largeur / periode
    cretes = np.cos(2 * np.pi * phase) > 0.0
    bord = ((X / 0.45) ** 2 + ((y - hauteur * 0.5) / hauteur / 0.47) ** 2) < 1 + 0.06 * bruit
    noir = cretes & bord
    # quelques points isolés et une coupure, comme sur un vrai encrage
    for _ in range(40):
        cy, cx = rng.integers(0, hauteur), rng.integers(0, largeur)
        noir[max(cy - 1, 0):cy + 1, max(cx - 1, 0):cx + 1] = bord[cy, cx]
    img = np.where(noir, 0, 255).astype(np.uint8)
    Image.fromarray(img).save(chemin)
    return chemin


def lettres(chemin, texte="RAW", largeur=900, hauteur=300):
    """Pour vérifier le sens de lecture : un texte noir sur blanc."""
    from PIL import ImageDraw, ImageFont
    im = Image.new("L", (largeur, hauteur), 255)
    d = ImageDraw.Draw(im)
    try:
        fnt = ImageFont.truetype("DejaVuSans-Bold.ttf", int(hauteur * 0.8))
    except OSError:
        fnt = ImageFont.load_default()
    d.text((largeur * 0.05, hauteur * 0.05), texte, fill=0, font=fnt)
    im.save(chemin)
    return chemin
