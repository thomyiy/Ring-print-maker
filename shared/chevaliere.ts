/**
 * La chevalière à empreinte, dans le navigateur : lecture des maillages de la
 * bibliothèque, contours du plateau, et le relief de l'empreinte en solide.
 *
 * ⚠️ TRADUCTION LIGNE À LIGNE DE `moteur/chevaliere.py`. La page montre le
 * relief construit ici, l'atelier reçoit celui de Python : `npm test` compare
 * les deux sommet par sommet. Toute retouche se refait des deux côtés.
 *
 * Repère : dessus du plateau à y = 0, anneau vers −y, axe du doigt Z. Le
 * plateau se décrit en mm « SVG » centré (u à droite, v vers le bas) et se pose
 * en x = −u, z = −v : l'empreinte reste à l'endroit vue de dessus.
 */
import { lireRelief, type TextureRelief } from './alliance.ts'

export const EPAISSEUR_ANCRAGE = 0.2
export const MARGE_PLEIN = 0.4

// — Maillages JRM1 ——————————————————————————————————————————————————

export interface MaillageJrm {
  positions: Float32Array
  indices: Uint16Array | Uint32Array
}

/** En-tête (sommets, indices, drapeaux), boîte (min, taille), positions u16,
 *  4 octets par sommet, indices u16 ou u32.
 *
 *  ⚠️ LES 4 OCTETS PAR SOMMET NE SONT PAS DES NORMALES. Lus comme telles, ils
 *  donnaient des vecteurs de longueur 1,1 à 1,4 et l'anneau sortait couvert de
 *  reflets martelés (16/11/2026). On les saute ; la vue recalcule les normales
 *  depuis la géométrie, et les sommets dédoublés aux arêtes vives gardent
 *  celles-ci franches. */
export function lireJrm(buf: ArrayBuffer): MaillageJrm {
  const dv = new DataView(buf)
  if (dv.getUint32(0, true) !== 0x314d524a) throw new Error('Maillage illisible')
  const nv = dv.getUint32(4, true)
  const ni = dv.getUint32(8, true)
  const mn = [dv.getFloat32(16, true), dv.getFloat32(20, true), dv.getFloat32(24, true)]
  const sz = [dv.getFloat32(28, true), dv.getFloat32(32, true), dv.getFloat32(36, true)]
  const positions = new Float32Array(nv * 3)
  let o = 40
  for (let i = 0; i < nv * 3; i++) {
    positions[i] = mn[i % 3]! + (dv.getUint16(o, true) / 65535) * sz[i % 3]!
    o += 2
  }
  o += nv * 4
  const indices = nv < 65536 ? new Uint16Array(buf.slice(o, o + ni * 2)) : new Uint32Array(buf.slice(o, o + ni * 4))
  return { positions, indices }
}

// — Contours ————————————————————————————————————————————————————————

export type Point = [number, number]

export interface TaillePlateau {
  mm: number
  width: number
  height: number
  points: number[]
  cup: { points: number[] }
  cupDepth: number
  volumes: Record<string, Record<string, { lisse: number; email: number }>>
}

export function contourCentre(t: TaillePlateau, quoi: 'plateau' | 'cup' = 'plateau'): Point[] {
  const src = quoi === 'plateau' ? t.points : t.cup.points
  const out: Point[] = []
  for (let i = 0; i < src.length; i += 2) out.push([src[i]! - t.width / 2, src[i + 1]! - t.height / 2])
  return out
}

export function dansPolygone(x: number, y: number, poly: Point[]): boolean {
  let dedans = false
  let [xj, yj] = poly[poly.length - 1]!
  for (const [xi, yi] of poly) {
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / ((yj - yi) + 1e-300) + xi) dedans = !dedans
    xj = xi; yj = yi
  }
  return dedans
}

export function retrecir(poly: Point[], d: number): Point[] {
  const n = poly.length
  let cx = 0, cy = 0
  for (const [x, y] of poly) { cx += x; cy += y }
  cx /= n; cy /= n
  return poly.map((p, i) => {
    const a = poly[(i - 1 + n) % n]!, b = poly[(i + 1) % n]!
    const tx = b[0] - a[0], ty = b[1] - a[1]
    const l = Math.hypot(tx, ty) + 1e-12
    let nx = ty / l, ny = -tx / l
    if (nx * (cx - p[0]) + ny * (cy - p[1]) < 0) { nx = -nx; ny = -ny }
    return [p[0] + d * nx, p[1] + d * ny] as Point
  })
}

