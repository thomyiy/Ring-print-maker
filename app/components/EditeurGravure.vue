<!-- L'empreinte posée sur le plateau, à la manière de l'éditeur de gravure du
     configurateur de rainbowantworkshop.fr : le plateau reste fixe, c'est
     l'image qu'on déplace, qu'on agrandit par les coins et qu'on tourne par la
     poignée, avec les mêmes curseurs Taille et Rotation et les deux modes
     « Dans le plateau » / « Plateau dans l'image ».

     Sous le capot, rien ne change pour la géométrie : le placement reste
     [cx, cy, angle°] en pixels de l'image d'édition et l'échelle en mm par
     pixel, le repère que relisent `lecteurRelief` et `lecteur_relief`. Un
     point (u, v) du plateau correspond au pixel C + R(angle)·(u, v)/échelle ;
     l'éditeur dessine simplement l'inverse. -->
<script setup lang="ts">
import type { Point } from '~~/shared/chevaliere'

const props = defineProps<{
  image: string
  largeur: number
  hauteur: number
  boite: [number, number, number, number] // cadre de l'empreinte, px (y vers le bas)
  contour: Point[]                        // plateau, mm centrés
  zone: Point[]                           // là où les crêtes montent (godet ou plateau rétréci)
  periodePx: number
}>()
const placement = defineModel<[number, number, number]>('placement', { required: true })
const mmParPx = defineModel<number>('mmParPx', { required: true })
const mode = defineModel<'dans' | 'couvre'>('mode', { default: 'dans' })

type P = [number, number]
const rad = (d: number) => (d * Math.PI) / 180

// — Correspondances image ⇄ plateau ————————————————————————————————
function versPlateau(q: P): P {
  const [cx, cy, ang] = placement.value
  const a = rad(-ang), k = mmParPx.value
  const dx = q[0] - cx, dy = q[1] - cy
  return [(Math.cos(a) * dx - Math.sin(a) * dy) * k, (Math.sin(a) * dx + Math.cos(a) * dy) * k]
}
/** Le centre C qui envoie le pixel q sur le point u du plateau. */
function centrePour(q: P, u: P, ang: number, k: number): [number, number, number] {
  const a = rad(ang)
  return [q[0] - (Math.cos(a) * u[0] - Math.sin(a) * u[1]) / k, q[1] - (Math.sin(a) * u[0] + Math.cos(a) * u[1]) / k, ang]
}

const centreBoite = computed<P>(() => [(props.boite[0] + props.boite[2]) / 2, (props.boite[1] + props.boite[3]) / 2])
const coinsBoite = computed(() => {
  const [x0, y0, x1, y1] = props.boite
  return ([[x0, y0], [x1, y0], [x1, y1], [x0, y1]] as P[]).map(versPlateau)
})
const poignee = computed(() => {
  const [x0, y0, x1] = props.boite
  const haut = versPlateau([(x0 + x1) / 2, y0])
  const c = versPlateau(centreBoite.value)
  const dx = haut[0] - c[0], dy = haut[1] - c[1]
  const l = Math.hypot(dx, dy) || 1
  return { pied: haut, tete: [haut[0] + (dx / l) * 2, haut[1] + (dy / l) * 2] as P }
})
const transformImage = computed(() => {
  const [cx, cy, ang] = placement.value
  return `rotate(${-ang}) scale(${mmParPx.value}) translate(${-cx} ${-cy})`
})

// — Le cadre de la vue : le plateau, avec de quoi voir la poignée ————————————
const vue = computed(() => {
  const xs = props.contour.map((p) => p[0]), ys = props.contour.map((p) => p[1])
  const m = 3.2
  return { x: Math.min(...xs) - m, y: Math.min(...ys) - m, l: Math.max(...xs) - Math.min(...xs) + 2 * m, h: Math.max(...ys) - Math.min(...ys) + 2 * m }
})
const chaine = (pts: P[]) => pts.map((p) => `${p[0].toFixed(3)},${p[1].toFixed(3)}`).join(' ')

// — Modes et échelle de référence ————————————————————————————————————
/** L'échelle à 100 % : l'empreinte tient dans la zone (« dans »), ou la
 *  couvre entièrement (« couvre »). */
