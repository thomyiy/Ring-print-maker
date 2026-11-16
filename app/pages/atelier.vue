<script setup lang="ts">
type Schema = Record<string, { defaut: any; min: number; max: number; pas: number; unite: string; libelle: string }>

const { data: schema } = await useFetch<Schema & { ok: boolean }>('/api/schema')

// — Les réglages ——————————————————————————————————————————————————
const r = reactive({
  taille: 54,
  hauteur_relief: 0.18,
  zone_auto: true,
  angle_bande_deg: 90,
  decalage_bande: 0,
  cote: 1.8,
  rayon_arete: 0.15,
  torsion_deg: 180,
  arc_torsion_deg: 170,
  adouci: 0.08,
  sens: 1,
  cretes_largeur: 7,
  flou: 0.12,
  douceur: 0.08,
  aire_min_mm2: 0.01,
  agrandissement: 6,
  cretes_noires: true,
  miroir: false,
  qualite: 'fabrication' as 'apercu' | 'fabrication',
})
// Taille française = tour du doigt en mm ; 54 → 17,2 mm. Le diamètre reste
// modifiable à la main après coup, pour les tables d'atelier qui arrondissent autrement.
const diametre = ref(17.2)
watch(() => r.taille, (t) => { diametre.value = Math.round((t / Math.PI) * 10) / 10 })
const borne = (k: string) => schema.value?.[k] ?? { min: 0, max: 1, pas: 0.01, unite: '' }

function params() {
  const { zone_auto, qualite, ...reste } = r
  return {
    ...reste,
    diametre_interieur: diametre.value,
    angle_bande_deg: zone_auto ? null : r.angle_bande_deg,
    decalage_bande: zone_auto ? 0 : r.decalage_bande,
    n_sections: qualite === 'fabrication' ? 1440 : 720,
    n_face: qualite === 'fabrication' ? 50 : 26,
  }
}

// — L'empreinte ———————————————————————————————————————————————————
const depot = ref<{ id: string; nom: string; image: string } | null>(null)
const envoi = ref(false)
const erreur = ref('')

async function deposer(fichier?: File) {
  erreur.value = ''
  envoi.value = true
  try {
    const fd = new FormData()
    if (fichier) fd.append('image', fichier)
    depot.value = await $fetch('/api/empreinte' + (fichier ? '' : '?demo=1'), { method: 'POST', body: fd })
    resultat.value = null
    await analyser()
  } catch (e: any) {
    erreur.value = e?.data?.statusMessage ?? e?.statusMessage ?? String(e)
  } finally {
    envoi.value = false
  }
}
function surDepot(ev: DragEvent) {
  const f = ev.dataTransfer?.files?.[0]
  if (f) deposer(f)
}

// — Analyse (rapide) et génération ————————————————————————————————————
const analyse = ref<any>(null)
const resultat = ref<any>(null)
const enAnalyse = ref(false)
const enGeneration = ref(false)

async function calcul(action: 'analyser' | 'generer') {
  if (!depot.value) return null
  erreur.value = ''
  try {
    return await $fetch<any>('/api/calcul', { method: 'POST', body: { id: depot.value.id, action, params: params() } })
  } catch (e: any) {
    erreur.value = e?.data?.statusMessage ?? e?.statusMessage ?? 'Le calcul a échoué'
    return null
  }
}

async function analyser() {
  enAnalyse.value = true
  const a = await calcul('analyser')
  enAnalyse.value = false
  if (a) {
    analyse.value = a
    // Quand la zone est automatique, on reprend ce qu'elle a trouvé : passer
    // en manuel part de là au lieu de repartir de zéro.
    if (r.zone_auto) {
      r.angle_bande_deg = Math.round(a.bande.angle_deg)
      r.decalage_bande = Math.round(a.bande.decalage_mm * 20) / 20
    }
  }
}

async function generer() {
  enGeneration.value = true
  const g = await calcul('generer')
  enGeneration.value = false
  if (g) {
    resultat.value = g
    analyse.value = g
    onglet.value = 'apercu'
  }
}

