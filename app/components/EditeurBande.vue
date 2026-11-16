<!-- L'éditeur de placement : la bande se pose à la main sur l'empreinte.

     On attrape le corps pour la déplacer, un bout pour la tourner (bord à bord)
     ou pour l'allonger et la raccourcir (longueur libre). Les coordonnées sont
     les pixels de l'image d'édition rendue par le moteur, y vers le bas : c'est
     ce repère-là que le moteur relit dans `bande_px`. -->
<script setup lang="ts">
export interface Edition {
  image: string
  largeur: number
  hauteur: number
  a: [number, number]
  b: [number, number]
  largeur_bande_px: number
  mm_par_px: number
}

const props = defineProps<{ edition: Edition; occupe?: boolean }>()
const bordABord = defineModel<boolean>('bordABord', { default: true })
const emit = defineEmits<{
  /** Les deux bouts posés, ou null pour revenir au placement automatique. */
  change: [bande: [number, number, number, number] | null]
}>()

type P = [number, number]
const A = ref<P>([...props.edition.a] as P)
const B = ref<P>([...props.edition.b] as P)
const modifie = ref(false)

// Chaque nouveau résultat du moteur fait foi : en bord à bord, c'est lui qui
// sait où s'arrête l'empreinte.
watch(() => props.edition, (e) => {
  if (glisse.value) return
  A.value = [...e.a] as P
  B.value = [...e.b] as P
})

const svg = ref<SVGSVGElement>()
const glisse = ref<null | 'corps' | 'a' | 'b'>(null)
let depart: { p: P; A: P; B: P } | null = null

function versImage(ev: PointerEvent): P {
  const m = svg.value!.getScreenCTM()!.inverse()
  const pt = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(m)
  return [pt.x, pt.y]
}

function saisir(quoi: 'corps' | 'a' | 'b', ev: PointerEvent) {
  ;(ev.currentTarget as Element).setPointerCapture(ev.pointerId)
  glisse.value = quoi
  depart = { p: versImage(ev), A: [...A.value] as P, B: [...B.value] as P }
}

function bouger(ev: PointerEvent) {
  if (!glisse.value || !depart) return
  const p = versImage(ev)
  if (glisse.value === 'corps') {
    const dx = p[0] - depart.p[0]
    const dy = p[1] - depart.p[1]
    A.value = [depart.A[0] + dx, depart.A[1] + dy]
    B.value = [depart.B[0] + dx, depart.B[1] + dy]
    return
  }
  if (bordABord.value) {
    // Bord à bord, la longueur appartient à l'empreinte : le bout ne fait que
    // tourner la bande autour de son milieu.
    const m: P = [(depart.A[0] + depart.B[0]) / 2, (depart.A[1] + depart.B[1]) / 2]
    const demi = Math.hypot(depart.B[0] - depart.A[0], depart.B[1] - depart.A[1]) / 2
    let ux = p[0] - m[0]
    let uy = p[1] - m[1]
    const n = Math.hypot(ux, uy) || 1
    ux /= n; uy /= n
    const sgn = glisse.value === 'b' ? 1 : -1
    B.value = [m[0] + sgn * ux * demi, m[1] + sgn * uy * demi]
    A.value = [m[0] - sgn * ux * demi, m[1] - sgn * uy * demi]
  } else if (glisse.value === 'a') {
    A.value = p
  } else {
    B.value = p
  }
}

function lacher() {
  if (!glisse.value) return
  glisse.value = null
  depart = null
  modifie.value = true
  emit('change', [A.value[0], A.value[1], B.value[0], B.value[1]])
}

function automatique() {
  modifie.value = false
  bordABord.value = true
  emit('change', null)
}

watch(bordABord, () => {
  if (modifie.value) emit('change', [A.value[0], A.value[1], B.value[0], B.value[1]])
})

