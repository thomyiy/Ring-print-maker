"""Références pour test/geometrie.test.ts : ce que Python construit, pour que
la géométrie du navigateur (shared/alliance.ts) s'y compare sommet par sommet."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from moteur import alliance as A, empreinte as E, parametres  # noqa: E402

sortie = Path(sys.argv[1])
sortie.mkdir(parents=True, exist_ok=True)
racine = Path(__file__).resolve().parent.parent
image = racine / "exemples" / "demo" / "empreinte_demo.png"

cas = {
    "standard": {"n_sections": 360, "n_face": 20},
    "large_profond": {"n_sections": 360, "n_face": 20, "cote": 2.2, "hauteur_relief": 0.3, "taille": 62},
    "sens_inverse": {"n_sections": 240, "n_face": 12, "sens": -1, "arc_torsion_deg": 140, "adouci": 0.15},
    "sans_lissage": {"n_sections": 240, "n_face": 12, "lissage_sommet": 0},
}
out = {"sans_relief": {}, "avec_relief": {}}
for nom, brut in cas.items():
    p = parametres.normaliser(brut)
    m = A.construire(p, None)
    out["sans_relief"][nom] = {
        "params": {k: p[k] for k in ("diametre_interieur", "cote", "rayon_arete", "torsion_deg",
                                     "arc_torsion_deg", "adouci", "sens", "lissage_sommet", "hauteur_relief",
                                     "n_sections", "n_face", "n_coin")},
        "positions": m.V.ravel().tolist(),
        "volume": A.volume_signe(m.V, m.F),
    }

# Avec relief : la bande automatique, à l'échelle réelle.
p = parametres.normaliser({"n_sections": 720, "n_face": 30, "periode_mm": 0.45, "hauteur_relief": 0.25})
emp = E.preparer(str(image), p)
tex = E.texture_relief(emp, sortie / "relief.png")
img = np.asarray(Image.open(sortie / "relief.png"), dtype=np.uint8)
(sortie / "relief.raw").write_bytes(img.tobytes())
ed = E.image_edition(emp, sortie / "edition.png")
m = A.construire(p, emp)
ctrl = A.controler(p, m, complet=False)
out["avec_relief"] = {
    "params": {k: p[k] for k in ("diametre_interieur", "cote", "rayon_arete", "torsion_deg",
                                 "arc_torsion_deg", "adouci", "sens", "lissage_sommet", "hauteur_relief",
                                 "n_sections", "n_face", "n_coin")},
    "texture": tex,
    "hauteur_image": int(emp.gris.shape[0]),
    "periode_px": emp.periode_px,
    "mm_par_px": emp.mm_par_px,
    "largeur_utile": p["largeur_utile"],
    "bouts": ed["a"] + ed["b"],
    "longueur_mm": emp.bande.longueur_mm,
    "volume": ctrl["volume_mm3"],
    "arc_relief": ctrl["longueur_arc_relief_mm"],
    "positions": m.V.ravel().tolist(),
}
(sortie / "geometrie.json").write_text(json.dumps(out))

# — Chevalière : le relief en solide et le décodage des maillages ——————————
from moteur import chevaliere as C  # noqa: E402

cat = C.catalogue()
forme, taille = C.variante(cat, "ECU", 14)
plateau = C.contour_centre(taille, "plateau")
cup = C.contour_centre(taille, "cup")
hauteur = lambda u, v: 0.3 * (1 + np.sin(3 * u) * np.cos(2 * v)) / 2  # noqa: E731
chev = {"taille": taille}
for nom, (zone, emprise, base) in {
    "godet": (cup, C.retrecir(plateau, 0.3), -taille["cupDepth"]),
    "plein": (C.retrecir(plateau, C.MARGE_PLEIN), C.retrecir(plateau, C.MARGE_PLEIN), 0.0),
}.items():
    V, F, vol = C.relief_solide(zone, emprise, hauteur, base, 0.1)
    chev[nom] = {"base": base, "positions": V.ravel().tolist(), "indices": F.ravel().tolist(), "volume": vol}
data = C._telecharger("rings/ECU/14/creuse/190/creux.jrm")
(sortie / "ecu.jrm").write_bytes(data)
Vw, Fw = C.lire_jrm(data)
a, b, c = Vw[Fw[:, 0]], Vw[Fw[:, 1]], Vw[Fw[:, 2]]
chev["jrm_volume"] = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)
out["chevaliere"] = chev
(sortie / "geometrie.json").write_text(json.dumps(out))
