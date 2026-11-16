<!-- La page client : une photo d'empreinte, un métal, des dimensions, et la
     bague en trois dimensions. Tout le reste — cadrage de la bande, traitement
     de l'image, maillage — se règle par défaut ; l'atelier garde la main sur
     /atelier. -->
<script setup lang="ts">
useHead({ title: 'Alliance empreinte — Rainbow Ant Workshop' })

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

const choix = reactive({ metal: 'or-jaune', taille: 54, cote: 1.8, relief: 0.25 })
const metal = computed(() => METAUX.find((m) => m.id === choix.metal)!)

// — L'empreinte ———————————————————————————————————————————————————
const depot = ref<{ id: string; nom: string; image: string } | null>(null)
const etat = ref<'vide' | 'envoi' | 'calcul' | 'pret' | 'erreur'>('vide')
const erreur = ref('')
const resultat = ref<any>(null)
const glisse = ref(false)

async function deposer(fichier?: File | null, demo = false) {
  if (!fichier && !demo) return
  erreur.value = ''
  etat.value = 'envoi'
  try {
    const fd = new FormData()
    if (fichier) fd.append('image', fichier)
    depot.value = await $fetch('/api/empreinte' + (demo ? '?demo=1' : ''), { method: 'POST', body: fd })
    await calculer()
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

// Le dernier calcul demandé gagne : un réglage changé pendant un calcul en
// relance un, et la réponse du précédent est ignorée.
let numero = 0
async function calculer() {
  if (!depot.value) return
  const n = ++numero
  etat.value = 'calcul'
  try {
    const r = await $fetch<any>('/api/calcul', {
      method: 'POST',
      body: {
        id: depot.value.id,
        action: 'generer',
        leger: true,
        params: {
          taille: choix.taille,
          diametre_interieur: Math.round((choix.taille / Math.PI) * 10) / 10,
          cote: choix.cote,
          hauteur_relief: choix.relief,
          // Entre l'aperçu et la fabrication : à 720 × 26 les crêtes sortaient
          // en dents de scie à l'écran, et le client jugeait l'empreinte là-dessus.
          n_sections: 1080,
          n_face: 40,
        },
      },
    })
    if (n !== numero) return
    resultat.value = r
    etat.value = 'pret'
  } catch (e) {
    if (n === numero) montrerErreur(e)
  }
}

// Le métal ne change que la teinte et le poids : pas de recalcul.
let minuterie: ReturnType<typeof setTimeout> | undefined
watch(() => [choix.taille, choix.cote, choix.relief], () => {
  clearTimeout(minuterie)
  if (depot.value) minuterie = setTimeout(calculer, 400)
})

const volume = computed(() => resultat.value?.controles?.volume_mm3 as number | undefined)
const poids = (d: number) => (volume.value ? (volume.value / 1000) * d : null)
const f = (x: number | null | undefined, d = 1) =>
  x == null ? '—' : x.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
const diametre = computed(() => Math.round((choix.taille / Math.PI) * 10) / 10)
const largeurMax = computed(() => resultat.value?.controles?.largeur_max as number | undefined)
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="border-b border-line">
      <div class="flex items-center justify-between px-5 py-4 lg:px-10">
        <div class="flex items-center gap-3">
          <img src="/logo-mark.png" alt="" class="h-8 w-auto">
          <span class="text-[17px] font-medium tracking-tight">Rainbow Ant Workshop</span>
        </div>
        <NuxtLink to="/atelier" class="text-[13px] text-muted hover:text-ink">Atelier</NuxtLink>
      </div>
    </header>

    <div class="grid flex-1 items-start lg:grid-cols-[1fr_440px]">
      <!-- ─── La bague ─── -->
      <div class="relative min-h-[56vh] bg-paper-2 lg:sticky lg:top-0 lg:h-[calc(100vh-65px)]">
        <ClientOnly>
          <VueAlliance v-if="resultat?.stl" :url="resultat.stl" :teinte="metal.teinte" />
        </ClientOnly>

        <div v-if="!resultat" class="absolute inset-0 flex flex-col items-center justify-center px-8 text-center">
          <p class="eyebrow">Alliance empreinte</p>
          <div class="filet-teinte mx-auto mt-3" />
          <h1 class="mt-5 text-[40px] sm:text-[52px]">Votre empreinte, en relief</h1>
          <p class="mx-auto mt-4 max-w-[52ch]">
            Un fil carré qui fait un demi-tour sur le dessus de la main. Sur la face qui passe
            au sommet, les crêtes de votre empreinte, en relief dans le métal.
          </p>
          <p v-if="etat === 'envoi' || etat === 'calcul'" class="eyebrow mt-8">Votre bague se dessine…</p>
        </div>

        <p
          v-if="resultat && etat === 'calcul'"
          class="absolute left-5 top-5 border border-line bg-paper px-3 py-1 text-[13px] text-txt"
        >
          Mise à jour…
        </p>
        <p v-if="resultat" class="absolute bottom-5 left-5 text-[13px] text-txt">
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

        <!-- 2. Le métal -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">02</span>
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

        <!-- 3. Les dimensions -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">03</span>
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
          <a
            v-if="resultat?.stl"
            :href="resultat.stl"
            download="alliance-empreinte.stl"
            class="btn-primary mt-6 w-full"
          >
            Télécharger le fichier 3D
          </a>
          <button v-else type="button" class="btn-primary mt-6 w-full" disabled>
            Ajoutez d’abord votre empreinte
          </button>
        </section>
      </aside>
    </div>
  </div>
</template>
