<!-- La chevalière à empreinte : une chevalière de la bibliothèque de
     rainbowantworkshop.fr (10 formes, 3 plateaux, creuse ou pleine, 17 tailles
     de doigt), et l'empreinte en relief sur son plateau.

     Comme l'alliance : le moteur Python traite l'empreinte une fois au dépôt,
     la page construit le relief et affiche la bague (shared/chevaliere.ts), et
     Python refait le fichier de fabrication à l'envoi — maillage de la
     bibliothèque et relief unis en un seul solide. -->
<script setup lang="ts">
import type { TextureRelief } from '~~/shared/alliance'
import {
  contourCentre, lecteurRelief, lireJrm, MARGE_PLEIN, reliefChevaliere, retrecir, type MaillageJrm, type TaillePlateau,
} from '~~/shared/chevaliere'
import type { Piece } from '~~/shared/piece'

const marque = useMarque()
useHead({ title: `Chevalière empreinte — ${marque.nom}` })

// — La bibliothèque ——————————————————————————————————————————————————
const { data: catalogue } = await useFetch<any>('/api/biblio/catalog-chevaliere.json', { key: 'cat-chev' })
const produit = computed(() => catalogue.value?.products?.[0])
const metaux = computed(() => {
  const tous = catalogue.value?.metals ?? []
  return (produit.value?.metals ?? []).map((m: any) => tous.find((t: any) => t.id === m.id)).filter(Boolean)
})

const RELIEFS_PLEIN = [
  { h: 0.2, nom: 'Délicat', detail: '0,20 mm' },
  { h: 0.3, nom: 'Marqué', detail: '0,30 mm' },
  { h: 0.4, nom: 'Profond', detail: '0,40 mm' },
]
const choix = reactive({
  forme: 'ECU', plateau: 14, remplissage: 'creuse' as 'creuse' | 'pleine',
  surface: 'godet' as 'godet' | 'plein', hauteur: 0.3, doigt: 55, metal: 'or18j',
})

const forme = computed(() => produit.value?.shapes.find((s: any) => s.id === choix.forme))
const taille = computed<TaillePlateau | null>(() => forme.value?.sizes.find((t: any) => t.mm === choix.plateau) ?? null)
const doigtMesh = computed(() => {
  const p = produit.value
  if (!p) return null
  const i = p.fingerSizes.indexOf(choix.doigt)
  return i >= 0 ? p.fingerMeshes[i] : null
})
const diametre = computed(() => {
  const p = produit.value
  const i = p ? p.fingerSizes.indexOf(choix.doigt) : -1
  return i >= 0 ? p.fingerDiameters[i] : null
})
const metal = computed(() => metaux.value.find((m: any) => m.id === choix.metal))
const teinte = computed(() => {
  const f0 = metal.value?.f0 ?? [0.9, 0.75, 0.45]
  return (Math.round(f0[0] * 255) << 16) | (Math.round(f0[1] * 255) << 8) | Math.round(f0[2] * 255)
})

// — La chevalière choisie ————————————————————————————————————————————
const base = shallowRef<{ chemin: string; m: MaillageJrm } | null>(null)
const chargeBase = ref(false)
const cheminBase = computed(() => doigtMesh.value
  ? `rings/${choix.forme}/${choix.plateau}/${choix.remplissage}/${doigtMesh.value}/${choix.surface === 'godet' ? 'creux' : 'lisse'}.jrm`
  : null)
const memoire = new Map<string, MaillageJrm>()
watch(cheminBase, async (c) => {
  if (!c || !import.meta.client) return
  if (memoire.has(c)) { base.value = { chemin: c, m: memoire.get(c)! }; return }
  chargeBase.value = true
  try {
    const buf = await $fetch<ArrayBuffer>(`/api/biblio/${c}`, { responseType: 'arrayBuffer' })
    const m = lireJrm(buf)
    memoire.set(c, m)
    if (cheminBase.value === c) base.value = { chemin: c, m }
  } finally {
    if (cheminBase.value === c) chargeBase.value = false
  }
}, { immediate: true })

// — L'empreinte ———————————————————————————————————————————————————
const depot = ref<{ id: string; nom: string; image: string } | null>(null)
const etat = ref<'vide' | 'envoi' | 'preparation' | 'pret' | 'erreur'>('vide')
const erreur = ref('')
const glisse = ref(false)
const prep = shallowRef<any>(null)
const texture = shallowRef<TextureRelief | null>(null)
const placement = ref<[number, number, number]>([0, 0, 0])

