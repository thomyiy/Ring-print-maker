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
from . import parametres, synthetique

# figures et rendu tirent matplotlib (0,7 s de chargement) : importés seulement
# quand on s'en sert, jamais pour l'aperçu de la page client.


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
    from . import figures
    emp = E.preparer(image, p)
    edition = E.image_edition(emp, sortie / "edition.png")
    figures.figure_masque(emp, sortie / "masque.png")
    figures.figure_bande(emp, p, sortie / "bande.png")
    return emp, {"bande": _bande_json(emp, p), "avertissements": emp.avertissements,
                 "edition": edition,
                 "images": {"masque": "masque.png", "bande": "bande.png", "edition": "edition.png"}}


def preparer(image, p, sortie: Path):
    """Pour la page client, qui construit la bague dans le navigateur : tout
    ce qui demande scipy, une seule fois par empreinte. L'image d'édition, la
    texture de relief, la période des crêtes et la bande automatique."""
    emp = E.preparer(image, p)
    edition = E.image_edition(emp, sortie / "edition.png")
    texture = E.texture_relief(emp, sortie / "relief.png")
    return {
        "bande": _bande_json(emp, p),
        "avertissements": emp.avertissements,
        "edition": edition,
        "texture": texture,
        "periode_px": emp.periode_px,
        "hauteur_image": int(emp.gris.shape[0]),
        # Le milieu de l'empreinte, en pixels d'édition (y vers le bas) : là
        # où la chevalière pose son plateau au départ.
        # Le cadre de l'empreinte, en pixels d'édition (x0, y0, x1, y1, y vers
        # le bas) : l'éditeur de gravure le montre en pointillé et s'en sert
        # pour « dans le plateau » et « plateau dans l'image ».
        "boite_empreinte": [float(np.nonzero(emp.support)[1].min()),
                            float(emp.gris.shape[0] - 1 - np.nonzero(emp.support)[0].max()),
                            float(np.nonzero(emp.support)[1].max()),
                            float(emp.gris.shape[0] - 1 - np.nonzero(emp.support)[0].min())],
        "centre_empreinte": [float(np.nonzero(emp.support)[1].mean()),
                             float(emp.gris.shape[0] - 1 - np.nonzero(emp.support)[0].mean())],
        "images": {"edition": "edition.png", "relief": "relief.png"},
    }


def chevaliere(image, p, brut, sortie: Path):
    """La chevalière de l'atelier : maillage de la bibliothèque + relief de
    l'empreinte, unis en un seul solide fermé."""
    from . import chevaliere as C
    import trimesh
    emp = E.preparer(image, p)
    q = {
        "forme": str(brut.get("forme", "RON")),
        "plateau": int(brut.get("plateau", 14)),
        "remplissage": "pleine" if brut.get("remplissage") == "pleine" else "creuse",
        "doigt": int(brut.get("doigt", 54)),
        "surface": "plein" if brut.get("surface") == "plein" else "godet",
        "hauteur_relief": float(p["hauteur_relief"]),
        "periode_mm": float(brut.get("periode_mm", 0.45)),
        "placement_px": [float(x) for x in brut.get("placement_px") or [0, 0, 0]],
    }
    if not brut.get("placement_px"):
        H, W = emp.gris.shape
        ys, xs = np.nonzero(emp.support)
        q["placement_px"] = [float(xs.mean()), float(H - 1 - ys.mean()), 0.0]
    r = C.construire(q, emp)
    A.ecrire_stl(sortie / "chevaliere.stl", r["V"], r["F"])
    m = trimesh.Trimesh(r["V"], r["F"], process=False)
    ctrl = {
        "etanche": bool(m.is_watertight),
        "orientation_coherente": bool(m.is_winding_consistent),
        "statut_union": r["statut"],
        "volume_mm3": r["volume_mm3"],
        "volume_base_mm3": r["volume_base_mm3"],
        "volume_relief_mm3": r["volume_relief_mm3"],
        "poids_or_750_g": r["volume_mm3"] / 1000 * p["densite_or"],
        "poids_argent_925_g": r["volume_mm3"] / 1000 * p["densite_argent"],
        "triangles": int(len(r["F"])),
    }
    out = {"stl": "chevaliere.stl", "controles": ctrl, "choix": q, "forme": r["forme"],
           "avertissements": emp.avertissements, "images": {}}
    if not brut.get("sans_rendu"):
        from . import rendu
        Vc = r["V"]
        rendu.rendre(Vc, r["F"], direction=(0.55, 0.8, 0.9), haut=(0, 1, 0), largeur_px=1200).save(sortie / "rendu_general.png")
        rendu.rendre(Vc, r["F"], direction=(0, 1, 0), haut=(0, 0, 1), largeur_px=1200,
                     centre=(0, 0, 0), champ=q["plateau"] * 1.6).save(sortie / "rendu_dessus.png")
        out["images"] = {"general": "rendu_general.png", "dessus": "rendu_dessus.png"}
    if not ctrl["etanche"]:
        out["avertissements"].append("Maillage non étanche.")
    return out


