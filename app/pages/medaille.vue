<!-- La médaille à empreinte : les médailles du configurateur de
     rainbowantworkshop.fr (12 formes, 12, 16 ou 20 mm), construites depuis le
     contour du catalogue, et l'empreinte en relief sur la face.

     Même principe que la chevalière : le moteur Python traite l'empreinte une
     fois, la page construit la médaille et le relief (shared/medaille.ts), et
     Python refait le fichier de fabrication à l'envoi. -->
<script setup lang="ts">
import type { TextureRelief } from '~~/shared/alliance'
import { lecteurRelief, reliefSolide } from '~~/shared/chevaliere'
import {
  contourMedaille, corpsMedaille, debout, MARGE_TROU, trouMedaille, volumeGeometrie, zoneMedaille,
  type TailleMedaille,
} from '~~/shared/medaille'
import type { Piece } from '~~/shared/piece'

const marque = useMarque()
useHead({ title: `Médaille empreinte — ${marque.nom}` })

// — Le catalogue des médailles ———————————————————————————————————————
const { data: catalogue } = await useFetch<any>('/api/biblio/catalog-medaille.json', { key: 'cat-med' })
const produit = computed(() => catalogue.value?.products?.[0])
const EXCLUS = ['vermeil']
const metaux = computed(() => {
  const tous = catalogue.value?.metals ?? []
  return (produit.value?.metals ?? [])
    // Pas de vermeil ici, même si le catalogue du configurateur le propose
    // (Thomas, 16/11/2026).
    .filter((m: any) => !EXCLUS.includes(m.id))
    .map((m: any) => tous.find((t: any) => t.id === m.id)).filter(Boolean)
})
const epaisseur = computed(() => produit.value?.thickness ?? 1.4)

const RELIEFS = [
  { h: 0.2, nom: 'Délicat', detail: '0,20 mm' },
  { h: 0.3, nom: 'Marqué', detail: '0,30 mm' },
  { h: 0.4, nom: 'Profond', detail: '0,40 mm' },
]
const choix = reactive({ forme: 'LUN', taille: 16, hauteur: 0.3, metal: 'argent950' })
const forme = computed(() => produit.value?.shapes.find((s: any) => s.id === choix.forme))
const taille = computed<TailleMedaille | null>(() => forme.value?.sizes.find((t: any) => t.mm === choix.taille) ?? null)
const metal = computed(() => metaux.value.find((m: any) => m.id === choix.metal))
const teinte = computed(() => {
  const f0 = metal.value?.f0 ?? [0.95, 0.95, 0.93]
  return (Math.round(f0[0] * 255) << 16) | (Math.round(f0[1] * 255) << 8) | Math.round(f0[2] * 255)
})

// — Le corps ———————————————————————————————————————————————————————
// ⚠️ PAS AVANT QUE LA PAGE SOIT MONTÉE. La médaille se construit sans rien
// attendre ; prête dès l'hydratation, la vue 3D s'installait avant que son
// cadre existe (« Cannot read properties of undefined (reading 'appendChild') »)
// et la page tombait en erreur 500. La chevalière, elle, attendait son maillage.
const monte = ref(false)
onMounted(() => { monte.value = true })
const corps = computed(() => {
  if (!taille.value || !monte.value) return null
  const geo = corpsMedaille(taille.value, epaisseur.value, forme.value?.bail)
  const n = geo.getAttribute('position').count
  return {
    cle: `${choix.forme}-${choix.taille}`,
    positions: debout(geo.getAttribute('position').array as Float32Array),
    normales: debout(geo.getAttribute('normal').array as Float32Array),
    indices: Uint32Array.from({ length: n }, (_, i) => i),
    volume: volumeGeometrie(geo),
  }
})

