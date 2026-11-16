"""Ligne de commande. Le site l'appelle telle quelle ; elle écrit ses fichiers
dans le dossier de sortie et un seul objet JSON sur la sortie standard.

    python -m moteur schema
    python -m moteur analyser --image scan.png --params p.json --sortie dossier
    python -m moteur generer  --image scan.png --params p.json --sortie dossier
    python -m moteur demo     --sortie dossier
    python -m moteur synthetique --sortie empreinte.png
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from . import alliance as A
from . import empreinte as E
from . import figures, parametres, rendu, synthetique


def _bande_json(emp: E.Empreinte, p):
    b = emp.bande
    return {
        "angle_deg": float(np.degrees(b.angle)),
        "decalage_mm": b.decalage_px * emp.mm_par_px,
        "auto": b.auto,
        "longueur_mm": b.longueur_mm,
        "largeur_mm": p["largeur_utile"],
        "alignement": b.alignement,
        "periode_px": emp.periode_px,
        "periode_mm": emp.periode_px * emp.mm_par_px,
        "mm_par_px": emp.mm_par_px,
        "agrandissement": emp.facteur,
        "cretes_largeur": p["largeur_utile"] / (emp.periode_px * emp.mm_par_px),
    }


def analyser(image, p, sortie: Path):
    emp = E.preparer(image, p)
    edition = E.image_edition(emp, sortie / "edition.png")
    figures.figure_masque(emp, sortie / "masque.png")
    figures.figure_bande(emp, p, sortie / "bande.png")
    return emp, {"bande": _bande_json(emp, p), "avertissements": emp.avertissements,
                 "edition": edition,
                 "images": {"masque": "masque.png", "bande": "bande.png", "edition": "edition.png"}}


def generer(image, p, sortie: Path, leger=False):
    """`leger` : ni figures ni rendus, seulement le STL et les chiffres — c'est
    ce que la page client attend, et ça divise le temps par deux."""
    t0 = time.time()
    if leger and image:
        emp = E.preparer(image, p)
        edition = E.image_edition(emp, sortie / "edition.png")
        res = {"bande": _bande_json(emp, p), "avertissements": emp.avertissements,
               "edition": edition, "images": {"edition": "edition.png"}}
    else:
        emp, res = analyser(image, p, sortie) if image else (None, {"avertissements": [], "images": {}})
    m = A.construire(p, emp)
    ctrl = A.controler(p, m)
    A.ecrire_stl(sortie / "alliance.stl", m.V, m.F)
    if not leger:
        res["images"].update(rendu.rendus_controle(m, p, sortie))
    res["controles"] = ctrl
    res["stl"] = "alliance.stl"
    res["parametres"] = {k: v for k, v in p.items()}
    res["duree_s"] = time.time() - t0
    av = res["avertissements"]
    if not ctrl["etanche"]:
        av.append("Maillage non étanche.")
    if ctrl["normales_sortantes"] < 0.999:
        av.append(f"Normales sortantes : {100 * ctrl['normales_sortantes']:.2f} % seulement.")
    if ctrl["diametre_interieur_min"] < p["diametre_interieur"] - 1e-3:
        av.append("Le diamètre intérieur passe sous la cote.")
    if ctrl["ecart_raccord"] > 1e-4:
        av.append(f"Écart au raccord : {ctrl['ecart_raccord']:.2e} mm.")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(prog="moteur")
    ap.add_argument("action", choices=["schema", "analyser", "generer", "demo", "synthetique"])
    ap.add_argument("--image")
    ap.add_argument("--params")
    ap.add_argument("--sortie", default="sortie")
    ap.add_argument("--leger", action="store_true", help="STL et chiffres seulement")
    a = ap.parse_args(argv)
    try:
        if a.action == "synthetique":
            out = {"image": str(synthetique.empreinte_synthetique(a.sortie))}
        elif a.action == "schema":
            out = {k: dict(zip(("defaut", "min", "max", "pas", "unite", "libelle", "groupe"), v))
                   for k, v in parametres.TABLE.items()}
        else:
            sortie = Path(a.sortie)
            sortie.mkdir(parents=True, exist_ok=True)
            brut = json.loads(Path(a.params).read_text()) if a.params else {}
            p = parametres.normaliser(brut)
            image = a.image
            if a.action == "demo":
                image = str(synthetique.empreinte_synthetique(sortie / "empreinte_demo.png"))
            if not image and a.action == "analyser":
                raise ValueError("Une image d'empreinte est nécessaire.")
            out = analyser(image, p, sortie)[1] if a.action == "analyser" else generer(image, p, sortie, a.leger)
            (sortie / "resultat.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        json.dump({"ok": True, **out}, sys.stdout, ensure_ascii=False)
    except Exception as exc:  # le site affiche le message tel quel
        json.dump({"ok": False, "erreur": str(exc), "trace": traceback.format_exc()},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
