<script setup lang="ts">
import {
  ACESFilmicToneMapping, Box3, BufferAttribute, BufferGeometry, Color, Mesh, MeshPhysicalMaterial, PerspectiveCamera,
  PMREMGenerator, Scene, SRGBColorSpace, Vector3, WebGLRenderer,
} from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

const props = defineProps<{ url: string | null; teinte: number; fond?: number }>()
const hote = ref<HTMLDivElement>()
const chargement = ref(false)

let renderer: WebGLRenderer, scene: Scene, camera: PerspectiveCamera, controls: OrbitControls
let maillage: Mesh | null = null
let anim = 0

// ⚠️ ON NE DESSINE QUE QUAND QUELQUE CHOSE BOUGE. La boucle redessinait la
// bague soixante fois par seconde même immobile ; sur un appareil sans vraie
// carte graphique, chaque image prenait le fil principal et un clic sur une
// taille attendait 4 à 5 s avant même de partir au serveur (mesuré le
// 16/11/2026). Maintenant : une image à la demande, et la boucle ne tourne
// que tant que l'amortissement de la rotation n'est pas fini.
let enCours = false
function redessiner() {
  if (enCours || !renderer) return
  enCours = true
  anim = requestAnimationFrame(() => {
    enCours = false
    const bouge = controls.update()
    renderer.render(scene, camera)
    if (bouge) redessiner()
  })
}
const matiere = new MeshPhysicalMaterial({ metalness: 1, roughness: 0.26 })

function taille() {
  if (!hote.value) return
  const { clientWidth: w, clientHeight: h } = hote.value
  renderer.setSize(w, h)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

onMounted(() => {
  renderer = new WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.outputColorSpace = SRGBColorSpace
  renderer.toneMapping = ACESFilmicToneMapping
  hote.value!.appendChild(renderer.domElement)
  scene = new Scene()
  scene.background = new Color(props.fond ?? 0xfbf9f9)
  const pmrem = new PMREMGenerator(renderer)
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
  camera = new PerspectiveCamera(30, 1, 0.1, 500)
  camera.position.set(30, 32, 40)
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  taille()
  new ResizeObserver(() => { taille(); redessiner() }).observe(hote.value!)
  controls.addEventListener('change', redessiner)
  redessiner()
  if (props.url) charger(props.url)
})

onBeforeUnmount(() => { cancelAnimationFrame(anim); renderer?.dispose() })

/** STL : une soupe de triangles. On soude les sommets pour lisser l'éclairage,
 *  sinon le fil paraît facetté à l'écran alors qu'il ne l'est pas. */
function stl(buf: ArrayBuffer) {
  const brut = new STLLoader().parse(buf)
  brut.deleteAttribute('normal')
  const geo = mergeVertices(brut, 1e-4)
  geo.computeVertexNormals()
  return geo
}

/**
 * L'aperçu du moteur (`apercu.bin`) : M sections de N sommets, déjà partagés.
 * On refait ici la triangulation de `moteur/alliance.py::trianguler`, raccord
 * décalé de N/2 compris — huit fois moins à transférer qu'un STL, et pas de
 * soudure à calculer dans le navigateur.
 */
function grille(buf: ArrayBuffer) {
  const [M, N, inverse] = new Int32Array(buf, 0, 3)
  const pos = new Float32Array(buf, 12, M! * N! * 3)
  const idx = new Uint32Array(M! * N! * 6)
  let k = 0
  for (let j = 0; j < M!; j++) {
    const jn = (j + 1) % M!
    const dec = j === M! - 1 ? N! / 2 : 0
    for (let i = 0; i < N!; i++) {
      const a = j * N! + i
      const b = j * N! + ((i + 1) % N!)
      const c = jn * N! + ((i + 1 + dec) % N!)
      const d = jn * N! + ((i + dec) % N!)
      if (inverse) { idx.set([a, c, b, a, d, c], k) } else { idx.set([a, b, c, a, c, d], k) }
      k += 6
    }
  }
  const geo = new BufferGeometry()
  geo.setAttribute('position', new BufferAttribute(pos, 3))
  geo.setIndex(new BufferAttribute(idx, 1))
  geo.computeVertexNormals()
  return geo
}

let demande = ''
let cadre = false

async function charger(url: string) {
  demande = url
  chargement.value = true
  try {
    const buf = await (await fetch(url)).arrayBuffer()
    if (url !== demande) return // un calcul plus récent est déjà parti
    const geo = url.endsWith('.bin') ? grille(buf) : stl(buf)
    if (maillage) { scene.remove(maillage); maillage.geometry.dispose() }
    maillage = new Mesh(geo, matiere)
    scene.add(maillage)
    redessiner()
    // ⚠️ ON NE RECADRE QU'UNE FOIS. Recadrer à chaque recalcul ramenait la
    // caméra au point de départ après chaque clic sur une taille : on perdait
    // l'angle qu'on venait de choisir pour regarder l'empreinte.
    if (cadre) return
    cadre = true
    const b = new Box3().setFromObject(maillage)
    const c = b.getCenter(new Vector3())
    controls.target.copy(c)
    const r = b.getSize(new Vector3()).length()
    // Vue de départ : en biais et par-dessus, l'empreinte face au regard.
    camera.position.copy(c).add(new Vector3(0.45, 0.85, 0.75).normalize().multiplyScalar(r * 1.75))
    redessiner()
  } finally {
    if (url === demande) chargement.value = false
  }
}

watch(() => props.url, (u) => u && charger(u))
watch(() => props.teinte, (t) => { matiere.color.setHex(t); redessiner() }, { immediate: true })

function vue(nom: 'dessus' | 'face' | 'biais') {
  if (!maillage) return
  const c = controls.target.clone()
  const d = camera.position.distanceTo(c)
  const dir = { dessus: new Vector3(0, 1, 0.001), face: new Vector3(0, 0.001, 1), biais: new Vector3(0.55, 0.75, 0.9) }[nom]
  camera.position.copy(c).add(dir.normalize().multiplyScalar(d))
  redessiner()
}
defineExpose({ vue })
</script>

<template>
  <div class="relative h-full w-full">
    <div ref="hote" class="absolute inset-0" />
    <p v-if="chargement" class="absolute left-4 top-4 eyebrow">Chargement du maillage…</p>
  </div>
</template>