// — L'empreinte ———————————————————————————————————————————————————
const depot = ref<{ id: string; nom: string; image: string } | null>(null)
const etat = ref<'vide' | 'envoi' | 'preparation' | 'pret' | 'erreur'>('vide')
const erreur = ref('')
const glisse = ref(false)
const prep = shallowRef<any>(null)
const texture = shallowRef<TextureRelief | null>(null)
const placement = ref<[number, number, number]>([0, 0, 0])
const mmParPx = ref(0.05)
const modeGravure = ref<'dans' | 'couvre'>('dans')
const editeur = ref<{ recentrer: () => void } | null>(null)
const periodeMm = computed(() => (prep.value ? mmParPx.value * prep.value.periode_px : 0.45))

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
watch(() => [choix.forme, choix.taille], async () => {
  await nextTick()
  editeur.value?.recentrer()
})

// — Le relief, construit ici ————————————————————————————————————————
const contour = computed(() => (taille.value ? contourMedaille(taille.value) : []))
const zone = computed(() => (taille.value ? zoneMedaille(taille.value) : []))
const trou = computed(() => {
  const t = taille.value ? trouMedaille(taille.value, forme.value?.bail) : null
  return t ? ([t[0], t[1], t[2] + MARGE_TROU] as [number, number, number]) : null
})
const relief = shallowRef<ReturnType<typeof reliefSolide> | null>(null)
let image = 0
watch(
  () => [texture.value, taille.value, choix.hauteur, mmParPx.value, placement.value] as const,
  () => {
    if (!import.meta.client || image) return
    image = requestAnimationFrame(() => {
      image = 0
      if (!texture.value || !taille.value || !prep.value) return
      const lire = lecteurRelief(placement.value, mmParPx.value, prep.value.hauteur_image, texture.value)
      relief.value = reliefSolide(zone.value, zone.value, (u, v) => choix.hauteur * lire(u, v), 0, 0.05, trou.value)
    })
  },
  { deep: true },
)

let numRelief = 0
const pieces = computed<Piece[] | null>(() => {
  if (!corps.value) return null
  const liste: Piece[] = [corps.value]
  if (relief.value && depot.value) {
    liste.push({ cle: `relief-${++numRelief}`, positions: debout(relief.value.positions), indices: relief.value.indices })
  }
  return liste
})

// — Poids ————————————————————————————————————————————————————————
const volume = computed(() => (corps.value ? corps.value.volume + (depot.value && relief.value ? relief.value.volume : 0) : null))
const poids = (d: number) => (volume.value ? (volume.value / 1000) * d : null)
const f = (x: number | null | undefined, d = 1) =>
  x == null ? '—' : x.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })

// — L'envoi ——————————————————————————————————————————————————————
const fenetreEnvoi = ref<{ ouvrir: () => void } | null>(null)
const resume = computed(() => [
  `Médaille empreinte · ${forme.value?.name ?? ''} ${choix.taille} mm`,
  `relief ${f(choix.hauteur, 2)} mm`,
  depot.value ? `crêtes ${f(periodeMm.value, 2)} mm` : null,
  metal.value?.name,
].filter(Boolean).join(' · '))