// — Le relief en solide ———————————————————————————————————————————————

export interface Solide { positions: Float32Array; indices: Uint32Array; volume: number }

/** Voir `relief_solide` dans moteur/chevaliere.py : même grille, même ordre
 *  des sommets et des triangles. */
export function reliefSolide(
  zone: Point[], emprise: Point[], hauteurDe: (u: number, v: number) => number,
  base: number, pas: number, trou: [number, number, number] | null = null,
): Solide {
  let umin = Infinity, vmin = Infinity, umax = -Infinity, vmax = -Infinity
  for (const [u, v] of emprise) {
    umin = Math.min(umin, u); vmin = Math.min(vmin, v); umax = Math.max(umax, u); vmax = Math.max(vmax, v)
  }
  umin -= pas; vmin -= pas; umax += pas; vmax += pas
  const nu = Math.ceil((umax - umin) / pas) + 1
  const nv = Math.ceil((vmax - vmin) / pas) + 1
  const U = (i: number) => umin + pas * i
  const V = (j: number) => vmin + pas * j
  const at = (i: number, j: number) => i * nv + j

  const dansEmprise = new Uint8Array(nu * nv)
  const H = new Float64Array(nu * nv)
  for (let i = 0; i < nu; i++) {
    for (let j = 0; j < nv; j++) {
      const u = U(i), v = V(j)
      // Le trou (bélière d'une médaille) reste libre : ni emprise ni crête.
      const hors = !trou || Math.hypot(u - trou[0], v - trou[1]) > trou[2]
      dansEmprise[at(i, j)] = hors && dansPolygone(u, v, emprise) ? 1 : 0
      if (hors && dansPolygone(u, v, zone)) H[at(i, j)] = hauteurDe(u, v)
    }
  }
  const nci = nu - 1, ncj = nv - 1
  const cel = new Uint8Array(nci * ncj)
  for (let i = 0; i < nci; i++) {
    for (let j = 0; j < ncj; j++) {
      cel[i * ncj + j] = dansEmprise[at(i, j)]! & dansEmprise[at(i + 1, j)]! & dansEmprise[at(i, j + 1)]! & dansEmprise[at(i + 1, j + 1)]!
    }
  }
  // Pas de cellules qui ne se touchent que par un coin.
  for (;;) {
    let change = false
    const ajout1: number[] = [], ajout2: number[] = []
    for (let i = 0; i < nci - 1; i++) {
      for (let j = 0; j < ncj - 1; j++) {
        const a = cel[i * ncj + j], b = cel[(i + 1) * ncj + j + 1]
        const c = cel[(i + 1) * ncj + j], d = cel[i * ncj + j + 1]
        if (a && b && !c && !d) ajout1.push((i + 1) * ncj + j)
        if (c && d && !a && !b) ajout2.push(i * ncj + j)
      }
    }
    for (const k of ajout1) { cel[k] = 1; change = true }
    for (const k of ajout2) { cel[k] = 1; change = true }
    if (!change) break
  }

  const num = new Int32Array(nu * nv).fill(-1)
  for (let i = 0; i < nci; i++) {
    for (let j = 0; j < ncj; j++) {
      if (!cel[i * ncj + j]) continue
      num[at(i, j)] = 0; num[at(i + 1, j)] = 0; num[at(i, j + 1)] = 0; num[at(i + 1, j + 1)] = 0
    }
  }
  let n = 0
  for (let k = 0; k < nu * nv; k++) if (num[k]! === 0) num[k] = n++
  const pos = new Float32Array(n * 6)
  for (let i = 0; i < nu; i++) {
    for (let j = 0; j < nv; j++) {
      const s = num[at(i, j)]!
      if (s < 0) continue
      const x = -U(i), z = -V(j)
      pos.set([x, base + H[at(i, j)]!, z], s * 3)
      pos.set([x, base - EPAISSEUR_ANCRAGE, z], (s + n) * 3)
    }
  }

  const cellules: [number, number][] = []
  for (let i = 0; i < nci; i++) for (let j = 0; j < ncj; j++) if (cel[i * ncj + j]) cellules.push([i, j])
  const tri: number[] = []
  const coins = cellules.map(([i, j]) => [num[at(i, j)]!, num[at(i + 1, j)]!, num[at(i + 1, j + 1)]!, num[at(i, j + 1)]!])
  for (const [a, b, c] of coins) tri.push(a!, b!, c!)
  for (const [a, , c, d] of coins) tri.push(a!, c!, d!)
  for (const [a, b, c] of coins) tri.push(a! + n, c! + n, b! + n)
  for (const [a, , c, d] of coins) tri.push(a! + n, d! + n, c! + n)
  const occupe = (i: number, j: number) => i >= 0 && j >= 0 && i < nci && j < ncj && cel[i * ncj + j] === 1
  const bords: [number, number, Point, Point][] = [
    [0, -1, [0, 0], [1, 0]], [1, 0, [1, 0], [1, 1]], [0, 1, [1, 1], [0, 1]], [-1, 0, [0, 1], [0, 0]],
  ]
  for (const [di, dj, p0, p1] of bords) {
    const s0s: number[] = [], s1s: number[] = []
    for (const [i, j] of cellules) {
      if (occupe(i + di, j + dj)) continue
      s0s.push(num[at(i + p0[0], j + p0[1])]!)
      s1s.push(num[at(i + p1[0], j + p1[1])]!)
    }
    for (let k = 0; k < s0s.length; k++) tri.push(s0s[k]!, s1s[k]! + n, s1s[k]!)
    for (let k = 0; k < s0s.length; k++) tri.push(s0s[k]!, s0s[k]! + n, s1s[k]! + n)
  }
  const idx = Uint32Array.from(tri)
  let vs = 0
  for (let k = 0; k < idx.length; k += 3) {
    const a = idx[k]! * 3, b = idx[k + 1]! * 3, c = idx[k + 2]! * 3
    vs += pos[a]! * (pos[b + 1]! * pos[c + 2]! - pos[b + 2]! * pos[c + 1]!)
      + pos[a + 1]! * (pos[b + 2]! * pos[c]! - pos[b]! * pos[c + 2]!)
      + pos[a + 2]! * (pos[b]! * pos[c + 1]! - pos[b + 1]! * pos[c]!)
  }
  if (vs < 0) for (let k = 0; k < idx.length; k += 3) { const t = idx[k + 1]!; idx[k + 1] = idx[k + 2]!; idx[k + 2] = t }
  let vol = 0
  for (const [i, j] of cellules) {
    vol += 0.25 * (H[at(i, j)]! + H[at(i + 1, j)]! + H[at(i, j + 1)]! + H[at(i + 1, j + 1)]!)
  }
  return { positions: pos, indices: idx, volume: vol * pas * pas }
}