function echellePour(m: 'dans' | 'couvre') {
  const xs = props.zone.map((p) => p[0]), ys = props.zone.map((p) => p[1])
  const lz = Math.max(...xs) - Math.min(...xs), hz = Math.max(...ys) - Math.min(...ys)
  const lb = props.boite[2] - props.boite[0], hb = props.boite[3] - props.boite[1]
  return m === 'dans' ? Math.min(lz / lb, hz / hb) * 0.96 : Math.max(lz / lb, hz / hb) * 1.04
}
const echelleBase = computed(() => echellePour(mode.value))
function recentrer(k: number, ang = placement.value[2]) {
  mmParPx.value = k
  placement.value = centrePour(centreBoite.value, [0, 0], ang, k)
}
// ⚠️ L'ÉCHELLE DU MODE CHOISI, PAS CELLE DE `mode.value` : le modèle ne revient
// du parent qu'au rendu suivant, et « Plateau dans l'image » se recalait sur
// l'échelle de « Dans le plateau » (86 % au lieu de 100 %, mesuré à l'essai).
function choisirMode(m: 'dans' | 'couvre') {
  mode.value = m
  recentrer(echellePour(m))
}
defineExpose({ recentrer: () => recentrer(echelleBase.value) })

const taille = computed({
  get: () => Math.round((mmParPx.value / echelleBase.value) * 100),
  set: (pc: number) => {
    const c = versPlateau(centreBoite.value)
    const k = (echelleBase.value * pc) / 100
    mmParPx.value = k
    placement.value = centrePour(centreBoite.value, c, placement.value[2], k)
  },
})
const rotation = computed({
  get: () => Math.round(placement.value[2]),
  set: (a: number) => {
    const c = versPlateau(centreBoite.value)
    placement.value = centrePour(centreBoite.value, c, a, mmParPx.value)
  },
})
function tailleReelle() {
  const c = versPlateau(centreBoite.value)
  const k = 0.45 / props.periodePx
  mmParPx.value = k
  placement.value = centrePour(centreBoite.value, c, placement.value[2], k)
}

// — Gestes ———————————————————————————————————————————————————————————
const svg = ref<SVGSVGElement>()
let geste: null | { quoi: 'corps' | 'coin' | 'rotation'; p: P; pl: [number, number, number]; k: number; c: P } = null
function versMm(ev: PointerEvent): P {
  const pt = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(svg.value!.getScreenCTM()!.inverse())
  return [pt.x, pt.y]
}
function saisir(quoi: 'corps' | 'coin' | 'rotation', ev: PointerEvent) {
  ;(ev.currentTarget as Element).setPointerCapture(ev.pointerId)
  geste = { quoi, p: versMm(ev), pl: [...placement.value] as [number, number, number], k: mmParPx.value, c: versPlateau(centreBoite.value) }
}
function bouger(ev: PointerEvent) {
  if (!geste) return
  const p = versMm(ev)
  const g = geste
  if (g.quoi === 'corps') {
    const u: P = [g.c[0] + p[0] - g.p[0], g.c[1] + p[1] - g.p[1]]
    placement.value = centrePour(centreBoite.value, u, g.pl[2], g.k)
  } else if (g.quoi === 'coin') {
    const d0 = Math.hypot(g.p[0] - g.c[0], g.p[1] - g.c[1]) || 1
    const d1 = Math.hypot(p[0] - g.c[0], p[1] - g.c[1])
    const k = Math.min(Math.max((g.k * d1) / d0, echelleBase.value * 0.2), echelleBase.value * 3)
    mmParPx.value = k
    placement.value = centrePour(centreBoite.value, g.c, g.pl[2], k)
  } else {
    let a = (Math.atan2(-(p[0] - g.c[0]), -(p[1] - g.c[1])) * 180) / Math.PI
    const r = Math.round(a / 15) * 15
    if (Math.abs(a - r) < 3) a = r // aimanté tous les 15°
    placement.value = centrePour(centreBoite.value, g.c, a, g.k)
  }
}
function lacher() { geste = null }

