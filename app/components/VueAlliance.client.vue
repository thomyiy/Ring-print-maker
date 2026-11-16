<script setup lang="ts">
import {
  ACESFilmicToneMapping, Box3, Color, Mesh, MeshPhysicalMaterial, PerspectiveCamera,
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
  new ResizeObserver(taille).observe(hote.value!)
  const boucle = () => { controls.update(); renderer.render(scene, camera); anim = requestAnimationFrame(boucle) }
  boucle()
  if (props.url) charger(props.url)
})

onBeforeUnmount(() => { cancelAnimationFrame(anim); renderer?.dispose() })

async function charger(url: string) {
  chargement.value = true
  try {
    const buf = await (await fetch(url)).arrayBuffer()
    // Le STL est une soupe de triangles : on soude les sommets pour lisser
    // l'éclairage, sinon le fil paraît facetté à l'écran alors qu'il ne l'est pas.
    const brut = new STLLoader().parse(buf)
    brut.deleteAttribute('normal')
    const geo = mergeVertices(brut, 1e-4)
    geo.computeVertexNormals()
    if (maillage) { scene.remove(maillage); maillage.geometry.dispose() }
    maillage = new Mesh(geo, matiere)
    scene.add(maillage)
    const b = new Box3().setFromObject(maillage)
    const c = b.getCenter(new Vector3())
    controls.target.copy(c)
    const r = b.getSize(new Vector3()).length()
    // Vue de départ : en biais et par-dessus, l'empreinte face au regard.
    camera.position.copy(c).add(new Vector3(0.45, 0.85, 0.75).normalize().multiplyScalar(r * 1.75))
  } finally {
    chargement.value = false
  }
}

watch(() => props.url, (u) => u && charger(u))
watch(() => props.teinte, (t) => matiere.color.setHex(t), { immediate: true })

function vue(nom: 'dessus' | 'face' | 'biais') {
  if (!maillage) return
  const c = controls.target.clone()
  const d = camera.position.distanceTo(c)
  const dir = { dessus: new Vector3(0, 1, 0.001), face: new Vector3(0, 0.001, 1), biais: new Vector3(0.55, 0.75, 0.9) }[nom]
  camera.position.copy(c).add(dir.normalize().multiplyScalar(d))
}
defineExpose({ vue })
</script>

<template>
  <div class="relative h-full w-full">
    <div ref="hote" class="absolute inset-0" />
    <p v-if="chargement" class="absolute left-4 top-4 eyebrow">Chargement du maillage…</p>
  </div>
</template>