// Les réglages qui touchent l'empreinte relancent l'analyse, un peu après.
const cleAnalyse = computed(() => JSON.stringify([
  r.zone_auto, r.zone_auto ? 0 : r.angle_bande_deg, r.zone_auto ? 0 : r.decalage_bande,
  r.cote, r.rayon_arete, r.cretes_largeur, r.flou, r.douceur, r.aire_min_mm2,
  r.agrandissement, r.cretes_noires, r.miroir, r.hauteur_relief,
]))
let minuterie: ReturnType<typeof setTimeout> | undefined
watch(cleAnalyse, () => {
  clearTimeout(minuterie)
  if (depot.value) minuterie = setTimeout(analyser, 700)
})
const perime = computed(() => resultat.value && JSON.stringify(resultat.value.parametres_envoyes) !== JSON.stringify(params()))
watch(resultat, (g) => { if (g) g.parametres_envoyes = params() })

// — Affichage ————————————————————————————————————————————————————
const onglet = ref<'apercu' | 'general' | 'dessus' | 'relief' | 'masque' | 'bande'>('masque')
const metal = ref<'or' | 'argent'>('or')
const vue3d = ref<{ vue: (n: 'dessus' | 'face' | 'biais') => void } | null>(null)
const ONGLETS = [
  { cle: 'apercu', nom: '3D', faut: 'stl' },
  { cle: 'general', nom: 'Vue générale', faut: 'general' },
  { cle: 'dessus', nom: 'Dessus, portée', faut: 'dessus' },
  { cle: 'relief', nom: 'Relief', faut: 'relief' },
  { cle: 'masque', nom: 'Empreinte et cadre', faut: 'masque' },
  { cle: 'bande', nom: 'Bande déroulée', faut: 'bande' },
] as const
const images = computed(() => ({ ...(analyse.value?.images ?? {}), ...(resultat.value?.images ?? {}) }))
function dispo(faut: string) {
  return faut === 'stl' ? !!resultat.value?.stl : !!images.value[faut]
}

const f = (x: number, d = 2) => (x ?? 0).toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
const c = computed(() => resultat.value?.controles)
const b = computed(() => analyse.value?.bande)
</script>