async function deposer(fichier?: File | null, demo = false) {
  if (!fichier && !demo) return
  erreur.value = ''
  etat.value = 'envoi'
  try {
    const fd = new FormData()
    if (fichier) fd.append('image', fichier)
    depot.value = await $fetch('/api/empreinte' + (demo ? '?demo=1' : ''), { method: 'POST', body: fd })
    etat.value = 'preparation'
    const r = await $fetch<any>('/api/calcul', {
      method: 'POST', body: { id: depot.value!.id, action: 'preparer', params: { periode_mm: 0.45 } },
    })
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
    placement.value = [r.centre_empreinte[0], r.centre_empreinte[1], 0]
    mmParPx.value = 0.45 / r.periode_px
    // Comme le configurateur : l'empreinte arrive entière, dans le plateau.
    await nextTick()
    editeur.value?.recentrer()
    etat.value = 'pret'
  } catch (e: any) {
    etat.value = 'erreur'
    const m = e?.data?.statusMessage ?? e?.statusMessage ?? ''
    erreur.value = /empreinte|crête/i.test(m)
      ? 'Nous n’avons pas trouvé d’empreinte nette sur cette photo. Essayez une image plus contrastée, l’empreinte bien à plat.'
      : m || 'Le calcul n’a pas abouti. Réessayez dans un instant.'
  }
}

// — Le relief, construit ici ————————————————————————————————————————
// L'échelle (mm par pixel) et le placement viennent de l'éditeur de gravure ;
// l'écart des crêtes sur la bague en découle (échelle × période en pixels).
const mmParPx = ref(0.05)
const modeGravure = ref<'dans' | 'couvre'>('dans')
const editeur = ref<{ recentrer: () => void } | null>(null)
const periodeMm = computed(() => (prep.value ? mmParPx.value * prep.value.periode_px : 0.45))
// Une autre forme, un autre plateau ou un autre relief : l'empreinte se
// recale dans la nouvelle zone, comme au premier dépôt.
watch(() => [choix.forme, choix.plateau, choix.surface], async () => {
  await nextTick()
  editeur.value?.recentrer()
})
const relief = shallowRef<ReturnType<typeof reliefChevaliere> | null>(null)
let image = 0
// Une reconstruction par image au plus : glisser le plateau envoie des dizaines
// d'évènements par seconde, et chacun referait tout le relief.
watch(
  () => [texture.value, taille.value, choix.surface, choix.hauteur, mmParPx.value, placement.value] as const,
  () => {
    if (!import.meta.client || image) return
    image = requestAnimationFrame(() => {
      image = 0
      if (!texture.value || !taille.value || !prep.value) return
      const lire = lecteurRelief(placement.value, mmParPx.value, prep.value.hauteur_image, texture.value)
      // 0,04 mm : une empreinte entière dans le godet a des crêtes de 0,25 mm ; à
      // 0,06 mm l'aperçu n'en prenait que 4 points et sortait bruité.
      relief.value = reliefChevaliere(taille.value, choix.surface, choix.hauteur, lire, 0.04)
    })
  },
  { deep: true },
)

let numRelief = 0
const pieces = computed<Piece[] | null>(() => {
  if (!base.value) return null
  const liste: Piece[] = [{ cle: base.value.chemin, ...base.value.m }]
  if (relief.value && depot.value) {
    liste.push({ cle: `relief-${++numRelief}`, positions: relief.value.solide.positions, indices: relief.value.solide.indices })
  }
  return liste
})

const contourPlateau = computed(() => (taille.value ? contourCentre(taille.value, 'plateau') : []))
const zoneGravure = computed(() => {
  if (!taille.value) return []
  return choix.surface === 'godet' ? contourCentre(taille.value, 'cup') : retrecir(contourPlateau.value, MARGE_PLEIN)
})

// — Poids ————————————————————————————————————————————————————————
// Le catalogue donne le volume de chaque maillage ; le relief s'y ajoute.
const volume = computed(() => {
  const t = taille.value
  if (!t || !doigtMesh.value) return null
  const v = t.volumes?.[choix.remplissage]?.[doigtMesh.value]
  if (!v) return null
  return (choix.surface === 'godet' ? v.email : v.lisse) + (depot.value && relief.value ? relief.value.solide.volume : 0)
})
const poids = (d: number) => (volume.value ? (volume.value / 1000) * d : null)
const f = (x: number | null | undefined, d = 1) =>
  x == null ? '—' : x.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })

