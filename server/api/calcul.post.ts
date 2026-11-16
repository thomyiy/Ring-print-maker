/** `analyser` (empreinte seule, rapide) ou `generer` (STL et contrôles). */
export default defineEventHandler(async (event) => {
  const corps = await readBody<{ id: string; action: 'analyser' | 'generer'; params: Record<string, unknown> }>(event)
  const dossier = dossierSession(corps.id)
  const action = corps.action === 'generer' ? 'generer' : 'analyser'
  const sous = `${action}-${Date.now().toString(36)}`
  const sortie = `${dossier}/${sous}`
  const params = await ecrireParams(sortie, corps.params)
  const r = await lancerMoteur([action, '--image', `${dossier}/source.png`, '--params', params, '--sortie', sortie])
  return urlsFichiers(corps.id, sous, r)
})
