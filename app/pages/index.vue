<!-- La page client : une photo d'empreinte, un métal, des dimensions, et la
     bague en trois dimensions. Tout le reste — cadrage de la bande, traitement
     de l'image, maillage — se règle par défaut ; l'atelier garde la main sur
     /atelier. -->
<script setup lang="ts">
import {
  boutsBande, construire, placerBande, type Alliance, type TextureRelief,
} from '~~/shared/alliance'

const marque = useMarque()
useHead({ title: `Alliance empreinte — ${marque.nom}` })

// — Les choix ————————————————————————————————————————————————————
// Densités : or 750 à 15,5 g/cm³ et argent 925 à 10,36 g/cm³, les valeurs de
// l'atelier. Les trois ors 750 partagent la même : l'écart réel entre jaune,
// rose et gris (quelques pour cent) est sous la précision d'une pesée avant fonte.
const METAUX = [
  { id: 'argent925', nom: 'Argent 925', densite: 10.36, teinte: 0xdcdcdc, pastille: '#D9D9D9' },
  { id: 'or-jaune', nom: 'Or jaune 18 k', densite: 15.5, teinte: 0xe3b864, pastille: '#E3B864' },
  { id: 'or-rose', nom: 'Or rose 18 k', densite: 15.5, teinte: 0xe7ad95, pastille: '#E7AD95' },
  { id: 'or-gris', nom: 'Or gris 18 k', densite: 15.5, teinte: 0xe9e7e1, pastille: '#E9E7E1' },
] as const
const LARGEURS = [
  { cote: 1.5, nom: 'Fine', detail: '1,5 mm' },
  { cote: 1.8, nom: 'Classique', detail: '1,8 mm' },
  { cote: 2.2, nom: 'Affirmée', detail: '2,2 mm' },
]
const RELIEFS = [
  { h: 0.18, nom: 'Délicat', detail: '0,18 mm' },
  { h: 0.25, nom: 'Marqué', detail: '0,25 mm' },
  { h: 0.3, nom: 'Profond', detail: '0,30 mm' },
]
const TAILLES = Array.from({ length: 27 }, (_, i) => 44 + i)

// L'échelle de l'empreinte, donnée par l'écart entre deux crêtes sur la bague.
const choix = reactive({ metal: 'or-jaune', taille: 54, cote: 1.8, relief: 0.25 })
const diametre = computed(() => Math.round((choix.taille / Math.PI) * 10) / 10)

// — L'empreinte, traitée une fois par le moteur ——————————————————————
// ⚠️ LA BAGUE SE CONSTRUIT DANS LE NAVIGATEUR (shared/alliance.ts), PAS SUR LE
// SERVEUR. Le moteur Python ne sert qu'une fois par empreinte (`preparer` :
// seuillage, échelle, cadrage automatique, texture de relief), puis à l'envoi
// pour le fichier de fabrication. Chaque réglage — taille, fil, relief,
// échelle, placement — se recalcule ici en quelques dizaines de millisecondes,
// sans aller-retour. `test/geometrie.test.ts` garde les deux géométries égales.
const depot = ref<{ id: string; nom: string; image: string } | null>(null)
const etat = ref<'vide' | 'envoi' | 'preparation' | 'pret' | 'erreur'>('vide')
const erreur = ref('')
const glisse = ref(false)
const prep = shallowRef<any>(null)
const texture = shallowRef<TextureRelief | null>(null)

// — Le placement, comme une gravure de médaille ————————————————————————
// La bande est un « plateau » fixe de LONGUEUR_BANDE × largeur de la face ; on
// y déplace, agrandit et tourne l'empreinte avec le même éditeur que la
// chevalière et la médaille (Thomas, 16/11/2026). Les crêtes s'arrêtent là où
// l'empreinte s'arrête : la bande n'en porte que ce qui tombe dedans.
const LONGUEUR_BANDE = 22   // mm de face sur le dessus, dans l'arc de torsion
const placement = ref<[number, number, number]>([0, 0, 0])
const mmParPx = ref(0.02)
const periodeMm = computed(() => (prep.value ? mmParPx.value * prep.value.periode_px : 0.45))
/** Les deux bouts de la bande en pixels d'édition (y vers le bas), ce que
 *  `placerBande` et le moteur (`bande_px`) attendent. */
