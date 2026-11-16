/**
 * La géométrie de l'alliance, dans le navigateur.
 *
 * ⚠️ C'EST UNE TRADUCTION LIGNE À LIGNE DE `moteur/alliance.py`, ET ELLE DOIT
 * LE RESTER. La page client montre la bague construite ici ; l'atelier reçoit
 * le STL construit par Python. Si les deux divergent, le client commande une
 * bague qu'il n'a pas vue. `test/geometrie.test.ts` compare les deux sommet
 * par sommet : toute retouche d'un côté se refait de l'autre, et le test le dit.
 *
 * Repère : axe du doigt Z, sommet +Y, φ = 0 au sommet, raccord à φ = ±π.
 * Profil (u, v) : u le long de Z, v vers l'extérieur.
 */

export interface ParamsAlliance {
  diametre_interieur: number
  cote: number
  rayon_arete: number
  torsion_deg: number
  arc_torsion_deg: number
  adouci: number
  sens: number
  lissage_sommet: number
  hauteur_relief: number
  n_sections: number
  n_face: number
  n_coin: number
}

export const DEFAUTS: ParamsAlliance = {
  diametre_interieur: 17.2,
  cote: 1.8,
  rayon_arete: 0.15,
  torsion_deg: 180,
  arc_torsion_deg: 170,
  adouci: 0.08,
  sens: 1,
  lissage_sommet: 0.08,
  hauteur_relief: 0.18,
  n_sections: 1080,
  n_face: 40,
  n_coin: 8,
}

/** La texture de relief rendue par `moteur preparer` (voir `texture_relief`). */
export interface TextureRelief {
  donnees: Uint8Array | Uint8ClampedArray // luminance 0..255, ligne 0 en haut
  pas: number // octets par pixel dans `donnees` (4 pour un RGBA de canvas)
  largeur: number
  hauteur: number
  x0: number
  y0: number
  facteur: number
}

/** La bande, en pixels de l'image d'origine, y vers le HAUT. */
export interface Bande {
  centre: [number, number]
  e: [number, number]
  n: [number, number]
  longueurMm: number
  mmParPx: number
}

// — Profil ———————————————————————————————————————————————————————

export interface Profil {
  u: Float64Array
  v: Float64Array
  nu: Float64Array
  nv: Float64Array
  face: Int8Array
  t: Float64Array
}

export function profilCarre(a: number, r: number, nFace: number, nCoin: number): Profil {
  const b = a / 2 - r
  const N = 4 * (nFace + nCoin)
  const P: Profil = {
    u: new Float64Array(N), v: new Float64Array(N), nu: new Float64Array(N),
    nv: new Float64Array(N), face: new Int8Array(N), t: new Float64Array(N),
  }
  let i = 0
  for (let k = 0; k < 4; k++) {
    const psi = Math.PI + (k * Math.PI) / 2
    const nk = [Math.cos(psi), Math.sin(psi)] as const
    const tau = [-nk[1], nk[0]] as const
    for (let q = 0; q < nFace; q++) {
      const tt = nFace === 1 ? -b : -b + (2 * b * q) / (nFace - 1)
      P.u[i] = nk[0] * (a / 2) + tau[0] * tt
      P.v[i] = nk[1] * (a / 2) + tau[1] * tt
      P.nu[i] = nk[0]; P.nv[i] = nk[1]; P.face[i] = k; P.t[i] = tt
      i++
    }
    const n2 = [Math.cos(psi + Math.PI / 2), Math.sin(psi + Math.PI / 2)] as const
    const c = [(nk[0] + n2[0]) * b, (nk[1] + n2[1]) * b] as const
    for (let q = 1; q <= nCoin; q++) {
      const ang = psi + ((Math.PI / 2) * q) / (nCoin + 1)
      const d = [Math.cos(ang), Math.sin(ang)] as const
      P.u[i] = c[0] + r * d[0]; P.v[i] = c[1] + r * d[1]
      P.nu[i] = d[0]; P.nv[i] = d[1]; P.face[i] = -1; P.t[i] = 0
      i++
    }
  }
  return P
}

// — Torsion ——————————————————————————————————————————————————————

export function loiTorsion(phi: number, p: ParamsAlliance): number {
  const A = ((p.arc_torsion_deg * Math.PI) / 180) / 2
  const T = (p.torsion_deg * Math.PI) / 180
  const e = p.adouci
  const x = Math.min(1, Math.max(0, (phi + A) / (2 * A)))
  if (e <= 0) return T * x
  const R = (x: number) => (x < e ? 0.5 * (x - (e / Math.PI) * Math.sin((Math.PI * x) / e)) : e / 2 + (x - e))
  const r = x <= 0.5 ? R(x) : (1 - e) - R(1 - x)
  return (T * r) / (1 - e)
}

