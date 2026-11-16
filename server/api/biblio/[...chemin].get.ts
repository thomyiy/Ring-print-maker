import { mkdir, readFile, rename, stat, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'

/**
 * Les chevalières de rainbowantworkshop.fr, relayées.
 *
 * ⚠️ LE NAVIGATEUR NE PEUT PAS LES LIRE EN DIRECT : la bibliothèque ne renvoie
 * aucun en-tête CORS (vérifié le 16/11/2026), et une page d'un autre domaine
 * reçoit une erreur réseau. Notre serveur les cherche et les garde sur disque —
 * dans le même dossier que le moteur Python, qui lit les mêmes fichiers.
 *
 * Seuls les chemins de la bibliothèque des chevalières passent : ce relais
 * n'est pas un proxy ouvert.
 */
const AUTORISE = [
  /^catalog-chevaliere\.json$/,
  /^catalog-medaille\.json$/,
  /^rings\/[A-Z]{2,4}\/\d{1,2}\/(creuse|pleine)\/\d{3}\/(lisse|creux)\.jrm$/,
]

export default defineEventHandler(async (event) => {
  const chemin = getRouterParam(event, 'chemin') ?? ''
  if (!AUTORISE.some((r) => r.test(chemin))) throw createError({ statusCode: 404 })
  const cfg = useRuntimeConfig()
  const racine = resolve(cfg.dossierBiblio || join(process.cwd(), '.data', 'biblio'))
  const local = join(racine, chemin)
  const catalogue = chemin.endsWith('.json')

  let donnees: Buffer | null = null
  try {
    const s = await stat(local)
    // Les maillages sont immuables ; le catalogue se relit une fois par jour.
    if (!catalogue || Date.now() - s.mtimeMs < 86_400_000) donnees = await readFile(local)
  } catch {}
  if (!donnees) {
    const base = (cfg.biblioUrl || 'https://rainbowantworkshop.fr/biblio/assets').replace(/\/$/, '')
    try {
      donnees = Buffer.from(await $fetch<ArrayBuffer>(`${base}/${chemin}`, { responseType: 'arrayBuffer', timeout: 20_000 }))
    } catch (e: any) {
      throw createError({ statusCode: 502, statusMessage: 'Bibliothèque injoignable' })
    }
    await mkdir(dirname(local), { recursive: true })
    const tmp = `${local}.${process.pid}.part`
    await writeFile(tmp, donnees)
    await rename(tmp, local)
  }
  setHeader(event, 'Content-Type', catalogue ? 'application/json' : 'application/octet-stream')
  setHeader(event, 'Cache-Control', catalogue ? 'public, max-age=3600' : 'public, max-age=31536000, immutable')
  return donnees
})
