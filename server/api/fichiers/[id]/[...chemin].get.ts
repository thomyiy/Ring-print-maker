import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { join } from 'node:path'

const TYPES: Record<string, string> = { png: 'image/png', stl: 'model/stl', json: 'application/json', bin: 'application/octet-stream' }

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id') ?? ''
  const morceaux = (getRouterParam(event, 'chemin') ?? '').split('/')
  const dossier = dossierSession(id)
  let chemin: string
  let nom = 'source.png'
  if (morceaux.length === 1 && morceaux[0] === 'source') {
    chemin = join(dossier, 'source.png')
  } else if (morceaux.length === 2) {
    const [sous, fichier] = morceaux
    const m = /^([a-z0-9_]+)\.(png|stl|json|bin)$/i.exec(fichier)
    if (!m) throw createError({ statusCode: 400 })
    chemin = join(dossier, nomSortie(sous), fichier)
    nom = fichier
  } else {
    throw createError({ statusCode: 404 })
  }
  try {
    const s = await stat(chemin)
    setHeader(event, 'Content-Length', s.size)
  } catch {
    throw createError({ statusCode: 404, statusMessage: 'Fichier expiré ou absent' })
  }
  const ext = nom.split('.').pop()!.toLowerCase()
  setHeader(event, 'Content-Type', TYPES[ext] ?? 'application/octet-stream')
  if (ext === 'stl') setHeader(event, 'Content-Disposition', `attachment; filename="alliance-empreinte.stl"`)
  return sendStream(event, createReadStream(chemin))
})