const bandePx = computed<[number, number, number, number] | null>(() => {
  if (!prep.value) return null
  const [cx, cy, ang] = placement.value
  const a = (ang * Math.PI) / 180, d = LONGUEUR_BANDE / 2 / mmParPx.value
  return [cx - Math.cos(a) * d, cy - Math.sin(a) * d, cx + Math.cos(a) * d, cy + Math.sin(a) * d]
})
const bordABord = ref(false)

async function deposer(fichier?: File | null, demo = false) {
  if (!fichier && !demo) return
  erreur.value = ''
  etat.value = 'envoi'
  try {
    const fd = new FormData()
    if (fichier) fd.append('image', fichier)
    depot.value = await $fetch('/api/empreinte' + (demo ? '?demo=1' : ''), { method: 'POST', body: fd })
    prep.value = null
    texture.value = null
    await preparer()
  } catch (e: any) {
    montrerErreur(e)
  }
}

function montrerErreur(e: any) {
  etat.value = 'erreur'
  const m = e?.data?.statusMessage ?? e?.statusMessage ?? ''
  erreur.value = /empreinte|crête|bande/i.test(m)
    ? 'Nous n’avons pas trouvé d’empreinte nette sur cette photo. Essayez une image plus contrastée, l’empreinte bien à plat.'
    : m || 'Le calcul n’a pas abouti. Réessayez dans un instant.'
}

/** Le moteur traite l'empreinte et propose une bande. Une fois au dépôt, puis
 *  seulement si le client redemande le placement automatique. */
async function preparer() {
  if (!depot.value) return
  etat.value = 'preparation'
  try {
    const r = await $fetch<any>('/api/calcul', {
      method: 'POST',
      body: { id: depot.value.id, action: 'preparer', params: { cote: choix.cote, periode_mm: 0.45 } },
    })
    // La texture devient des pixels lisibles par la géométrie.
    const img = new Image()
    img.src = r.images.relief
    await img.decode()
    const toile = document.createElement('canvas')
    toile.width = img.naturalWidth
    toile.height = img.naturalHeight
    const ctx = toile.getContext('2d', { willReadFrequently: true })!
    ctx.drawImage(img, 0, 0)
    const t = r.texture
    texture.value = {
      donnees: ctx.getImageData(0, 0, toile.width, toile.height).data, pas: 4,
      largeur: t.largeur, hauteur: t.hauteur, x0: t.x0, y0: t.y0, facteur: t.facteur,
    }
    prep.value = r
    // La bande automatique du moteur devient le placement de départ : même
    // milieu, même angle, à l'échelle réelle.
    const [ax, ay] = r.edition.a, [bx, by] = r.edition.b
    placement.value = [(ax + bx) / 2, (ay + by) / 2, (Math.atan2(by - ay, bx - ax) * 180) / Math.PI]
    mmParPx.value = 0.45 / r.periode_px
    etat.value = 'pret'
  } catch (e) {
    montrerErreur(e)
  }
}


// — La bague, construite ici ——————————————————————————————————————————
const largeurUtile = computed(() => choix.cote - 2 * 0.15)
const bande = computed(() => {
  if (!prep.value || !texture.value || !bandePx.value) return null
  return placerBande(bandePx.value, prep.value.hauteur_image, bordABord.value,
    largeurUtile.value, mmParPx.value, prep.value.periode_px, texture.value)
})
const alliance = shallowRef<Alliance | null>(null)
watchEffect(() => {
  if (!bande.value || !texture.value) return
  alliance.value = construire(
    { diametre_interieur: diametre.value, cote: choix.cote, hauteur_relief: choix.relief, n_sections: 1080, n_face: 40 },
    { bande: bande.value, texture: texture.value },
  )
})

