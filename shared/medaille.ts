/**
 * La médaille à empreinte, dans le navigateur : le corps depuis le contour du
 * catalogue (épaisseur, bord adouci, trou de bélière) et le relief sur la face.
 *
 * ⚠️ MÊMES RÉGLAGES QUE `moteur/medaille.py`, qui fait le fichier de
 * fabrication. Le corps y est arrondi par tranches (8 marches de 0,03 mm), ici
 * par le biseau de three.js : `npm test` vérifie que les volumes concordent.
 */
import { BufferGeometry, ExtrudeGeometry, Matrix4, Path, Shape, ShapeUtils, Vector2 } from 'three'
import { contourCentre, MARGE_PLEIN, retrecir, type Point } from './chevaliere.ts'

export const RAYON_BORD = 0.25
export const TROU_BELIERE = 1.5
export const MARGE_FACE = 0.3
export const MARGE_TROU = 0.4

export interface TailleMedaille {
  mm: number
  width: number
  height: number
  points: number[]
  bail?: [number, number] | null
  aireUtileMm2: number
  volumeMm3: { nu: number; serti: number }
}

export function contourMedaille(t: TailleMedaille): Point[] {
  return contourCentre({ ...t, cup: { points: [] }, cupDepth: 0, volumes: {} } as never, 'plateau')
}

/** (u, v, rayon) du trou : la bélière, ou l'évidement central du Cercle. */
export function trouMedaille(t: TailleMedaille, bail?: string): [number, number, number] | null {
  if (bail === 'center') return [0, 0, t.mm / 8]
  if (!t.bail) return null
  return [t.bail[0] - t.width / 2, t.bail[1] - t.height / 2, TROU_BELIERE / 2]
}

export function zoneMedaille(t: TailleMedaille): Point[] {
  return retrecir(contourMedaille(t), RAYON_BORD + MARGE_FACE)
}

/** Le corps, dans le repère commun : face gravée à y = 0, épaisseur vers −y. */
export function corpsMedaille(t: TailleMedaille, epaisseur: number, bail?: string): BufferGeometry {
  const r = Math.min(RAYON_BORD, epaisseur / 2 - 0.05)
  const pq = contourMedaille(t).map(([u, v]) => [-u, -v] as Point)
  const forme = new Shape()
  forme.moveTo(pq[0]![0], pq[0]![1])
  for (const [p, q] of pq.slice(1)) forme.lineTo(p, q)
  forme.closePath()
  const trou = trouMedaille(t, bail)
  if (trou) {
    // ⚠️ LE TROU TOURNE À L'INVERSE DU CONTOUR, ET C'EST À NOUS DE LE GARANTIR.
    // three.js ne retourne un trou que s'il retourne aussi le contour : sur le
    // rond, tracé dans l'autre sens, le trou de bélière AJOUTAIT du métal au
    // lieu d'en retirer (+1,6 mm³, attrapé par test/medaille.test.ts).
    const horaire = ShapeUtils.isClockWise(pq.map(([p, q]) => new Vector2(p, q)))
    const h = new Path()
    h.absarc(-trou[0], -trou[1], trou[2], 0, Math.PI * 2, !horaire)
    forme.holes.push(h)
  }
  const geo = new ExtrudeGeometry(forme, {
    depth: epaisseur - 2 * r, curveSegments: 48,
    bevelEnabled: true, bevelThickness: r, bevelSize: r, bevelOffset: -r, bevelSegments: 6,
  })
  // z ∈ [−r, T − r] → [0, T], puis (p, q, c) → (p, −c, q).
  geo.applyMatrix4(new Matrix4().makeTranslation(0, 0, r))
  geo.applyMatrix4(new Matrix4().set(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1))
  return geo
}

export function volumeGeometrie(geo: BufferGeometry): number {
  const p = geo.getAttribute('position').array as ArrayLike<number>
  const idx = geo.getIndex()?.array
  const n = idx ? idx.length : p.length / 3
  let v = 0
  for (let k = 0; k < n; k += 3) {
    const a = (idx ? idx[k]! : k) * 3, b = (idx ? idx[k + 1]! : k + 1) * 3, c = (idx ? idx[k + 2]! : k + 2) * 3
    v += p[a]! * (p[b + 1]! * p[c + 2]! - p[b + 2]! * p[c + 1]!) + p[a + 1]! * (p[b + 2]! * p[c]! - p[b]! * p[c + 2]!)
      + p[a + 2]! * (p[b]! * p[c + 1]! - p[b + 1]! * p[c]!)
  }
  return Math.abs(v / 6)
}

/** Pour l'affichage : la médaille debout, face vers la caméra, bélière en
 *  haut. Une rotation (pas un miroir) : l'empreinte reste à l'endroit. */
export function debout(positions: Float32Array): Float32Array {
  const out = new Float32Array(positions.length)
  for (let i = 0; i < positions.length; i += 3) {
    out[i] = -positions[i]!
    out[i + 1] = positions[i + 2]!
    out[i + 2] = positions[i + 1]!
  }
  return out
}

export { MARGE_PLEIN }