/** |x|, arrondi en parabole sous d : jamais en dessous de |x|, raccord C1. */
function absLisse(x: number, d: number): number {
  const ax = Math.abs(x)
  return d <= 0 || ax >= d ? ax : 0.5 * ((x * x) / d + d)
}

/** Voir `rayon_centre` dans moteur/alliance.py : le pli au sommet venait de
 *  l'angle vif de |cos α| à 90°, arrondi ici sous `lissage`. */
export function rayonCentre(alpha: number, a: number, r: number, lissage: number): number {
  const b = a / 2 - r
  return b * (absLisse(Math.cos(alpha), lissage) + Math.abs(Math.sin(alpha))) + r
}

export function demiHauteur(alpha: number, a: number, r: number): number {
  const b = a / 2 - r
  return b * (Math.abs(Math.cos(alpha)) + Math.abs(Math.sin(alpha))) + r
}

// — Relief ———————————————————————————————————————————————————————

/** Relief 0..1 en un point de l'image d'origine (x, y vers le haut). Bilinéaire,
 *  zéro hors de la texture, comme `map_coordinates(order=1, cval=0)`. */
export function lireRelief(tx: TextureRelief, x: number, y: number): number {
  const c = (x - tx.x0 + 0.5) * tx.facteur - 0.5
  const lh = (y - tx.y0 + 0.5) * tx.facteur - 0.5
  const l = tx.hauteur - 1 - lh
  if (c < 0 || l < 0 || c > tx.largeur - 1 || l > tx.hauteur - 1) return 0
  const c0 = Math.floor(c), l0 = Math.floor(l)
  const c1 = Math.min(c0 + 1, tx.largeur - 1), l1 = Math.min(l0 + 1, tx.hauteur - 1)
  const fc = c - c0, fl = l - l0
  const d = tx.donnees, s = tx.pas, W = tx.largeur
  const v00 = d[(l0 * W + c0) * s]!, v01 = d[(l0 * W + c1) * s]!
  const v10 = d[(l1 * W + c0) * s]!, v11 = d[(l1 * W + c1) * s]!
  return ((v00 * (1 - fc) + v01 * fc) * (1 - fl) + (v10 * (1 - fc) + v11 * fc) * fl) / 255
}

/**
 * La bande à partir de ses deux bouts posés dans l'éditeur (pixels, y vers le
 * BAS, comme `bande_px`). En bord à bord, la longueur va de la première à la
 * dernière crête rencontrée sur toute la largeur, plus une demi-période, et le
 * milieu se recentre — le même geste que `borner_bande` côté Python.
 */
export function placerBande(
  ab: [number, number, number, number], hauteurImage: number, bordABord: boolean,
  largeurMm: number, mmParPx: number, periodePx: number, tx: TextureRelief,
): Bande {
  const A: [number, number] = [ab[0], hauteurImage - 1 - ab[1]]
  const B: [number, number] = [ab[2], hauteurImage - 1 - ab[3]]
  const dx = B[0] - A[0], dy = B[1] - A[1]
  const L = Math.hypot(dx, dy) || 1
  const e: [number, number] = [dx / L, dy / L]
  const n: [number, number] = [-e[1], e[0]]
  let centre: [number, number] = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2]
  let longueurMm = L * mmParPx
  if (bordABord) {
    // On sonde la droite sur toute l'étendue de la texture.
    const x1 = tx.x0 - 0.5, x2 = x1 + tx.largeur / tx.facteur
    const y1 = tx.y0 - 0.5, y2 = y1 + tx.hauteur / tx.facteur
    let lmin = Infinity, lmax = -Infinity
    for (const [x, y] of [[x1, y1], [x2, y1], [x1, y2], [x2, y2]] as const) {
      const l = (x - centre[0]) * e[0] + (y - centre[1]) * e[1]
      lmin = Math.min(lmin, l); lmax = Math.max(lmax, l)
    }
    const pas = 1 / tx.facteur
    const demiW = largeurMm / mmParPx / 2
    let premier = Infinity, dernier = -Infinity
    for (let l = lmin; l <= lmax; l += pas) {
      for (let q = 0; q < 25; q++) {
        const w = -demiW + (2 * demiW * q) / 24
        if (lireRelief(tx, centre[0] + l * e[0] + w * n[0], centre[1] + l * e[1] + w * n[1]) > 0.05) {
          if (l < premier) premier = l
          dernier = l
          break
        }
      }
    }
    if (premier <= dernier) {
      premier -= periodePx / 2
      dernier += periodePx / 2
      const lc = (premier + dernier) / 2
      centre = [centre[0] + lc * e[0], centre[1] + lc * e[1]]
      longueurMm = (dernier - premier) * mmParPx
    }
  }
  return { centre, e, n, longueurMm, mmParPx }
}

