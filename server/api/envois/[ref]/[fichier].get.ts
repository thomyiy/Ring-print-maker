import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { join } from 'node:path'

const TYPES: Record<string, string> = { png: 'image/png', stl: 'model/stl', json: 'application/json' }

export default defineEventHandler(async (event) => {
  exigerAtelier(event)
  const ref = getRouterParam(event, 'ref') ?? ''
  const fichier = getRouterParam(event, 'fichier') ?? ''
  if (!/^[a-z0-9_]+\.(png|stl|json)$/i.test(fichier)) throw createError({ statusCode: 400 })
  const chemin = join(dossierEnvoi(ref), fichier)
  try {
    setHeader(event, 'Content-Length', (await stat(chemin)).size)
  } catch {
    throw createError({ statusCode: 404 })
  }
  const ext = fichier.split('.').pop()!.toLowerCase()
  setHeader(event, 'Content-Type', TYPES[ext] ?? 'application/octet-stream')
  if (ext === 'stl') setHeader(event, 'Content-Disposition', `attachment; filename="${ref}.stl"`)
  return sendStream(event, createReadStream(chemin))
})
