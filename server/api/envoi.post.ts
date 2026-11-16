import { cp, mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

interface Corps {
  type?: 'alliance' | 'chevaliere' | 'medaille'
  marque?: string
  id: string
  piece?: { nom?: string }
  contact?: { nom?: string; email?: string; telephone?: string; message?: string }
  choix?: Record<string, unknown>
  params: Record<string, unknown>
}

const nettoyer = (s: unknown, max: number) => String(s ?? '').replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, max)

function slug(s: string) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'alliance'
}

/**
 * La bague part à l'atelier : recalculée en qualité FABRICATION (la page client
 * ne montre qu'un aperçu plus léger), rangée avec sa fiche, puis annoncée au
 * webhook s'il y en a un.
 */
export default defineEventHandler(async (event) => {
  const c = await readBody<Corps>(event)
  const dossierSource = dossierSession(c.id)
  const type = c.type === 'chevaliere' || c.type === 'medaille' ? c.type : 'alliance'
  const DEFAUT = { alliance: 'Alliance empreinte', chevaliere: 'Chevalière empreinte', medaille: 'Médaille empreinte' }
  const nomPiece = nettoyer(c.piece?.nom, 80) || DEFAUT[type]
  const contact = {
    nom: nettoyer(c.contact?.nom, 120),
    email: nettoyer(c.contact?.email, 200),
    telephone: nettoyer(c.contact?.telephone, 40),
    message: nettoyer(c.contact?.message, 2000),
  }
  if (!contact.nom) throw createError({ statusCode: 400, statusMessage: 'Votre nom est nécessaire.' })
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email)) {
    throw createError({ statusCode: 400, statusMessage: 'L’adresse e-mail ne semble pas valide.' })
  }

  const d = new Date()
  const p2 = (n: number) => String(n).padStart(2, '0')
  const horodatage = `${d.getFullYear()}${p2(d.getMonth() + 1)}${p2(d.getDate())}-${p2(d.getHours())}${p2(d.getMinutes())}${p2(d.getSeconds())}`
  const ref = `${horodatage}-${slug(nomPiece)}`
  const dossier = dossierEnvoi(ref)
  await mkdir(dossier, { recursive: true })
  await cp(join(dossierSource, 'source.png'), join(dossier, 'empreinte_source.png'))

  const params = type === 'alliance' ? { ...c.params, n_sections: 1440, n_face: 50 } : { ...c.params }
  const fichierParams = await ecrireParams(dossier, params)
  const r = await lancerMoteur([
    type === 'alliance' ? 'generer' : type,
    '--image', join(dossier, 'empreinte_source.png'), '--params', fichierParams, '--sortie', dossier,
  ])

  const fiche = {
    ref,
    recu_le: d.toISOString(),
    piece: nomPiece,
    contact,
    type,
    // Pour qui l'atelier fabrique : 'raw', ou le client en marque blanche.
    marque: c.marque === 'joia' ? 'joia' : 'raw',
    choix: c.choix ?? {},
    bande: r.bande,
    controles: r.controles,
    avertissements: r.avertissements,
    fichiers: [r.stl, ...Object.values(r.images ?? {}), 'empreinte_source.png'],
  }
  await writeFile(join(dossier, 'fiche.json'), JSON.stringify(fiche, null, 2))

  const cfg = useRuntimeConfig()
  if (cfg.webhookEnvoi) {
    const base = getRequestURL(event).origin
    try {
      await $fetch(cfg.webhookEnvoi, {
        method: 'POST',
        body: { ...fiche, liens: Object.fromEntries(fiche.fichiers.map((f) => [f, `${base}/api/envois/${ref}/${f}`])) },
        timeout: 10_000,
      })
    } catch (e: any) {
      // L'envoi est déjà rangé : un webhook en panne ne doit pas le faire échouer.
      console.error('[envoi] webhook injoignable :', e?.message ?? e)
    }
  }
  return { ok: true, ref, piece: nomPiece }
})
