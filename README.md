# Alliance empreinte — outil de configuration

Alliance torsadée en fil carré, avec une empreinte digitale en relief sur la face qui passe
au sommet. Le moteur de géométrie est en Python (numpy + scipy) et le site est en Nuxt 4,
avec la DA de rainbowantworkshop.fr. Le STL part en résine calcinable, puis en fonte à cire
perdue.

## Les deux pages

- **`/`, la page client** : on ajoute la photo de son empreinte, on choisit le métal (argent 925,
  or jaune, rose ou gris 18 k) et les dimensions (taille de doigt, largeur du fil, relief). La
  bague se recalcule en 3D, avec son poids estimé.
- **`/atelier`, l'outil complet** : cadrage de la bande, traitement de l'image, forme du fil,
  maillage de fabrication, rendus de contrôle, masque et bande déroulée, et tous les contrôles.

## Lancer

```bash
pip install -r requirements.txt
npm install
npm run dev
```

Le moteur s'utilise aussi seul, en ligne de commande :

```bash
python3 -m moteur generer --image scan.png --params params.json --sortie sortie/
python3 -m moteur demo --sortie sortie/      # empreinte synthétique
python3 -m moteur schema                     # paramètres, défauts, bornes
```

`params.json` ne contient que ce qui change. Les défauts sont dans `moteur/parametres.py`.

## Ce que fait le moteur

| fichier | rôle |
|---|---|
| `moteur/empreinte.py` | niveaux de gris, ×6, léger flou, seuil doux, points isolés retirés ; période des crêtes (spectre) → échelle pour 6 à 8 crêtes sur 1,5 mm ; champ d'orientation → bande en biais où les crêtes filent en long, d'un bord à l'autre, centrée sur le sommet |
| `moteur/alliance.py` | carré rayonné, torsion de 180° à vitesse constante sur 170° (rampe en cosinus aux raccords), intérieur tangent au doigt, raccord par décalage de N/2 ; contrôles et STL binaire |
| `moteur/rendu.py` | rendus de contrôle en numpy (vue générale, dessus portée, gros plan) |
| `moteur/figures.py` | masque complet avec le cadre de la bande, bande déroulée et coupe |

Repère : l'axe du doigt est Z, le sommet est +Y. Les images sont lues « y vers le haut »,
de sorte que le repère de la bande est direct : l'empreinte se lit à l'endroit vue de
l'extérieur (vérifié avec un texte, voir l'option miroir sinon).

Contrôles à chaque génération : étanchéité (chaque arête partagée par deux triangles, et
orientation cohérente), normales sortantes, diamètre intérieur minimal égal à la cote,
écart au raccord.

## Déploiement

Railway, nixpacks : Node 22 pour Nuxt, et le venv Python du fournisseur nixpacks dans `/opt/venv`
(`NUXT_PYTHON`). Variables relues au démarrage :

- `NUXT_PYTHON` : l'interpréteur du moteur (défaut `python3`) ;
- `NUXT_DOSSIER_TRAVAIL` : où ranger les dépôts et les sorties (défaut : dossier
  temporaire). Les dépôts sont effacés au bout de six heures.

Un calcul à la fois : un maillage de fabrication (1440 × 224 points, 668 000 triangles,
33 Mo de STL) prend 10 à 15 s et environ 1 Go de mémoire.
