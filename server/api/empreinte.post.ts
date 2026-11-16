import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

/** Dépôt de l'image, ou empreinte de démonstration (`?demo=1`). */
export default defineEventHandler(async (event) => {
  await menage()
  const { id, dossier } = nouveauDossier()
  await mkdir(dossier, { recursive: true })
  const source = join(dossier, 'source.png')
  if (getQuery(event).demo) {
    await lancerMoteur(['synthetique', '--sortie', source])
    return { id, nom: 'empreinte de démonstration', image: `/api/fichiers/${id}/source` }
  }
  const parts = await readMultipartFormData(event)
  const f = parts?.find((p) => p.name === 'image' && p.data?.length)
  if (!f) throw createError({ statusCode: 400, statusMessage: 'Aucune image reçue' })
  if (f.data.length > 25 * 1024 * 1024) throw createError({ statusCode: 413, statusMessage: 'Image trop lourde (25 Mo max.)' })
  await writeFile(source, f.data)
  return { id, nom: f.filename ?? 'empreinte', image: `/api/fichiers/${id}/source` }
})