/** Les deux bouts d'une bande, en pixels y vers le BAS (pour l'éditeur). */
export function boutsBande(b: Bande, hauteurImage: number): [number, number, number, number] {
  const demi = b.longueurMm / b.mmParPx / 2
  const A = [b.centre[0] - demi * b.e[0], b.centre[1] - demi * b.e[1]]
  const B = [b.centre[0] + demi * b.e[0], b.centre[1] + demi * b.e[1]]
  return [A[0]!, hauteurImage - 1 - A[1]!, B[0]!, hauteurImage - 1 - B[1]!]
}

// — Maillage —————————————————————————————————————————————————————

export interface Alliance {
  positions: Float32Array
  M: number
  N: number
  inverse: boolean
  volumeMm3: number
  diametreIntMin: number
  diametreExtMax: number
  largeurMax: number
  arcReliefMm: number
}

function sections(p: ParamsAlliance, P: Profil, k0: number, H: Float64Array | null, nF: number) {
  const M = p.n_sections, N = P.u.length
  const a = p.cote, r = p.rayon_arete, Rin = p.diametre_interieur / 2, sig = p.sens
  const V = new Float64Array(M * N * 3)
  const alpha = new Float64Array(M)
  for (let j = 0; j < M; j++) {
    const phi = -Math.PI + (2 * Math.PI * j) / M
    const al = loiTorsion(phi, p)
    alpha[j] = al
    const Rc = Rin + rayonCentre(al, a, r, p.lissage_sommet)
    const c = Math.cos(sig * al), s = Math.sin(sig * al)
    const sp = Math.sin(phi), cp = Math.cos(phi)
    let q = 0
    for (let i = 0; i < N; i++) {
      let u = P.u[i]!, v = P.v[i]!
      if (H && P.face[i] === k0) {
        const h = H[j * nF + q]!
        u += h * P.nu[i]!; v += h * P.nv[i]!
        q++
      }
      const uu = u * c + v * s
      const vv = -u * s + v * c
      const rad = Rc + vv
      const o = (j * N + i) * 3
      V[o] = rad * sp; V[o + 1] = rad * cp; V[o + 2] = uu
    }
  }
  return { V, alpha }
}

export function trianguler(M: number, N: number, inverse: boolean): Uint32Array {
  const idx = new Uint32Array(M * N * 6)
  let k = 0
  for (let j = 0; j < M; j++) {
    const jn = (j + 1) % M
    const dec = j === M - 1 ? N / 2 : 0
    for (let i = 0; i < N; i++) {
      const a = j * N + i
      const b = j * N + ((i + 1) % N)
      const c = jn * N + ((i + 1 + dec) % N)
      const d = jn * N + ((i + dec) % N)
      if (inverse) { idx[k++] = a; idx[k++] = c; idx[k++] = b; idx[k++] = a; idx[k++] = d; idx[k++] = c }
      else { idx[k++] = a; idx[k++] = b; idx[k++] = c; idx[k++] = a; idx[k++] = c; idx[k++] = d }
    }
  }
  return idx
}

function volume(V: Float64Array, F: Uint32Array): number {
  let s = 0
  for (let k = 0; k < F.length; k += 3) {
    const a = F[k]! * 3, b = F[k + 1]! * 3, c = F[k + 2]! * 3
    const ax = V[a]!, ay = V[a + 1]!, az = V[a + 2]!
    const bx = V[b]!, by = V[b + 1]!, bz = V[b + 2]!
    const cx = V[c]!, cy = V[c + 1]!, cz = V[c + 2]!
    s += ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)
  }
  return s / 6
}

