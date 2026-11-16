import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
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
// mémoire. Deux en parallèle sur un petit conteneur Railway suffisent à le
// faire tuer.
let file: Promise<unknown> = Promise.resolve()

export function lancerMoteur(args: string[]): Promise<any> {
  const tache = file.then(() => demander(args))
  file = tache.catch(() => undefined)
  return tache
}

// — Le processus Python persistant ———————————————————————————————————
// ⚠️ UN PROCESSUS PAR CALCUL COÛTAIT 1,4 s D'IMPORTS ET JETAIT LE CACHE.
// Changer la taille de doigt prenait 7 à 9 s, dont 6 à retraiter une empreinte
// qui n'avait pas changé. Le moteur reste maintenant chargé
// (`python -m moteur serveur`) : une ligne JSON par demande, une ligne marquée
// `§§` par réponse. S'il meurt, le suivant le relance.
let ouvrier: ChildProcessWithoutNullStreams | null = null
let tampon = ''
let attente: { ok: (r: any) => void; ko: (e: any) => void } | null = null

function demarrer(): ChildProcessWithoutNullStreams {
  const cfg = useRuntimeConfig()
  const p = spawn(cfg.python || 'python3', ['-m', 'moteur', 'serveur'], {
    cwd: process.cwd(),
    env: { ...process.env, MPLBACKEND: 'Agg', MPLCONFIGDIR: join(tmpdir(), 'mpl'), PYTHONUNBUFFERED: '1' },
  })
  tampon = ''
  p.stdout.setEncoding('utf8')
  p.stdout.on('data', (d: string) => {
    tampon += d
    let i: number
    while ((i = tampon.indexOf('\n')) >= 0) {
      const ligne = tampon.slice(0, i)
      tampon = tampon.slice(i + 1)
      if (!ligne.startsWith('§§') || !attente) continue
      const a = attente
      attente = null
      try {
        const r = JSON.parse(ligne.slice(2))
        if (r.ok) a.ok(r)
        else a.ko(createError({ statusCode: 422, statusMessage: r.erreur, data: { trace: r.trace } }))
      } catch {
        a.ko(createError({ statusCode: 500, statusMessage: 'Réponse illisible du moteur' }))
      }
    }
  })
  let journal = ''
  p.stderr.on('data', (d) => { journal = (journal + d).slice(-4000) })
  const fin = (raison: string) => {
    if (ouvrier === p) ouvrier = null
    if (attente) {
      const a = attente
      attente = null
      a.ko(createError({ statusCode: 500, statusMessage: `Le moteur s’est arrêté (${raison})`, data: { stderr: journal } }))
    }
  }
  p.on('exit', (code, signal) => fin(signal ?? `code ${code}`))
  p.on('error', (e) => fin(e.message))
  return p
}

function demander(args: string[]): Promise<any> {
  return new Promise((ok, ko) => {
    if (!ouvrier) ouvrier = demarrer()
    const p = ouvrier
    const minuterie = setTimeout(() => p.kill('SIGKILL'), 180_000)
    attente = {
      ok: (r) => { clearTimeout(minuterie); ok(r) },
      ko: (e) => { clearTimeout(minuterie); ko(e) },
    }
    p.stdin.write(JSON.stringify(args) + '\n')
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
  return {
    ...r,
    images,
    stl: r.stl ? base + r.stl : undefined,
    apercu: r.apercu ? base + r.apercu : undefined,
  }
}
