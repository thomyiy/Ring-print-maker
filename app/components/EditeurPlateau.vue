<!-- Le placement de l'empreinte sur le plateau d'une chevalière.

     Le contour du plateau est posé sur l'empreinte traitée, à l'échelle réelle :
     on le glisse pour choisir la zone, la poignée le fait tourner. Le placement
     est [cx, cy, angle°] en pixels de l'image d'édition (y vers le bas) — le
     repère que relisent `lecteurRelief` (navigateur) et `lecteur_relief`
     (Python). -->
<script setup lang="ts">
import type { Point } from '~~/shared/chevaliere'

const props = defineProps<{
  image: string
  largeur: number
  hauteur: number
  contour: Point[]       // mm, centré, v vers le bas
  godet?: Point[] | null // mm, centré
  mmParPx: number
}>()
const placement = defineModel<[number, number, number]>({ required: true })

const svg = ref<SVGSVGElement>()
const glisse = ref<null | 'corps' | 'rotation'>(null)
let depart: { p: [number, number]; pl: [number, number, number] } | null = null

function versImage(ev: PointerEvent): [number, number] {
  const pt = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(svg.value!.getScreenCTM()!.inverse())
  return [pt.x, pt.y]
}
function saisir(quoi: 'corps' | 'rotation', ev: PointerEvent) {
  ;(ev.currentTarget as Element).setPointerCapture(ev.pointerId)
  glisse.value = quoi
  depart = { p: versImage(ev), pl: [...placement.value] as [number, number, number] }
}
function bouger(ev: PointerEvent) {
  if (!glisse.value || !depart) return
  const p = versImage(ev)
  if (glisse.value === 'corps') {
    placement.value = [depart.pl[0] + p[0] - depart.p[0], depart.pl[1] + p[1] - depart.p[1], depart.pl[2]]
  } else {
    // La poignée est au-dessus du plateau (v négatif) : l'angle qui l'amène
    // sous le pointeur.
    const dx = p[0] - placement.value[0], dy = p[1] - placement.value[1]
    let a = (Math.atan2(dx, -dy) * 180) / Math.PI
    // Aimanté tous les 15°, à 3° près : l'empreinte droite se retrouve d'un geste.
    const r = Math.round(a / 15) * 15
    if (Math.abs(a - r) < 3) a = r
    placement.value = [placement.value[0], placement.value[1], a]
  }
}
function lacher() {
  glisse.value = null
  depart = null
}
function tourner(d: number) {
  placement.value = [placement.value[0], placement.value[1], ((placement.value[2] + d + 540) % 360) - 180]
}

// Contour en pixels d'édition.
function versPx(pts: Point[]) {
  const [cx, cy, ang] = placement.value
  const a = (ang * Math.PI) / 180, ca = Math.cos(a), sa = Math.sin(a), k = 1 / props.mmParPx
  return pts.map(([u, v]) => [cx + (ca * u - sa * v) * k, cy + (sa * u + ca * v) * k] as [number, number])
}
const contourPx = computed(() => versPx(props.contour))
const godetPx = computed(() => (props.godet ? versPx(props.godet) : null))
const chaine = (pts: [number, number][]) => pts.map((p) => p.join(',')).join(' ')
const poignee = computed(() => {
  const vmin = Math.min(...props.contour.map((p) => p[1]))
  return versPx([[0, vmin - 1.6], [0, vmin]])
})
const r = computed(() => Math.max(props.largeur, props.hauteur) / 55)
const idVoile = useId()
</script>

<template>
  <div>
    <div class="relative border border-line bg-paper">
      <svg
        ref="svg" :viewBox="`0 0 ${largeur} ${hauteur}`" class="block h-auto w-full touch-none select-none"
        @pointermove="bouger" @pointerup="lacher" @pointercancel="lacher"
      >
        <defs>
          <mask :id="idVoile">
            <rect x="0" y="0" :width="largeur" :height="hauteur" fill="white" />
            <polygon :points="chaine(contourPx)" fill="black" />
          </mask>
        </defs>
        <image :href="image" x="0" y="0" :width="largeur" :height="hauteur" />
        <rect
          x="0" y="0" :width="largeur" :height="hauteur" fill="white" fill-opacity="0.62"
          :mask="`url(#${idVoile})`" pointer-events="none"
        />
        <polygon
          v-if="godetPx" :points="chaine(godetPx)" fill="none" stroke="#C47396"
          :stroke-width="r / 8" stroke-dasharray="4 4" pointer-events="none"
        />
        <polygon
          :points="chaine(contourPx)" fill="#C47396" fill-opacity="0.06" stroke="#C47396"
          :stroke-width="r / 4" class="cursor-move" @pointerdown="saisir('corps', $event)"
        />
        <line
          :x1="poignee[0]![0]" :y1="poignee[0]![1]" :x2="poignee[1]![0]" :y2="poignee[1]![1]"
          stroke="#000" :stroke-width="r / 6" pointer-events="none"
        />
        <circle
          :cx="poignee[0]![0]" :cy="poignee[0]![1]" :r="r" fill="white" stroke="#000" :stroke-width="r / 5"
          class="cursor-grab" @pointerdown="saisir('rotation', $event)"
        />
      </svg>
    </div>
    <div class="mt-3 flex flex-wrap items-center justify-between gap-x-5 gap-y-2 text-[13px]">
      <span class="valeur text-txt">{{ Math.round(placement[2]) }}°</span>
      <span class="flex gap-4">
        <button type="button" class="lien" @click="tourner(-90)">↺ 90°</button>
        <button type="button" class="lien" @click="tourner(90)">↻ 90°</button>
      </span>
    </div>
    <p class="mt-2 text-[13px] text-txt">
      Glissez le plateau sur la partie de l’empreinte à garder ; la poignée le fait tourner.
      <template v-if="godet">Le pointillé est le bord du godet : les crêtes s’arrêtent là.</template>
    </p>
  </div>
</template>
