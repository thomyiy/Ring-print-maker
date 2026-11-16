import { spawn } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

/** Dossier de travail : un sous-dossier par empreinte déposée. */
export function racineTravail(): string {
  const cfg = useRuntimeConfig()
  return resolve(cfg.dossierTravail || join(tmpdir(), 'alliance-empreinte'))
}

const ID = /^[0-9a-f-]{36}$/
const NOM = /^[a-z0-9_-]+$/i

export function dossierSession(id: string): string {
  if (!ID.test(id)) throw createError({ statusCode: 400, statusMessage: 'Identifiant invalide' })
  return join(racineTravail(), id)
}

export function nouveauDossier(): { id: string; dossier: string } {
  const id = randomUUID()
  return { id, dossier: join(racineTravail(), id) }
}

export function nomSortie(nom: string): string {
  if (!NOM.test(nom)) throw createError({ statusCode: 400, statusMessage: 'Nom invalide' })
  return nom
}

// ⚠️ Un seul calcul à la fois : un maillage de fabrication prend ~1 Go de
// mémoire et 10 à 15 s. Deux en parallèle sur un petit conteneur Railway
// suffisent à le faire tuer.
let file: Promise<unknown> = Promise.resolve()

export function lancerMoteur(args: string[]): Promise<any> {
  const tache = file.then(() => executer(args))
  file = tache.catch(() => undefined)
  return tache
}

function executer(args: string[]): Promise<any> {
  const cfg = useRuntimeConfig()
  return new Promise((ok, ko) => {
    const p = spawn(cfg.python || 'python3', ['-m', 'moteur', ...args], {
      cwd: process.cwd(),
      env: { ...process.env, MPLBACKEND: 'Agg', MPLCONFIGDIR: join(tmpdir(), 'mpl') },
    })
    let out = ''
    let err = ''
    const minuterie = setTimeout(() => p.kill('SIGKILL'), 180_000)
    p.stdout.on('data', (d) => (out += d))
    p.stderr.on('data', (d) => (err += d))
    p.on('error', (e) => {
      clearTimeout(minuterie)
      ko(createError({ statusCode: 500, statusMessage: `Moteur introuvable : ${e.message}` }))
    })
    p.on('close', () => {
      clearTimeout(minuterie)
      try {
        const r = JSON.parse(out)
        if (!r.ok) return ko(createError({ statusCode: 422, statusMessage: r.erreur, data: { trace: r.trace } }))
        ok(r)
      } catch {
        ko(createError({ statusCode: 500, statusMessage: 'Le moteur n’a rien rendu', data: { stderr: err.slice(-2000) } }))
      }
    })
  })
}

export async function ecrireParams(dossier: string, params: unknown): Promise<string> {
  await mkdir(dossier, { recursive: true })
  const chemin = join(dossier, 'params.json')
  await writeFile(chemin, JSON.stringify(params ?? {}))
  return chemin
}

/**
 * Les bagues envoyées à l'atelier. ⚠️ HORS du dossier de travail, que le
 * ménage vide toutes les six heures : un envoi effacé est une commande perdue.
 * Sur Railway, `NUXT_DOSSIER_ENVOIS` doit pointer sur un volume monté, sinon
 * chaque redéploiement les efface.
 */
export function racineEnvois(): string {
  const cfg = useRuntimeConfig()
  return resolve(cfg.dossierEnvois || join(process.cwd(), '.data', 'envois'))
}

const REF = /^[0-9]{8}-[0-9]{6}-[a-z0-9-]{1,60}$/
export function dossierEnvoi(ref: string): string {
  if (!REF.test(ref)) throw createError({ statusCode: 400, statusMessage: 'Référence invalide' })
  return join(racineEnvois(), ref)
}

/** L'atelier seul lit les envois : ils portent des coordonnées de clients. */
export function exigerAtelier(event: any) {
  const cfg = useRuntimeConfig()
  const jeton = String(getHeader(event, 'x-jeton-atelier') ?? getQuery(event).jeton ?? '')
  if (!cfg.jetonAtelier) {
    throw createError({ statusCode: 503, statusMessage: 'NUXT_JETON_ATELIER n’est pas défini sur le serveur' })
  }
  if (jeton !== cfg.jetonAtelier) throw createError({ statusCode: 401, statusMessage: 'Jeton d’atelier refusé' })
}

/** Ménage : on garde les dépôts six heures. */
export async function menage(): Promise<void> {
  const racine = racineTravail()
  const limite = Date.now() - 6 * 3600_000
  try {
    for (const n of await readdir(racine)) {
      const s = await stat(join(racine, n))
      if (s.mtimeMs < limite) await rm(join(racine, n), { recursive: true, force: true })
    }
  } catch {}
}

export function urlsFichiers(id: string, sous: string, r: any) {
  const base = `/api/fichiers/${id}/${sous}/`
  const images: Record<string, string> = {}
  for (const [k, v] of Object.entries(r.images ?? {})) images[k] = base + v
  return { ...r, images, stl: r.stl ? base + r.stl : undefined }
}