async function envoyer(fo: { nom_piece: string; nom: string; email: string; telephone: string; message: string }) {
  return await $fetch<{ piece: string; ref: string }>('/api/envoi', {
    method: 'POST',
    body: {
      type: 'medaille',
      id: depot.value!.id,
      marque: marque.id,
      piece: { nom: fo.nom_piece || 'Médaille empreinte' },
      contact: { nom: fo.nom, email: fo.email, telephone: fo.telephone, message: fo.message },
      choix: { resume: resume.value, metalNom: metal.value?.name, poids_g: poids(metal.value?.density ?? 0) },
      params: {
        forme: choix.forme, taille_medaille: choix.taille, hauteur_relief: choix.hauteur,
        periode_mm: periodeMm.value, placement_px: placement.value,
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
      <div class="relative h-[56vh] min-h-[320px] bg-paper-2 lg:sticky lg:top-0 lg:h-[calc(100vh-65px)]">
        <ClientOnly>
          <VueAlliance v-if="pieces" :pieces="pieces" :teinte="teinte" :direction="[0.15, 0.2, 1]" />
        </ClientOnly>
        <p v-if="occupe" class="absolute left-5 top-5 border border-line bg-paper px-3 py-1 text-[13px] text-txt">
          Lecture de votre empreinte…
        </p>
        <p class="absolute bottom-5 left-5 text-[13px] text-txt">Faites tourner la médaille du doigt ou de la souris.</p>
      </div>

      <aside class="border-line lg:border-l">
        <div class="border-b border-line px-6 pb-6 pt-8 lg:px-9">
          <p class="eyebrow">Médaille empreinte</p>
          <div class="filet-teinte mt-3" />
          <h1 class="mt-4 text-[32px]">Votre empreinte sur une médaille</h1>
        </div>

        <!-- 1. La médaille -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">01</span>
            <h2 class="text-[20px] font-medium">La médaille</h2>
          </div>
          <span class="champ-intitule mt-5">Forme</span>
          <div class="mt-2 grid grid-cols-4 gap-px border border-line bg-line">
            <button
              v-for="s in produit?.shapes ?? []" :key="s.id" type="button"
              class="flex flex-col items-center gap-1 bg-paper px-1 py-2"
              :class="choix.forme === s.id ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              :aria-pressed="choix.forme === s.id" :title="s.tagline"
              @click="choix.forme = s.id"
            >
              <svg :viewBox="`-1 -1 ${s.sizes[0].width + 2} ${s.sizes[0].height + 2}`" class="h-8 w-8">
                <path :d="s.sizes[0].d" fill="none" stroke="currentColor" :stroke-width="s.sizes[0].width / 20" fill-rule="evenodd" />
              </svg>
              <span class="text-center text-[11px] leading-tight text-txt">{{ s.name }}</span>
            </button>
          </div>

          <span class="champ-intitule mt-6">Taille</span>
          <div class="mt-2 grid grid-cols-3 gap-px border border-line bg-line">
            <button
              v-for="t in produit?.sizes ?? []" :key="t.mm" type="button" class="bg-paper px-3 py-3 text-[14px]"
              :class="choix.taille === t.mm ? 'outline outline-2 -outline-offset-2 outline-ink' : 'hover:bg-paper-2'"
              @click="choix.taille = t.mm"
            >
              {{ t.label }}
            </button>
          </div>
          <p class="mt-2 text-[13px] text-txt">{{ forme?.tagline }} {{ choix.taille }} mm {{ forme?.dimension }}, {{ f(epaisseur, 1) }} mm d’épaisseur.</p>
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
            <span class="champ-intitule mt-6">Placement sur la médaille</span>
            <EditeurGravure
              ref="editeur" v-model:placement="placement" v-model:mm-par-px="mmParPx" v-model:mode="modeGravure"
              class="mt-2"
              :image="prep.images.edition" :largeur="prep.edition.largeur" :hauteur="prep.edition.hauteur"
              :boite="prep.boite_empreinte" :contour="contour" :zone="zone" :periode-px="prep.periode_px"
            />
          </template>
        </section>

        <!-- 3. Le relief -->
        <section class="border-b border-line px-6 py-7 lg:px-9">
          <div class="flex items-baseline gap-3">
            <span class="valeur text-muted">03</span>
            <h2 class="text-[20px] font-medium">Le relief</h2>
          </div>
          <div class="mt-5 grid grid-cols-3 gap-px border border-line bg-line">
            <button
              v-for="r in RELIEFS" :key="r.h" type="button" class="bg-paper px-3 py-3 text-center"
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
          <p class="mt-2 text-[14px]">Poids estimé <span class="valeur">{{ f(poids(metal?.density ?? 0), 1) }} g</span>, sans l’anneau</p>
          <button
            type="button" class="btn-primary mt-6 w-full" :disabled="!depot || !relief || occupe"
            @click="fenetreEnvoi?.ouvrir()"
          >
            {{ depot ? 'Envoyer ma médaille à l’atelier' : 'Ajoutez d’abord votre empreinte' }}
          </button>
          <FenetreEnvoi ref="fenetreEnvoi" :resume="resume" :envoyer="envoyer" />
        </section>
      </aside>
    </div>
  </div>
</template>