// — Géométrie affichée ————————————————————————————————————————————
const coins = computed(() => {
  const [ax, ay] = A.value
  const [bx, by] = B.value
  const L = Math.hypot(bx - ax, by - ay) || 1
  const nx = (-(by - ay) / L) * (props.edition.largeur_bande_px / 2)
  const ny = ((bx - ax) / L) * (props.edition.largeur_bande_px / 2)
  return `${ax + nx},${ay + ny} ${bx + nx},${by + ny} ${bx - nx},${by - ny} ${ax - nx},${ay - ny}`
})
const milieu = computed<P>(() => [(A.value[0] + B.value[0]) / 2, (A.value[1] + B.value[1]) / 2])
const longueurMm = computed(() =>
  Math.hypot(B.value[0] - A.value[0], B.value[1] - A.value[1]) * props.edition.mm_par_px)
const angle = computed(() => {
  // Affiché en degrés, sens trigonométrique à l'écran, 0 à 180.
  const a = (Math.atan2(-(B.value[1] - A.value[1]), B.value[0] - A.value[0]) * 180) / Math.PI
  return ((a % 180) + 180) % 180
})
// Taille des poignées : lisibles quelle que soit la résolution de l'image.
const idVoile = useId()
const r = computed(() => Math.max(props.edition.largeur, props.edition.hauteur) / 55)
const fmt = (x: number, d = 1) => x.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
</script>

<template>
  <div>
    <div class="relative border border-line bg-paper">
      <svg
        ref="svg"
        :viewBox="`0 0 ${edition.largeur} ${edition.hauteur}`"
        class="block h-auto w-full touch-none select-none"
        @pointermove="bouger"
        @pointerup="lacher"
        @pointercancel="lacher"
      >
        <defs>
          <mask :id="idVoile">
            <rect x="0" y="0" :width="edition.largeur" :height="edition.hauteur" fill="white" />
            <polygon :points="coins" fill="black" />
          </mask>
        </defs>
        <image :href="edition.image" x="0" y="0" :width="edition.largeur" :height="edition.hauteur" />
        <!-- Hors de la bande, l'empreinte s'efface : ce qui reste net est ce qui
             sera sur la bague. -->
        <rect
          x="0" y="0" :width="edition.largeur" :height="edition.hauteur"
          fill="white" fill-opacity="0.62" :mask="`url(#${idVoile})`"
          pointer-events="none"
        />
        <polygon
          :points="coins" fill="#C47396" fill-opacity="0.08" stroke="#C47396"
          :stroke-width="r / 4" class="cursor-move" @pointerdown="saisir('corps', $event)"
        />
        <line
          :x1="A[0]" :y1="A[1]" :x2="B[0]" :y2="B[1]" stroke="#C47396"
          :stroke-width="r / 8" stroke-dasharray="4 4" pointer-events="none"
        />
        <circle :cx="milieu[0]" :cy="milieu[1]" :r="r / 2.2" fill="#C47396" pointer-events="none" />
        <circle
          v-for="(p, i) in [A, B]" :key="i"
          :cx="p[0]" :cy="p[1]" :r="r" fill="white" stroke="#000" :stroke-width="r / 5"
          class="cursor-grab"
          @pointerdown="saisir(i === 0 ? 'a' : 'b', $event)"
        />
      </svg>
      <p v-if="occupe" class="absolute left-2 top-2 border border-line bg-paper px-2 py-0.5 text-[12px] text-txt">
        Recalcul…
      </p>
    </div>

    <div class="mt-3 flex flex-wrap items-center justify-between gap-x-5 gap-y-2 text-[13px]">
      <span class="valeur text-txt">{{ fmt(longueurMm) }} × 1,5 mm · {{ fmt(angle, 0) }}°</span>
      <span class="flex gap-4">
        <label class="flex items-center gap-1.5"><input v-model="bordABord" type="radio" :value="true"> Bord à bord</label>
        <label class="flex items-center gap-1.5"><input v-model="bordABord" type="radio" :value="false"> Longueur libre</label>
      </span>
    </div>
    <p class="mt-2 text-[13px] text-txt">
      Glissez la bande pour la déplacer, tirez un bout pour
      {{ bordABord ? 'la faire tourner' : 'la tourner ou changer sa longueur' }}.
      <button type="button" class="lien ml-1" @click="automatique">Placement automatique</button>
    </p>
  </div>
</template>