const contourBande = computed(() => {
  const l = LONGUEUR_BANDE / 2, w = largeurUtile.value / 2
  return [[-l, -w], [l, -w], [l, w], [-l, w]] as [number, number][]
})

/** Ce que le moteur reçoit à l'envoi : la bague qu'on voit, au point près. */
function paramsMoteur() {
  const b = bande.value && prep.value ? boutsBande(bande.value, prep.value.hauteur_image) : null
  return {
    taille: choix.taille,
    diametre_interieur: diametre.value,
    cote: choix.cote,
    periode_mm: periodeMm.value,
    hauteur_relief: choix.relief,
    bande_px: b,
    bord_a_bord: bordABord.value,
  }
}

const occupe = computed(() => etat.value === 'preparation' || etat.value === 'envoi')
const metal = computed(() => METAUX.find((m) => m.id === choix.metal)!)

// — L'envoi ————————————————————————————————————————————————————
const fenetreEnvoi = ref<{ ouvrir: () => void } | null>(null)
const LIB_RELIEF: Record<number, string> = { 0.18: 'délicat', 0.25: 'marqué', 0.3: 'profond' }
const resume = computed(() =>
  `Alliance empreinte · crêtes ${f(periodeMm.value, 2)} mm · ${metal.value.nom} · taille ${choix.taille} · fil ${f(choix.cote, 1)} mm · relief ${LIB_RELIEF[choix.relief] ?? f(choix.relief, 2) + ' mm'}`)

async function envoyer(fo: { nom_piece: string }) {
  return await $fetch<{ piece: string; ref: string }>('/api/envoi', {
    method: 'POST',
    body: {
      id: depot.value!.id,
      marque: marque.id,
      piece: { nom: fo.nom_piece },
      choix: { metal: choix.metal, metalNom: metal.value.nom, taille: choix.taille, cote: choix.cote, relief: choix.relief, periode_mm: periodeMm.value, poids_g: poids(metal.value.densite) },
      params: paramsMoteur(),
    },
  })
}

const volume = computed(() => alliance.value?.volumeMm3)
const poids = (d: number) => (volume.value ? (volume.value / 1000) * d : null)
const f = (x: number | null | undefined, d = 1) =>
  x == null ? '—' : x.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