// — Placement de l'empreinte ————————————————————————————————————————

/** [cx, cy, angle°] en pixels de l'image d'édition (y vers le bas), comme
 *  l'éditeur les pose. Rend (u, v) du plateau → relief 0..1. */
export function lecteurRelief(
  placement: [number, number, number], mmParPx: number, hauteurImage: number, tx: TextureRelief,
) {
  const [cx, cy, ang] = placement
  const a = (ang * Math.PI) / 180
  const ca = Math.cos(a), sa = Math.sin(a)
  return (u: number, v: number) => {
    const x = cx + (ca * u - sa * v) / mmParPx
    const yBas = cy + (sa * u + ca * v) / mmParPx
    return lireRelief(tx, x, hauteurImage - 1 - yBas)
  }
}

export const RETRAIT_GODET = 0.1

/** Voir `socle_godet` dans moteur/chevaliere.py : le fond du godet remonte,
 *  et les crêtes s'arrêtent RETRAIT_GODET sous le bord. */
export function socleGodet(t: TaillePlateau, hauteur: number): number {
  return Math.max(0, t.cupDepth - hauteur - RETRAIT_GODET)
}

export interface ReliefChevaliere {
  solide: Solide
  base: number
  hauteur: number
}

/** Le relief tel que `construire` le pose en Python, au pas d'affichage. */
export function reliefChevaliere(
  taille: TaillePlateau, surface: 'godet' | 'plein', hauteurPlein: number,
  lire: (u: number, v: number) => number, pas: number,
): ReliefChevaliere {
  const plateau = contourCentre(taille, 'plateau')
  const hauteur = hauteurPlein
  let zone: Point[], emprise: Point[], base: number, socle: number
  if (surface === 'godet') {
    zone = contourCentre(taille, 'cup')
    emprise = retrecir(plateau, 0.3)
    base = -taille.cupDepth
    socle = socleGodet(taille, hauteur)
  } else {
    zone = retrecir(plateau, MARGE_PLEIN)
    emprise = zone
    base = 0
    socle = 0
  }
  const solide = reliefSolide(zone, emprise, (u, v) => socle + hauteur * lire(u, v), base, pas)
  return { solide, base, hauteur }
}
