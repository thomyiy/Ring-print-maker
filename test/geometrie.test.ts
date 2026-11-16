// La bague du navigateur (shared/alliance.ts) contre celle de Python
// (moteur/alliance.py). Lancer : node --test test/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { construire, placerBande, type TextureRelief } from '../shared/alliance.ts'

const dossier = mkdtempSync(join(tmpdir(), 'geom-'))
execFileSync(process.env.PYTHON ?? 'python3', [join(import.meta.dirname, 'fixture_geometrie.py'), dossier])
const ref = JSON.parse(readFileSync(join(dossier, 'geometrie.json'), 'utf8'))

function ecartMax(a: ArrayLike<number>, b: ArrayLike<number>) {
  assert.equal(a.length, b.length, 'nombre de sommets')
  let m = 0
  for (let i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i]! - b[i]!))
  return m
}

for (const [nom, c] of Object.entries<any>(ref.sans_relief)) {
  test(`sans relief, ${nom} : mêmes sommets que Python`, () => {
    const a = construire(c.params)
    // float32 côté navigateur : 1e-5 mm près sur une bague de 11 mm de rayon.
    assert.ok(ecartMax(a.positions, c.positions) < 2e-5, `écart ${ecartMax(a.positions, c.positions)}`)
    assert.ok(Math.abs(a.volumeMm3 - Math.abs(c.volume)) < 1e-6 * Math.abs(c.volume))
  })
}

test('avec relief : même bande, même bague, à la texture près', () => {
  const r = ref.avec_relief
  const t = r.texture
  const tx: TextureRelief = {
    donnees: new Uint8Array(readFileSync(join(dossier, 'relief.raw'))), pas: 1,
    largeur: t.largeur, hauteur: t.hauteur, x0: t.x0, y0: t.y0, facteur: t.facteur,
  }
  const b = placerBande(r.bouts, r.hauteur_image, true, r.largeur_utile, r.mm_par_px, r.periode_px, tx)
  // La bande bord à bord recalculée ici retombe sur celle de Python.
  assert.ok(Math.abs(b.longueurMm - r.longueur_mm) < 0.1, `longueur ${b.longueurMm} contre ${r.longueur_mm}`)
  const a = construire(r.params, { bande: b, texture: tx })
  // La texture est l'agrandi ×6 ramené à ×3 : le relief diffère d'un souffle.
  assert.ok(Math.abs(a.volumeMm3 - r.volume) / r.volume < 0.003, `volume ${a.volumeMm3} contre ${r.volume}`)
  assert.ok(Math.abs(a.arcReliefMm - r.arc_relief) < 0.15, `arc ${a.arcReliefMm} contre ${r.arc_relief}`)
  // Sommet par sommet : identiques hors relief, à moins d'un dixième de la hauteur dessus.
  assert.ok(ecartMax(a.positions, r.positions) < 0.1 * r.params.hauteur_relief, `écart ${ecartMax(a.positions, r.positions)}`)
})