const largeurMax = computed(() => alliance.value?.largeurMax)
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <EnTete />

    <div class="grid flex-1 items-start lg:grid-cols-[1fr_440px]">
      <!-- ─── La bague ─── -->
      <!-- ⚠️ UNE HAUTEUR, PAS UNE HAUTEUR MINIMALE. Avec `min-h` seul, la vue 3D
             (qui prend 100 % de son parent) tombait à 0 px sur téléphone : la
             bague était calculée, le cadre restait vide (Thomas, 16/11/2026). -->
        <div class="relative h-[56vh] min-h-[320px] bg-paper-2 lg:sticky lg:top-0 lg:h-[calc(100vh-65px)]">
        <ClientOnly>
          <VueAlliance v-if="alliance" :maillage="alliance" :teinte="metal.teinte" />
        </ClientOnly>

        <div v-if="!alliance" class="absolute inset-0 flex flex-col items-center justify-center px-8 text-center">
          <p class="eyebrow">Alliance empreinte</p>
          <div class="filet-teinte mx-auto mt-3" />
          <h1 class="mt-5 text-[40px] sm:text-[52px]">Votre empreinte, en relief</h1>
          <p class="mx-auto mt-4 max-w-[52ch]">
            Un fil carré qui fait un demi-tour sur le dessus de la main. Sur la face qui passe
            au sommet, les crêtes de votre empreinte, en relief dans le métal.
          </p>
          <p v-if="etat === 'envoi' || etat === 'preparation'" class="eyebrow mt-8">Lecture de votre empreinte…</p>
        </div>

        <!-- Recalcul : la bague affichée est l'ancienne, on le dit franchement. -->
        <div v-if="alliance && occupe" class="pointer-events-none absolute inset-0 bg-paper-2/60" aria-live="polite">
          <div class="barre-calcul absolute inset-x-0 top-0 h-[3px] overflow-hidden bg-vert-pale" />
          <div class="absolute inset-0 flex items-center justify-center">
            <p class="border border-line bg-paper px-5 py-3 text-[15px] text-ink">
              Recadrage de l’empreinte…
            </p>
          </div>
        </div>
        <p v-if="alliance && !occupe" class="absolute bottom-5 left-5 text-[13px] text-txt">
          Faites tourner la bague du doigt ou de la souris.
        </p>
      </div>

      <!-- ─── Les choix ─── -->
      <aside class="border-line lg:border-l">
        <!-- 1. L'empreinte -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">01</span>
            <h2 class="text-[20px] font-medium">Votre empreinte</h2>
          </div>
          <label
            class="mt-5 flex cursor-pointer items-center gap-4 border border-dashed px-4 py-4 transition-colors"
            :class="glisse ? 'border-ink bg-vert-pale' : 'border-line bg-paper-2 hover:border-ink'"
            @dragover.prevent="glisse = true"
            @dragleave="glisse = false"
            @drop.prevent="glisse = false; deposer($event.dataTransfer?.files?.[0])"
          >
            <img v-if="depot" :src="depot.image" alt="Votre empreinte" class="h-16 w-16 border border-line bg-paper object-contain">
            <span v-else class="flex h-16 w-16 items-center justify-center border border-line bg-paper text-[22px] text-muted">+</span>
            <span class="flex flex-col">
              <span class="text-[15px] text-ink">{{ depot ? 'Changer de photo' : 'Ajouter la photo de votre empreinte' }}</span>
              <span class="text-[13px] text-txt">Une empreinte encrée sur papier blanc, photographiée bien à plat.</span>
            </span>
            <input type="file" accept="image/*" class="sr-only" @change="deposer(($event.target as HTMLInputElement).files?.[0])">
          </label>
          <button v-if="!depot" type="button" class="lien mt-3 text-[14px]" @click="deposer(null, true)">
            Voir avec une empreinte d’exemple
          </button>
          <p v-if="etat === 'erreur'" class="mt-3 text-[13px] text-framboise">{{ erreur }}</p>
        </section>

        <!-- 2. Le placement -->
        <section v-if="depot" class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">02</span>
            <h2 class="text-[20px] font-medium">La partie de l’empreinte</h2>
          </div>
          <p class="mt-2 text-[14px] text-txt">
            Seule une bande de 1,5 mm de large passe sur la bague. Choisissez laquelle.
          </p>
          <EditeurGravure
            v-if="prep"
            v-model:placement="placement" v-model:mm-par-px="mmParPx"
            class="mt-5"
            :image="prep.images.edition" :largeur="prep.edition.largeur" :hauteur="prep.edition.hauteur"
            :boite="prep.boite_empreinte" :contour="contourBande" :zone="contourBande"
            :periode-px="prep.periode_px" :modes="false" :echelle-ref="0.45 / prep.periode_px"
            hors-zone :marge-vue="7"
          />
          <p v-else class="mt-4 text-[13px] text-muted">Lecture de l’empreinte…</p>
          <button v-if="prep" type="button" class="lien mt-2 text-[13px]" :disabled="occupe" @click="preparer()">
            Placement automatique
          </button>
        </section>

        <!-- 3. Le métal -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">03</span>
            <h2 class="text-[20px] font-medium">Le métal</h2>
          </div>
          <div class="mt-5 grid grid-cols-2 gap-px border border-line bg-line">
            <button
              v-for="m in METAUX" :key="m.id" type="button"
              class="flex items-center gap-3 bg-paper px-4 py-3 text-left transition-colors"
              :class="choix.metal === m.id ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              :aria-pressed="choix.metal === m.id"
              @click="choix.metal = m.id"
            >
              <span class="h-5 w-5 shrink-0 border border-line" :style="{ background: m.pastille }" />
              <span class="flex flex-col">
                <span class="text-[14px] text-ink">{{ m.nom }}</span>
                <span class="valeur text-[12px] text-txt">≈ {{ f(poids(m.densite), 1) }} g</span>
              </span>
            </button>
          </div>
        </section>

        <!-- 4. Les dimensions -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">04</span>
            <h2 class="text-[20px] font-medium">Les dimensions</h2>
          </div>

          <label class="champ-intitule mt-6" for="taille">Taille de doigt</label>
          <div class="mt-2 flex items-center gap-4">
            <select id="taille" v-model.number="choix.taille" class="champ w-32">
              <option v-for="t in TAILLES" :key="t" :value="t">{{ t }}</option>
            </select>
            <span class="text-[13px] text-txt">diamètre intérieur <span class="valeur">{{ f(diametre) }} mm</span></span>
          </div>

          <span class="champ-intitule mt-6">Largeur du fil</span>
          <div class="mt-2 grid grid-cols-3 gap-px border border-line bg-line">
            <button
              v-for="l in LARGEURS" :key="l.cote" type="button"
              class="bg-paper px-3 py-3 text-center"
              :class="choix.cote === l.cote ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              :aria-pressed="choix.cote === l.cote"
              @click="choix.cote = l.cote"
            >
              <span class="block text-[14px] text-ink">{{ l.nom }}</span>
              <span class="valeur block text-[12px] text-txt">{{ l.detail }}</span>
            </button>
          </div>

          <span class="champ-intitule mt-6">Relief de l’empreinte</span>
          <div class="mt-2 grid grid-cols-3 gap-px border border-line bg-line">
            <button
              v-for="r in RELIEFS" :key="r.h" type="button"
              class="bg-paper px-3 py-3 text-center"
              :class="choix.relief === r.h ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              :aria-pressed="choix.relief === r.h"
              @click="choix.relief = r.h"
            >
              <span class="block text-[14px] text-ink">{{ r.nom }}</span>
              <span class="valeur block text-[12px] text-txt">{{ r.detail }}</span>
            </button>
          </div>
          <p class="mt-2 text-[13px] text-txt">Marqué ou profond tiennent mieux au porter de tous les jours.</p>
        </section>

        <!-- Récapitulatif -->
        <section class="px-6 py-7 lg:px-9">
          <dl class="space-y-2 text-[14px]">
            <div class="flex justify-between"><dt>Métal</dt><dd>{{ metal.nom }}</dd></div>
            <div class="flex justify-between"><dt>Taille</dt><dd class="valeur">{{ choix.taille }} · Ø {{ f(diametre) }} mm</dd></div>
            <div class="flex justify-between"><dt>Fil</dt><dd class="valeur">{{ f(choix.cote, 1) }} mm · jusqu’à {{ f(largeurMax, 1) }} mm dans la torsion</dd></div>
            <div class="flex justify-between"><dt>Poids estimé</dt><dd class="valeur">{{ f(poids(metal.densite), 1) }} g</dd></div>
          </dl>
          <!-- ⚠️ PAS DE TÉLÉCHARGEMENT ICI : la bague part à l'atelier, qui fabrique.
               Le fichier ne quitte le serveur que pour l'atelier (/atelier). -->
          <button
            type="button" class="btn-primary mt-6 w-full"
            :disabled="!alliance || occupe"
            @click="fenetreEnvoi?.ouvrir()"
          >
            {{ alliance ? 'Envoyer ma bague à l’atelier' : 'Ajoutez d’abord votre empreinte' }}
          </button>
          <FenetreEnvoi ref="fenetreEnvoi" :resume="resume" :envoyer="envoyer" />
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
/* Barre qui défile : on ne connaît pas la durée, on montre que ça travaille. */
.barre-calcul::after {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 35%;
  background: var(--vert);
  animation: defile 1.1s ease-in-out infinite;
}
@keyframes defile {
  from { transform: translateX(-100%); }
  to { transform: translateX(290%); }
}
@media (prefers-reduced-motion: reduce) {
  .barre-calcul::after { animation: none; width: 100%; opacity: 0.6; }
}
</style>