// — Ce que l'on dit ——————————————————————————————————————————————————
const dimensions = computed(() => {
  const k = mmParPx.value
  return [(props.boite[2] - props.boite[0]) * k, (props.boite[3] - props.boite[1]) * k]
})
const periodeMm = computed(() => mmParPx.value * props.periodePx)
const f = (x: number, d = 1) => x.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
const idClip = useId()
</script>

<template>
  <div>
    <div class="grid grid-cols-2 border border-line">
      <button
        type="button" class="h-9 text-[13px]" :class="mode === 'dans' ? 'bg-ink text-paper' : 'bg-paper text-txt hover:bg-paper-2'"
        @click="choisirMode('dans')"
      >Dans le plateau</button>
      <button
        type="button" class="h-9 border-l border-line text-[13px]" :class="mode === 'couvre' ? 'bg-ink text-paper' : 'bg-paper text-txt hover:bg-paper-2'"
        @click="choisirMode('couvre')"
      >Plateau dans l’image</button>
    </div>

    <div class="relative mt-3 border border-line bg-paper-2">
      <svg
        ref="svg" :viewBox="`${vue.x} ${vue.y} ${vue.l} ${vue.h}`" class="block h-auto w-full touch-none select-none"
        @pointermove="bouger" @pointerup="lacher" @pointercancel="lacher"
      >
        <defs>
          <clipPath :id="idClip"><polygon :points="chaine(zone)" /></clipPath>
        </defs>
        <polygon :points="chaine(contour)" fill="white" stroke="#000" stroke-width="0.08" />
        <g :clip-path="`url(#${idClip})`">
          <image :href="image" x="0" y="0" :width="largeur" :height="hauteur" :transform="transformImage" />
        </g>
        <polygon
          v-if="zone !== contour" :points="chaine(zone)" fill="none" stroke="#A6A6A6"
          stroke-width="0.05" stroke-dasharray="0.3 0.3" pointer-events="none"
        />
        <!-- Le cadre de l'empreinte : on l'attrape pour la déplacer. -->
        <polygon
          :points="chaine(coinsBoite)" fill="transparent" stroke="#000" stroke-width="0.06"
          stroke-dasharray="0.35 0.25" class="cursor-move" @pointerdown="saisir('corps', $event)"
        />
        <line
          :x1="poignee.pied[0]" :y1="poignee.pied[1]" :x2="poignee.tete[0]" :y2="poignee.tete[1]"
          stroke="#000" stroke-width="0.06" pointer-events="none"
        />
        <circle
          :cx="poignee.tete[0]" :cy="poignee.tete[1]" r="0.5" fill="white" stroke="#000" stroke-width="0.07"
          class="cursor-grab" @pointerdown="saisir('rotation', $event)"
        />
        <rect
          v-for="(c, i) in coinsBoite" :key="i" :x="c[0] - 0.4" :y="c[1] - 0.4" width="0.8" height="0.8"
          fill="white" stroke="#000" stroke-width="0.07" class="cursor-nwse-resize" @pointerdown="saisir('coin', $event)"
        />
      </svg>
      <span class="valeur absolute bottom-2 left-3 text-[11px] text-txt">{{ f(dimensions[0]!) }} × {{ f(dimensions[1]!) }} mm</span>
    </div>

    <div class="mt-4 grid grid-cols-[80px_1fr_56px] items-center gap-3 text-[14px]">
      <label for="g-taille">Taille</label>
      <input id="g-taille" v-model.number="taille" type="range" min="20" max="300" step="1">
      <span class="valeur text-right text-txt">{{ taille }} %</span>
      <label for="g-rot">Rotation</label>
      <input id="g-rot" v-model.number="rotation" type="range" min="-180" max="180" step="1">
      <span class="valeur text-right text-txt">{{ rotation }}°</span>
    </div>
    <p class="mt-3 text-[13px] text-txt">
      Écart des crêtes <span class="valeur">{{ f(periodeMm, 2) }} mm</span>
      <span v-if="periodeMm < 0.25" class="text-framboise"> — trop fines pour bien sortir à la fonte, agrandissez</span>.
      <button type="button" class="lien ml-1" @click="tailleReelle">Taille réelle</button>
    </p>
  </div>
</template>
