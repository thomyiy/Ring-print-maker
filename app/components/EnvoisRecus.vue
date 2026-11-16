<!-- Les bagues envoyées par les clients. Protégé par NUXT_JETON_ATELIER : les
     fiches portent des noms et des adresses e-mail. -->
<script setup lang="ts">
const jeton = ref('')
const envois = ref<any[] | null>(null)
const faute = ref('')
const charge = ref(false)

onMounted(() => {
  try { jeton.value = localStorage.getItem('jeton-atelier') ?? '' } catch {}
  if (jeton.value) charger()
})

async function charger() {
  faute.value = ''
  charge.value = true
  try {
    envois.value = await $fetch<any[]>('/api/envois', { headers: { 'x-jeton-atelier': jeton.value } })
    try { localStorage.setItem('jeton-atelier', jeton.value) } catch {}
  } catch (e: any) {
    envois.value = null
    faute.value = e?.data?.statusMessage ?? e?.statusMessage ?? 'Liste indisponible'
  } finally {
    charge.value = false
  }
}

const lien = (ref: string, f: string) => `/api/envois/${ref}/${f}?jeton=${encodeURIComponent(jeton.value)}`
const date = (s: string) => new Date(s).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
const f = (x: number, d = 1) => (x ?? 0).toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
</script>

<template>
  <section class="border-t border-line px-5 py-8 lg:px-10">
    <p class="eyebrow">Bagues reçues</p>
    <div class="filet-teinte mt-3" />
    <form class="mt-5 flex max-w-md items-end gap-4" @submit.prevent="charger">
      <label class="flex-1">
        <span class="champ-intitule">Jeton d’atelier</span>
        <input v-model="jeton" type="password" class="champ mt-2" autocomplete="off">
      </label>
      <button type="submit" class="lien h-10 text-[14px]">{{ charge ? 'Lecture…' : 'Afficher' }}</button>
    </form>
    <p v-if="faute" class="mt-3 text-[13px] text-framboise">{{ faute }}</p>

    <p v-if="envois && !envois.length" class="mt-6 text-[14px] text-txt">Aucune bague reçue pour l’instant.</p>
    <div v-if="envois?.length" class="mt-6 border-t border-line">
      <article v-for="e in envois" :key="e.ref" class="grid gap-4 border-b border-line py-5 md:grid-cols-[140px_1fr_auto]">
        <a :href="lien(e.ref, 'rendu_dessus.png')" target="_blank">
          <img :src="lien(e.ref, 'rendu_general.png')" :alt="e.piece" class="h-28 w-full border border-line bg-paper-2 object-contain">
        </a>
        <div class="min-w-0 text-[14px]">
          <p class="text-[17px] font-medium text-ink">
            {{ e.piece }}
            <span v-if="e.marque === 'joia'" class="tag ml-2 align-middle">Joia Bijou</span>
          </p>
          <p class="text-txt">
            {{ e.contact.nom }} · <a :href="`mailto:${e.contact.email}`" class="lien">{{ e.contact.email }}</a>
            <template v-if="e.contact.telephone"> · {{ e.contact.telephone }}</template>
          </p>
          <p class="valeur mt-1 text-[12px] text-txt">
            <template v-if="e.choix.resume">{{ e.choix.resume }}</template>
            <template v-else>{{ e.choix.metalNom }} · taille {{ e.choix.taille }} · fil {{ f(e.choix.cote) }} mm · relief {{ f(e.choix.relief, 2) }} mm</template>
            · {{ f(e.controles.poids_or_750_g, 2) }} g or / {{ f(e.controles.poids_argent_925_g, 2) }} g argent
          </p>
          <p v-if="e.contact.message" class="mt-2 text-txt">« {{ e.contact.message }} »</p>
          <p class="valeur mt-1 text-[12px] text-muted">{{ date(e.recu_le) }} · {{ e.ref }}</p>
        </div>
        <div class="flex flex-col gap-2 text-[14px] md:items-end">
          <a :href="lien(e.ref, e.fichiers.find((x: string) => x.endsWith('.stl')))" class="lien">STL de fabrication</a>
          <a v-if="e.fichiers.includes('masque.png')" :href="lien(e.ref, 'masque.png')" target="_blank" class="lien">Empreinte et cadre</a>
          <a v-if="e.fichiers.includes('bande.png')" :href="lien(e.ref, 'bande.png')" target="_blank" class="lien">Bande déroulée</a>
          <a v-if="e.fichiers.includes('rendu_dessus.png')" :href="lien(e.ref, 'rendu_dessus.png')" target="_blank" class="lien">Vue de dessus</a>
          <a :href="lien(e.ref, 'empreinte_source.png')" target="_blank" class="lien">Image envoyée</a>
        </div>
      </article>
    </div>
  </section>
</template>