// — L'envoi ——————————————————————————————————————————————————————
const fenetreEnvoi = ref<{ ouvrir: () => void } | null>(null)
const resume = computed(() => [
  `Chevalière empreinte · ${forme.value?.name ?? ''} ${choix.plateau} mm`,
  choix.remplissage === 'creuse' ? 'creuse' : 'pleine',
  `${choix.surface === 'godet' ? 'empreinte dans le godet' : 'empreinte sur le plateau'}, relief ${f(choix.hauteur, 2)} mm`,
  depot.value ? `crêtes ${f(periodeMm.value, 2)} mm` : null,
  metal.value?.name, `taille ${choix.doigt}`,
].filter(Boolean).join(' · '))

async function envoyer(fo: { nom_piece: string; nom: string; email: string; telephone: string; message: string }) {
  return await $fetch<{ piece: string; ref: string }>('/api/envoi', {
    method: 'POST',
    body: {
      type: 'chevaliere',
      id: depot.value!.id,
      marque: marque.id,
      piece: { nom: fo.nom_piece || 'Chevalière empreinte' },
      contact: { nom: fo.nom, email: fo.email, telephone: fo.telephone, message: fo.message },
      choix: { resume: resume.value, metalNom: metal.value?.name, poids_g: poids(metal.value?.density ?? 0) },
      params: {
        forme: choix.forme, plateau: choix.plateau, remplissage: choix.remplissage, doigt: choix.doigt,
        surface: choix.surface, hauteur_relief: choix.hauteur, periode_mm: periodeMm.value,
        placement_px: placement.value,
      },
    },
  })
}
const occupe = computed(() => etat.value === 'envoi' || etat.value === 'preparation')
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <EnTete />

    <div class="grid flex-1 items-start lg:grid-cols-[1fr_460px]">
      <!-- ─── La bague ─── -->
      <div class="relative h-[56vh] min-h-[320px] bg-paper-2 lg:sticky lg:top-0 lg:h-[calc(100vh-65px)]">
        <ClientOnly>
          <VueAlliance v-if="pieces" :pieces="pieces" :teinte="teinte" />
        </ClientOnly>
        <p v-if="occupe" class="absolute left-5 top-5 border border-line bg-paper px-3 py-1 text-[13px] text-txt">
          Lecture de votre empreinte…
        </p>
        <p v-else-if="chargeBase" class="absolute left-5 top-5 border border-line bg-paper px-3 py-1 text-[13px] text-txt">
          Chargement de la chevalière…
        </p>
        <p class="absolute bottom-5 left-5 text-[13px] text-txt">Faites tourner la bague du doigt ou de la souris.</p>
      </div>

      <!-- ─── Les choix ─── -->
      <aside class="border-line lg:border-l">
        <div class="border-b border-line px-6 pb-6 pt-8 lg:px-9">
          <p class="eyebrow">Chevalière empreinte</p>
          <div class="filet-teinte mt-3" />
          <h1 class="mt-4 text-[32px]">Votre empreinte sur le plateau</h1>
        </div>

        <!-- 1. La chevalière -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">01</span>
            <h2 class="text-[20px] font-medium">La chevalière</h2>
          </div>
          <span class="champ-intitule mt-5">Forme du plateau</span>
          <div class="mt-2 grid grid-cols-5 gap-px border border-line bg-line">
            <button
              v-for="s in produit?.shapes ?? []" :key="s.id" type="button"
              class="flex flex-col items-center gap-1 bg-paper px-1 py-2"
              :class="choix.forme === s.id ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              :aria-pressed="choix.forme === s.id" :title="s.name"
              @click="choix.forme = s.id"
            >
              <svg viewBox="0 0 100 100" class="h-8 w-8"><path :d="s.icon" fill="none" stroke="currentColor" stroke-width="4" /></svg>
              <span class="text-[11px] leading-tight text-txt">{{ s.name }}</span>
            </button>
          </div>

          <span class="champ-intitule mt-6">Taille du plateau</span>
          <div class="mt-2 grid grid-cols-3 gap-px border border-line bg-line">
            <button
              v-for="p in produit?.plateaux ?? []" :key="p.mm" type="button" class="bg-paper px-3 py-3 text-[14px]"
              :class="choix.plateau === p.mm ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              @click="choix.plateau = p.mm"
            >
              {{ p.label }}
            </button>
          </div>

          <span class="champ-intitule mt-6">Corps</span>
          <div class="mt-2 grid grid-cols-2 gap-px border border-line bg-line">
            <button
              v-for="r in produit?.fills ?? []" :key="r.id" type="button" class="bg-paper px-3 py-3 text-left"
              :class="choix.remplissage === r.id ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              @click="choix.remplissage = r.id"
            >
              <span class="block text-[14px] text-ink">{{ r.name }}</span>
              <span class="block text-[12px] text-txt">{{ r.hint }}</span>
            </button>
          </div>

          <label class="champ-intitule mt-6" for="doigt">Taille de doigt</label>
          <div class="mt-2 flex items-center gap-4">
            <select id="doigt" v-model.number="choix.doigt" class="champ w-32">
              <option v-for="t in produit?.fingerSizes ?? []" :key="t" :value="t">{{ t }}</option>
            </select>
            <span class="text-[13px] text-txt">diamètre intérieur <span class="valeur">{{ f(diametre) }} mm</span></span>
          </div>
        </section>

        <!-- 2. L'empreinte -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">02</span>
            <h2 class="text-[20px] font-medium">Votre empreinte</h2>
          </div>
          <label
            class="mt-5 flex cursor-pointer items-center gap-4 border border-dashed px-4 py-4 transition-colors"
            :class="glisse ? 'border-ink bg-vert-pale' : 'border-line bg-paper-2 hover:border-ink'"
            @dragover.prevent="glisse = true" @dragleave="glisse = false"
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

          <template v-if="prep && taille">
            <span class="champ-intitule mt-6">Placement sur le plateau</span>
            <EditeurGravure
              ref="editeur" v-model:placement="placement" v-model:mm-par-px="mmParPx" v-model:mode="modeGravure"
              class="mt-2"
              :image="prep.images.edition" :largeur="prep.edition.largeur" :hauteur="prep.edition.hauteur"
              :boite="prep.boite_empreinte" :contour="contourPlateau" :zone="zoneGravure" :periode-px="prep.periode_px"
            />
          </template>
        </section>

        <!-- 3. Le relief -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">03</span>
            <h2 class="text-[20px] font-medium">Le relief</h2>
          </div>
          <div class="mt-5 grid grid-cols-2 gap-px border border-line bg-line">
            <button
              type="button" class="bg-paper px-3 py-3 text-left"
              :class="choix.surface === 'godet' ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              @click="choix.surface = 'godet'"
            >
              <span class="block text-[14px] text-ink">Dans le godet</span>
              <span class="block text-[12px] text-txt">Plateau creusé, le relief juste sous le bord, à l’abri des chocs</span>
            </button>
            <button
              type="button" class="bg-paper px-3 py-3 text-left"
              :class="choix.surface === 'plein' ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              @click="choix.surface = 'plein'"
            >
              <span class="block text-[14px] text-ink">Sur le plateau</span>
              <span class="block text-[12px] text-txt">Plateau plein, les crêtes en saillie</span>
            </button>
          </div>
          <div class="mt-3 grid grid-cols-3 gap-px border border-line bg-line">
            <button
              v-for="r in RELIEFS_PLEIN" :key="r.h" type="button" class="bg-paper px-3 py-3 text-center"
              :class="choix.hauteur === r.h ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              @click="choix.hauteur = r.h"
            >
              <span class="block text-[14px] text-ink">{{ r.nom }}</span>
              <span class="valeur block text-[12px] text-txt">{{ r.detail }}</span>
            </button>
          </div>
        </section>

        <!-- 4. Le métal -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">04</span>
            <h2 class="text-[20px] font-medium">Le métal</h2>
          </div>
          <div class="mt-5 grid grid-cols-2 gap-px border border-line bg-line">
            <button
              v-for="m in metaux" :key="m.id" type="button" class="flex items-center gap-3 bg-paper px-4 py-3 text-left"
              :class="choix.metal === m.id ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              @click="choix.metal = m.id"
            >
              <span class="h-5 w-5 shrink-0 border border-line" :style="{ background: m.swatch }" />
              <span class="flex flex-col">
                <span class="text-[14px] text-ink">{{ m.name }}</span>
                <span class="valeur text-[12px] text-txt">≈ {{ f(poids(m.density), 1) }} g</span>
              </span>
            </button>
          </div>
        </section>

        <section class="px-6 py-7 lg:px-9">
          <p class="text-[14px] text-txt">{{ resume }}</p>
          <p class="mt-2 text-[14px]">Poids estimé <span class="valeur">{{ f(poids(metal?.density ?? 0), 1) }} g</span></p>
          <button
            type="button" class="btn-primary mt-6 w-full" :disabled="!depot || !relief || occupe"
            @click="fenetreEnvoi?.ouvrir()"
          >
            {{ depot ? 'Envoyer ma chevalière à l’atelier' : 'Ajoutez d’abord votre empreinte' }}
          </button>
          <FenetreEnvoi ref="fenetreEnvoi" :resume="resume" :envoyer="envoyer" />
        </section>
      </aside>
    </div>
  </div>
</template>