<template>
  <div class="min-h-screen">
    <!-- En-tête -->
    <header class="border-b border-line">
      <div class="flex items-center justify-between px-5 py-4 lg:px-10">
        <div class="flex items-center gap-3">
          <NuxtLink to="/"><img src="/logo-mark.png" alt="Accueil" class="h-8 w-auto"></NuxtLink>
          <span class="text-[17px] font-medium tracking-tight">Rainbow Ant Workshop</span>
        </div>
        <span class="eyebrow">Outil d’atelier</span>
      </div>
    </header>

    <div class="px-5 pb-6 pt-10 lg:px-10">
      <p class="eyebrow">Alliance torsadée</p>
      <div class="filet-teinte mt-3" />
      <h1 class="mt-5 text-[40px] sm:text-[52px]">Empreinte en relief</h1>
      <p class="mt-3 max-w-[68ch]">
        Fil carré, un demi-tour de torsion centré au sommet, et l’empreinte qui court sur la face
        qui passe dessus. Le STL est prêt pour la résine calcinable et la fonte à cire perdue.
      </p>
    </div>

    <div class="grid gap-0 border-t border-line lg:grid-cols-[400px_1fr]">
      <!-- ─── Réglages ─── -->
      <aside class="border-line lg:border-r">
        <!-- 1. L'image -->
        <section class="border-b border-line px-5 py-6 lg:px-8">
          <p class="eyebrow">01 · L’empreinte</p>
          <label
            class="mt-4 flex cursor-pointer flex-col items-center justify-center border border-dashed border-line bg-paper-2 px-4 py-6 text-center hover:border-ink"
            @dragover.prevent
            @drop.prevent="surDepot"
          >
            <img v-if="depot" :src="depot.image" alt="Empreinte déposée" class="mb-3 max-h-36 w-auto">
            <span class="text-[14px] text-ink">{{ depot ? depot.nom : 'Déposer l’image ici' }}</span>
            <span class="mt-1 text-[13px] text-muted">PNG ou JPG, noir et blanc ou niveaux de gris</span>
            <input type="file" accept="image/*" class="sr-only" @change="deposer(($event.target as HTMLInputElement).files?.[0])">
          </label>
          <button class="lien mt-3 text-[14px]" :disabled="envoi" @click="deposer()">
            Essayer avec l’empreinte de démonstration
          </button>
          <p v-if="envoi" class="mt-2 text-[13px] text-muted">Envoi…</p>
        </section>

        <!-- 2. Les trois questions -->
        <section class="border-b border-line bg-bleu-pale px-5 py-6 lg:px-8">
          <p class="valeur text-bleu-texte">02</p>
          <h2 class="mt-1 text-[20px] font-medium">Les trois choses à décider</h2>
          <div class="mt-5 space-y-6">
            <div>
              <Reglage v-model="r.taille" libelle="Taille de doigt" :min="40" :max="75" :pas="0.5" />
              <Reglage v-model="diametre" class="mt-4" libelle="Diamètre intérieur" :min="12" :max="24" :pas="0.01" unite="mm" />
            </div>
            <Reglage
              v-model="r.hauteur_relief" libelle="Hauteur des crêtes" :min="0.08" :max="0.4" :pas="0.01" unite="mm"
              aide="0,18 mm pour l’effet ; 0,25 à 0,3 mm tiennent mieux au porter quotidien."
            />
            <div>
              <span class="champ-intitule">Zone de l’empreinte</span>
              <div class="mt-2 flex gap-5 text-[14px]">
                <label class="flex items-center gap-2"><input v-model="r.zone_auto" type="radio" :value="true"> Automatique</label>
                <label class="flex items-center gap-2"><input v-model="r.zone_auto" type="radio" :value="false"> Je cadre</label>
              </div>
              <p class="mt-1 text-[13px] text-txt">
                La bande en biais où les crêtes filent dans la longueur, d’un bord à l’autre de l’empreinte.
              </p>
              <div v-if="!r.zone_auto" class="mt-4 space-y-4">
                <Reglage v-model="r.angle_bande_deg" libelle="Angle" :min="0" :max="179" :pas="1" unite="°" />
                <Reglage v-model="r.decalage_bande" libelle="Décalage latéral" :min="-6" :max="6" :pas="0.05" unite="mm" />
              </div>
            </div>
          </div>
        </section>

        <!-- 3. Forme -->
        <details class="group border-b border-line px-5 py-5 lg:px-8">
          <summary class="flex cursor-pointer list-none items-center justify-between">
            <span class="eyebrow">03 · Forme du fil</span><span class="text-muted group-open:rotate-45">+</span>
          </summary>
          <div class="mt-5 space-y-5">
            <Reglage v-model="r.cote" libelle="Côté du carré" :min="1.2" :max="3" :pas="0.05" unite="mm" />
            <Reglage v-model="r.rayon_arete" libelle="Rayon des arêtes" :min="0.05" :max="0.4" :pas="0.01" unite="mm" />
            <Reglage v-model="r.torsion_deg" libelle="Torsion" :min="180" :max="360" :pas="180" unite="°" aide="Un nombre impair de demi-tours ferme l’anneau sur la face opposée." />
            <Reglage v-model="r.arc_torsion_deg" libelle="Arc de la torsion" :min="60" :max="300" :pas="1" unite="°" />
            <Reglage v-model="r.adouci" libelle="Adouci aux raccords" :min="0" :max="0.3" :pas="0.01" aide="Part de l’arc où la vitesse de rotation monte et descend." />
            <div>
              <span class="champ-intitule">Sens de la torsion</span>
              <div class="mt-2 flex gap-5 text-[14px]">
                <label class="flex items-center gap-2"><input v-model="r.sens" type="radio" :value="1"> Chant gauche dessus</label>
                <label class="flex items-center gap-2"><input v-model="r.sens" type="radio" :value="-1"> Inverse</label>
              </div>
            </div>
          </div>
        </details>

        <!-- 4. Traitement de l'image -->
        <details class="group border-b border-line px-5 py-5 lg:px-8">
          <summary class="flex cursor-pointer list-none items-center justify-between">
            <span class="eyebrow">04 · Traitement de l’image</span><span class="text-muted group-open:rotate-45">+</span>
          </summary>
          <div class="mt-5 space-y-5">
            <Reglage v-model="r.cretes_largeur" libelle="Crêtes dans la largeur" :min="4" :max="10" :pas="0.5" aide="Règle l’échelle : 6 à 8 sur 1,5 mm." />
            <Reglage v-model="r.agrandissement" libelle="Agrandissement" :min="2" :max="8" :pas="1" unite="×" />
            <Reglage v-model="r.flou" libelle="Flou" :min="0" :max="0.4" :pas="0.01" unite="pér." />
            <Reglage v-model="r.douceur" libelle="Douceur du seuil" :min="0.02" :max="0.3" :pas="0.01" aide="Plus haut, flancs plus en pente." />
            <Reglage v-model="r.aire_min_mm2" libelle="Points isolés retirés sous" :min="0" :max="0.05" :pas="0.001" unite="mm²" />
            <label class="flex items-center gap-2 text-[14px]"><input v-model="r.cretes_noires" type="checkbox"> Crêtes noires sur l’image</label>
            <label class="flex items-center gap-2 text-[14px]"><input v-model="r.miroir" type="checkbox"> Retourner l’empreinte (miroir)</label>
          </div>
        </details>

        <!-- 5. Générer -->
        <section class="px-5 py-6 lg:px-8">
          <span class="champ-intitule">Maillage</span>
          <div class="mt-2 flex gap-5 text-[14px]">
            <label class="flex items-center gap-2"><input v-model="r.qualite" type="radio" value="fabrication"> Fabrication <span class="valeur text-muted">1440 × 50</span></label>
            <label class="flex items-center gap-2"><input v-model="r.qualite" type="radio" value="apercu"> Aperçu <span class="valeur text-muted">720 × 26</span></label>
          </div>
          <button class="btn-primary mt-5 w-full" :disabled="!depot || enGeneration" @click="generer">
            {{ enGeneration ? 'Calcul en cours…' : 'Générer le STL' }}
          </button>
          <p v-if="!depot" class="mt-2 text-[13px] text-muted">Déposer d’abord une empreinte.</p>
          <p v-if="erreur" class="mt-3 text-[13px] text-framboise">{{ erreur }}</p>
        </section>
      </aside>

      <!-- ─── Résultats ─── -->
      <main class="min-w-0">
        <nav class="flex flex-wrap gap-x-6 gap-y-2 border-b border-line px-5 py-4 lg:px-8">
          <button
            v-for="o in ONGLETS" :key="o.cle"
            class="text-[14px] underline-offset-[6px]"
            :class="[onglet === o.cle ? 'text-ink underline decoration-vert decoration-2' : 'text-txt', !dispo(o.faut) && 'opacity-40']"
            :disabled="!dispo(o.faut)"
            @click="onglet = o.cle"
          >
            {{ o.nom }}
          </button>
          <span v-if="enAnalyse" class="ml-auto eyebrow">Analyse…</span>
        </nav>

        <div class="relative h-[62vh] min-h-[420px] bg-paper-2">
          <template v-if="onglet === 'apercu' && resultat?.stl">
            <VueAlliance ref="vue3d" :url="resultat.stl" :teinte="metal === 'or' ? 0xe0b765 : 0xdcdcdc" />
            <div class="absolute bottom-4 left-4 flex gap-4 text-[13px]">
              <button class="lien" @click="vue3d?.vue('biais')">Biais</button>
              <button class="lien" @click="vue3d?.vue('dessus')">Dessus</button>
              <button class="lien" @click="vue3d?.vue('face')">Face</button>
              <span class="text-line">|</span>
              <button class="lien" @click="metal = metal === 'or' ? 'argent' : 'or'">{{ metal === 'or' ? 'Voir en argent' : 'Voir en or' }}</button>
            </div>
          </template>
          <img
            v-else-if="images[onglet]"
            :src="images[onglet]"
            :alt="onglet"
            class="absolute inset-0 h-full w-full object-contain p-4"
          >
          <div v-else class="flex h-full items-center justify-center px-8 text-center">
            <p class="max-w-[46ch] text-muted">
              Déposez une empreinte : le cadrage de la bande s’affiche ici, puis la bague une fois générée.
            </p>
          </div>
          <p v-if="perime" class="absolute right-4 top-4 bg-paper px-3 py-1 text-[12px] text-txt border border-line">
            Réglages modifiés depuis la génération
          </p>
        </div>

        <!-- Chiffres -->
        <div class="grid border-t border-line md:grid-cols-3">
          <section class="border-line px-5 py-6 md:border-r lg:px-8">
            <p class="eyebrow">La bande</p>
            <dl v-if="b" class="mt-4 space-y-2 text-[14px]">
              <div class="flex justify-between"><dt>Angle, décalage</dt><dd class="valeur">{{ f(b.angle_deg, 0) }}° · {{ f(b.decalage_mm) }} mm</dd></div>
              <div class="flex justify-between"><dt>Longueur × largeur</dt><dd class="valeur">{{ f(b.longueur_mm) }} × {{ f(b.largeur_mm) }} mm</dd></div>
              <div class="flex justify-between"><dt>Crêtes alignées</dt><dd class="valeur">{{ f(100 * b.alignement, 0) }} %</dd></div>
              <div class="flex justify-between"><dt>Crêtes dans la largeur</dt><dd class="valeur">{{ f(b.cretes_largeur, 1) }}</dd></div>
              <div class="flex justify-between"><dt>Période des crêtes</dt><dd class="valeur">{{ f(b.periode_mm, 3) }} mm · {{ f(b.periode_px, 1) }} px</dd></div>
              <div class="flex justify-between"><dt>Échelle</dt><dd class="valeur">{{ f(b.mm_par_px * 1000, 1) }} µm/px</dd></div>
            </dl>
            <p v-else class="mt-4 text-[14px] text-muted">—</p>
          </section>

          <section class="border-line px-5 py-6 md:border-r lg:px-8">
            <p class="eyebrow">La pièce</p>
            <dl v-if="c" class="mt-4 space-y-2 text-[14px]">
              <div class="flex justify-between"><dt>Volume</dt><dd class="valeur">{{ f(c.volume_mm3, 1) }} mm³</dd></div>
              <div class="flex justify-between"><dt>Or 750 <span class="text-muted">(15,5)</span></dt><dd class="valeur">{{ f(c.poids_or_750_g) }} g</dd></div>
              <div class="flex justify-between"><dt>Argent 925 <span class="text-muted">(10,36)</span></dt><dd class="valeur">{{ f(c.poids_argent_925_g) }} g</dd></div>
              <div class="flex justify-between"><dt>Ø extérieur maxi</dt><dd class="valeur">{{ f(c.diametre_exterieur_max) }} mm</dd></div>
              <div class="flex justify-between"><dt>Largeur maxi</dt><dd class="valeur">{{ f(c.largeur_max) }} mm</dd></div>
              <div class="flex justify-between"><dt>Arc en relief</dt><dd class="valeur">{{ f(c.longueur_arc_relief_mm) }} mm</dd></div>
            </dl>
            <p v-else class="mt-4 text-[14px] text-muted">Générer pour mesurer.</p>
            <a v-if="resultat?.stl" :href="resultat.stl" class="lien mt-5 inline-block text-[14px]" download="alliance-empreinte.stl">
              Télécharger le STL
            </a>
          </section>

          <section class="px-5 py-6 lg:px-8">
            <p class="eyebrow">Contrôles</p>
            <dl v-if="c" class="mt-4 space-y-2 text-[14px]">
              <div class="flex justify-between"><dt>Étanche, 2 triangles par arête</dt><dd class="valeur" :class="c.etanche ? 'text-vert-texte' : 'text-framboise'">{{ c.etanche ? 'oui' : `non (${c.aretes_non_partagees_par_2})` }}</dd></div>
              <div class="flex justify-between"><dt>Normales sortantes</dt><dd class="valeur">{{ f(100 * c.normales_sortantes, 2) }} %</dd></div>
              <div class="flex justify-between"><dt>Ø intérieur mini / cote</dt><dd class="valeur">{{ f(c.diametre_interieur_min, 3) }} / {{ f(c.diametre_interieur_cote) }}</dd></div>
              <div class="flex justify-between"><dt>Écart au raccord</dt><dd class="valeur">{{ c.ecart_raccord.toExponential(1) }} mm</dd></div>
              <div class="flex justify-between"><dt>Pas tour / face</dt><dd class="valeur">{{ f(c.pas_tour_mm, 3) }} / {{ f(c.pas_face_mm, 3) }} mm</dd></div>
              <div class="flex justify-between"><dt>Triangles</dt><dd class="valeur">{{ c.triangles.toLocaleString('fr-FR') }}</dd></div>
            </dl>
            <p v-else class="mt-4 text-[14px] text-muted">—</p>
            <ul v-if="analyse?.avertissements?.length" class="mt-4 space-y-1 text-[13px] text-txt">
              <li v-for="(a, i) in analyse.avertissements" :key="i">— {{ a }}</li>
            </ul>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>