def generer(image, p, sortie: Path, leger=False):
    """`leger` : l'aperçu de la page client. Ni figures, ni rendus, ni STL :
    une grille de sommets en float32 (`apercu.bin`), huit fois plus légère, que
    le navigateur triangule lui-même — et seulement les contrôles rapides."""
    t0 = time.time()
    if leger and image:
        emp = E.preparer(image, p)
        edition = E.image_edition(emp, sortie / "edition.png")
        res = {"bande": _bande_json(emp, p), "avertissements": emp.avertissements,
               "edition": edition, "images": {"edition": "edition.png"}}
    else:
        emp, res = analyser(image, p, sortie) if image else (None, {"avertissements": [], "images": {}})
    m = A.construire(p, emp)
    ctrl = A.controler(p, m, complet=not leger)
    if leger:
        A.ecrire_grille(sortie / "apercu.bin", m)
        res["apercu"] = "apercu.bin"
    else:
        from . import rendu
        A.ecrire_stl(sortie / "alliance.stl", m.V, m.F)
        res["images"].update(rendu.rendus_controle(m, p, sortie))
        res["stl"] = "alliance.stl"
    res["controles"] = ctrl
    res["parametres"] = {k: v for k, v in p.items()}
    res["duree_s"] = time.time() - t0
    av = res["avertissements"]
    if leger:
        return res
    if not ctrl["etanche"]:
        av.append("Maillage non étanche.")
    if ctrl["normales_sortantes"] < 0.999:
        av.append(f"Normales sortantes : {100 * ctrl['normales_sortantes']:.2f} % seulement.")
    if ctrl["diametre_interieur_min"] < p["diametre_interieur"] - 1e-3:
        av.append("Le diamètre intérieur passe sous la cote.")
    if ctrl["ecart_raccord"] > 1e-4:
        av.append(f"Écart au raccord : {ctrl['ecart_raccord']:.2e} mm.")
    return res


def _arguments():
    ap = argparse.ArgumentParser(prog="moteur")
    ap.add_argument("action", choices=["schema", "analyser", "preparer", "generer", "chevaliere", "demo", "synthetique", "serveur"])
    ap.add_argument("--image")
    ap.add_argument("--params")
    ap.add_argument("--sortie", default="sortie")
    ap.add_argument("--leger", action="store_true", help="aperçu : grille et chiffres seulement")
    return ap


def executer(argv) -> dict:
    a = _arguments().parse_args(argv)
    if a.action == "synthetique":
        return {"image": str(synthetique.empreinte_synthetique(a.sortie))}
    if a.action == "schema":
        return {k: dict(zip(("defaut", "min", "max", "pas", "unite", "libelle", "groupe"), v))
                for k, v in parametres.TABLE.items()}
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    brut = json.loads(Path(a.params).read_text()) if a.params else {}
    p = parametres.normaliser(brut)
    image = a.image
    if a.action == "demo":
        image = str(synthetique.empreinte_synthetique(sortie / "empreinte_demo.png"))
    if not image and a.action in ("analyser", "preparer"):
        raise ValueError("Une image d'empreinte est nécessaire.")
    if a.action == "analyser":
        out = analyser(image, p, sortie)[1]
    elif a.action == "preparer":
        out = preparer(image, p, sortie)
    elif a.action == "chevaliere":
        out = chevaliere(image, p, brut, sortie)
    else:
        out = generer(image, p, sortie, a.leger)
    (sortie / "resultat.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


MARQUE = "§§"


def serveur():
    """Le moteur reste chargé : une demande par ligne (la liste d'arguments en
    JSON), une réponse par ligne préfixée de `§§`. Le site garde ce processus
    vivant ; il évite 1,4 s d'imports par calcul et garde le cache d'empreintes.

    ⚠️ La sortie standard est le canal du protocole : tout `print` d'une
    bibliothèque y casserait une réponse. Pendant un calcul, elle est donc
    détournée vers la sortie d'erreur, et seules nos lignes marquées passent."""
    canal = sys.stdout
    sys.stdout = sys.stderr
    for ligne in sys.stdin:
        if not ligne.strip():
            continue
        try:
            rep = {"ok": True, **executer(json.loads(ligne))}
        except SystemExit as exc:
            rep = {"ok": False, "erreur": f"arguments invalides ({exc})"}
        except Exception as exc:
            rep = {"ok": False, "erreur": str(exc), "trace": traceback.format_exc()}
        canal.write(MARQUE + json.dumps(rep, ensure_ascii=False) + "\n")
        canal.flush()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["serveur"]:
        return serveur()
    try:
        out = executer(argv)
        json.dump({"ok": True, **out}, sys.stdout, ensure_ascii=False)
    except Exception as exc:  # le site affiche le message tel quel
        json.dump({"ok": False, "erreur": str(exc), "trace": traceback.format_exc()},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
