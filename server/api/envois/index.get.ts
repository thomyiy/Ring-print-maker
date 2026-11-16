import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

/** La liste des bagues reçues, la plus récente d'abord. Atelier seulement. */
export default defineEventHandler(async (event) => {
  exigerAtelier(event)
  const racine = racineEnvois()
  let noms: string[] = []
  try { noms = await readdir(racine) } catch { return [] }
  const fiches = []
  for (const n of noms.sort().reverse()) {
    try { fiches.push(JSON.parse(await readFile(join(racine, n, 'fiche.json'), 'utf8'))) } catch {}
  }
  return fiches
})
