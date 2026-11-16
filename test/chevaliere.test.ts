// Le relief de la chevalière du navigateur (shared/chevaliere.ts) contre celui
// de Python (moteur/chevaliere.py). Lancer : node --test test/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { contourCentre, lireJrm, MARGE_PLEIN, reliefSolide, retrecir } from '../shared/chevaliere.ts'

const dossier = mkdtempSync(join(tmpdir(), 'chev-'))
execFileSync(process.env.PYTHON ?? 'python3', [join(import.meta.dirname, 'fixture_geometrie.py'), dossier])
const ref = JSON.parse(readFileSync(join(dossier, 'geometrie.json'), 'utf8')).chevaliere
const hauteur = (u: number, v: number) => 0.3 * (1 + Math.sin(3 * u) * Math.cos(2 * v)) / 2

for (const surface of ['godet', 'plein'] as const) {
  test(`relief ${surface} : même solide que Python`, () => {
    const t = ref.taille
    const plateau = contourCentre(t, 'plateau')
    const zone = surface === 'godet' ? contourCentre(t, 'cup') : retrecir(plateau, MARGE_PLEIN)
    const emprise = surface === 'godet' ? retrecir(plateau, 0.3) : zone
    const s = reliefSolide(zone, emprise, hauteur, ref[surface].base, 0.1)
    const r = ref[surface]
    assert.equal(s.positions.length, r.positions.length, 'nombre de sommets')
    assert.deepEqual(Array.from(s.indices), r.indices, 'mêmes triangles, même ordre')
    let m = 0
    for (let i = 0; i < r.positions.length; i++) m = Math.max(m, Math.abs(s.positions[i]! - r.positions[i]))
    assert.ok(m < 1e-5, `écart ${m}`)
    assert.ok(Math.abs(s.volume - r.volume) < 1e-6 * Math.max(1, r.volume))
  })
}

test('lecture des maillages JRM1 : même volume que Python', () => {
  const buf = readFileSync(join(dossier, 'ecu.jrm'))
  const m = lireJrm(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength))
  const p = m.positions, f = m.indices
  let v = 0
  for (let k = 0; k < f.length; k += 3) {
    const a = f[k]! * 3, b = f[k + 1]! * 3, c = f[k + 2]! * 3
    v += p[a]! * (p[b + 1]! * p[c + 2]! - p[b + 2]! * p[c + 1]!) + p[a + 1]! * (p[b + 2]! * p[c]! - p[b]! * p[c + 2]!)
      + p[a + 2]! * (p[b]! * p[c + 1]! - p[b + 1]! * p[c]!)
  }
  assert.ok(Math.abs(v / 6 - ref.jrm_volume) < 0.01, `${v / 6} contre ${ref.jrm_volume}`)
})