export function construire(
  pBrut: Partial<ParamsAlliance>,
  relief?: { bande: Bande; texture: TextureRelief } | null,
): Alliance {
  const p: ParamsAlliance = { ...DEFAUTS, ...pBrut }
  p.n_sections += p.n_sections % 2
  p.rayon_arete = Math.min(p.rayon_arete, p.cote / 2 - 0.05)
  p.sens = p.sens >= 0 ? 1 : -1
  const P = profilCarre(p.cote, p.rayon_arete, p.n_face, p.n_coin)
  const M = p.n_sections, N = P.u.length
  const k0 = p.sens > 0 ? 0 : 2
  const idx: number[] = []
  for (let i = 0; i < N; i++) if (P.face[i] === k0) idx.push(i)
  const nF = idx.length
  const i0 = idx[0]!, i1 = idx[nF - 1]!

  const { V: V0, alpha } = sections(p, P, k0, null, nF)
  // Abscisse curviligne du milieu de la face texturée, 0 au sommet.
  const s = new Float64Array(M)
  const cx = (j: number, d: number) => 0.5 * (V0[(j * N + i0) * 3 + d]! + V0[(j * N + i1) * 3 + d]!)
  for (let j = 1; j < M; j++) {
    s[j] = s[j - 1]! + Math.hypot(cx(j, 0) - cx(j - 1, 0), cx(j, 1) - cx(j - 1, 1), cx(j, 2) - cx(j - 1, 2))
  }
  const s0 = s[M / 2]!
  for (let j = 0; j < M; j++) s[j] = s[j]! - s0

  // Sens de lecture au sommet : (L × W)·n > 0 vu de l'extérieur.
  const j = M / 2
  const dPds = [0, 1, 2].map((d) => cx(j + 1, d) - cx(j - 1, d))
  const dPdt = [0, 1, 2].map((d) => V0[(j * N + i1) * 3 + d]! - V0[(j * N + i0) * 3 + d]!)
  const al = alpha[j]!, phi = 0
  const c = Math.cos(p.sens * al), sn = Math.sin(p.sens * al)
  const nu = P.nu[i0]! * c + P.nv[i0]! * sn
  const nv = -P.nu[i0]! * sn + P.nv[i0]! * c
  const nOut = [nv * Math.sin(phi), nv * Math.cos(phi), nu]
  const cr = [
    dPds[1]! * dPdt[2]! - dPds[2]! * dPdt[1]!,
    dPds[2]! * dPdt[0]! - dPds[0]! * dPdt[2]!,
    dPds[0]! * dPdt[1]! - dPds[1]! * dPdt[0]!,
  ]
  const signeW = Math.sign(cr[0]! * nOut[0]! + cr[1]! * nOut[1]! + cr[2]! * nOut[2]!)

  const H = new Float64Array(M * nF)
  let sMin = Infinity, sMax = -Infinity
  if (relief) {
    const { bande: b, texture: tx } = relief
    const demi = b.longueurMm / 2
    const k = 1 / b.mmParPx
    for (let jj = 0; jj < M; jj++) {
      const L = s[jj]!
      if (Math.abs(L) > demi) continue
      let maxi = 0
      for (let q = 0; q < nF; q++) {
        const W = signeW * P.t[idx[q]!]!
        const x = b.centre[0] + (L * b.e[0] + W * b.n[0]) * k
        const y = b.centre[1] + (L * b.e[1] + W * b.n[1]) * k
        const h = p.hauteur_relief * lireRelief(tx, x, y)
        H[jj * nF + q] = h
        if (h > maxi) maxi = h
      }
      if (maxi > 0.02 * p.hauteur_relief) { sMin = Math.min(sMin, L); sMax = Math.max(sMax, L) }
    }
  }
  const { V } = sections(p, P, k0, relief ? H : null, nF)
  let F = trianguler(M, N, false)
  let vol = volume(V, F)
  const inverse = vol < 0
  if (inverse) { F = trianguler(M, N, true); vol = -vol }

  let rMin = Infinity, rMax = 0
  for (let o = 0; o < V.length; o += 3) {
    const rr = Math.hypot(V[o]!, V[o + 1]!)
    if (rr < rMin) rMin = rr
    if (rr > rMax) rMax = rr
  }
  let largeurMax = 0
  for (let jj = 0; jj < M; jj++) largeurMax = Math.max(largeurMax, 2 * demiHauteur(alpha[jj]!, p.cote, p.rayon_arete))

  return {
    positions: Float32Array.from(V),
    M, N, inverse,
    volumeMm3: vol,
    diametreIntMin: 2 * rMin,
    diametreExtMax: 2 * rMax,
    largeurMax,
    arcReliefMm: sMax >= sMin ? sMax - sMin : 0,
  }
}
