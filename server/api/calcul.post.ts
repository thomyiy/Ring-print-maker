/** `preparer` (page client : empreinte traitée, la bague se construit dans le
 *  navigateur), `analyser` (atelier : empreinte et figures) ou `generer` (STL). */
export default defineEventHandler(async (event) => {
  const corps = await readBody<{ id: string; action: 'analyser' | 'preparer' | 'generer'; leger?: boolean; params: Record<string, unknown> }>(event)
  const dossier = dossierSession(corps.id)
  const action = (['analyser', 'preparer', 'generer'] as const).includes(corps.action) ? corps.action : 'analyser'
  const sous = `${action}-${Date.now().toString(36)}`
  const sortie = `${dossier}/${sous}`
  const params = await ecrireParams(sortie, corps.params)
  const r = await lancerMoteur([
    action, '--image', `${dossier}/source.png`, '--params', params, '--sortie', sortie,
    ...(corps.leger && action === 'generer' ? ['--leger'] : []),
  ])
  return urlsFichiers(corps.id, sous, r)
})
