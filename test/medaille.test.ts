// La médaille du navigateur (shared/medaille.ts) contre celle de Python
// (moteur/medaille.py). Lancer : node --test test/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { reliefSolide } from '../shared/chevaliere.ts'
import { corpsMedaille, MARGE_TROU, trouMedaille, volumeGeometrie, zoneMedaille } from '../shared/medaille.ts'

const dossier = mkdtempSync(join(tmpdir(), 'med-'))
execFileSync(process.env.PYTHON ?? 'python3', [join(import.meta.dirname, 'fixture_geometrie.py'), dossier])
const ref = JSON.parse(readFileSync(join(dossier, 'geometrie.json'), 'utf8')).medaille

for (const c of ref.corps) {
  test(`corps ${c.forme.id} ${c.taille.mm} mm : même volume que Python, à 0,5 % près`, () => {
    const v = volumeGeometrie(corpsMedaille(c.taille, 1.4, c.forme.bail))
    // Biseau lisse ici, arrondi en 8 marches là-bas : l'écart reste minime.
    assert.ok(Math.abs(v - c.volume) / c.volume < 0.005, `${v} contre ${c.volume}`)
  })
}

test('relief de médaille, trou de bélière évité : même solide que Python', () => {
  const r = ref.relief
  const hauteur = (u: number, v: number) => 0.3 * (1 + Math.sin(3 * u) * Math.cos(2 * v)) / 2
  const t = trouMedaille(r.taille, r.forme.bail)!
  const s = reliefSolide(zoneMedaille(r.taille), zoneMedaille(r.taille), hauteur, 0, 0.1, [t[0], t[1], t[2] + MARGE_TROU])
  assert.deepEqual(Array.from(s.indices), r.indices)
  let m = 0
  for (let i = 0; i < r.positions.length; i++) m = Math.max(m, Math.abs(s.positions[i]! - r.positions[i]))
  assert.ok(m < 1e-5, `écart ${m}`)
})
