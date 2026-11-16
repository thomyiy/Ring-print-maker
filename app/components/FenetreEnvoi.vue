<!-- La fenêtre d'envoi : le nom de la pièce, les coordonnées, puis la
     confirmation qui reprend ce nom. Même construction que la fenêtre de devis
     de rainbowantworkshop.fr — un `<dialog>` natif, pour le piège de focus,
     l'Échap et le voile sans rien réécrire. -->
<script setup lang="ts">
const props = defineProps<{ resume: string; envoyer: (f: Formulaire) => Promise<{ piece: string; ref: string }> }>()

export interface Formulaire {
  nom_piece: string
  nom: string
  email: string
  telephone: string
  message: string
}

const fenetre = ref<HTMLDialogElement>()
const f = reactive<Formulaire>({ nom_piece: '', nom: '', email: '', telephone: '', message: '' })
const etat = ref<'saisie' | 'envoi' | 'envoye'>('saisie')
const faute = ref('')
const envoye = ref<{ piece: string; ref: string } | null>(null)
const champNom = ref<HTMLInputElement>()

function ouvrir() {
  // Une fenêtre neuve à chaque envoi, sauf les coordonnées : on ne les fait
  // pas retaper à qui envoie une deuxième bague.
  f.nom_piece = ''
  faute.value = ''
  etat.value = 'saisie'
  envoye.value = null
  fenetre.value?.showModal()
  nextTick(() => champNom.value?.focus())
}
function fermer() {
  fenetre.value?.close()
}
defineExpose({ ouvrir })

async function soumettre() {
  faute.value = ''
  if (!f.nom.trim()) return (faute.value = 'Votre nom est nécessaire.')
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim())) return (faute.value = 'L’adresse e-mail ne semble pas valide.')
  etat.value = 'envoi'
  try {
    envoye.value = await props.envoyer({ ...f })
    etat.value = 'envoye'
  } catch (e: any) {
    etat.value = 'saisie'
    faute.value = e?.data?.statusMessage ?? e?.statusMessage ?? 'L’envoi n’a pas abouti. Réessayez dans un instant.'
  }
}
</script>

<template>
  <dialog
    ref="fenetre"
    class="w-[min(520px,calc(100vw-32px))] border border-line bg-paper p-0 text-ink backdrop:bg-ink/40"
    @cancel="etat === 'envoi' && $event.preventDefault()"
  >
    <!-- ⚠️ `method="dialog"` : un formulaire ordinaire ferait naviguer la page
         à la touche Entrée, et la bague calculée serait perdue. -->
    <form v-if="etat !== 'envoye'" method="dialog" novalidate class="px-7 py-7" @submit.prevent="soumettre">
      <p class="eyebrow">Envoyer ma bague</p>
      <div class="filet-teinte mt-3" />
      <p class="mt-4 text-[14px] text-txt">{{ resume }}</p>

      <label for="env-piece" class="champ-intitule mt-6">Nom de la pièce (facultatif)</label>
      <input
        id="env-piece" ref="champNom" v-model="f.nom_piece" class="champ mt-2" maxlength="80"
        autocomplete="off" spellcheck="false" placeholder="Alliance de Camille"
      >

      <p class="champ-intitule mt-6">Vos coordonnées</p>
      <div class="mt-2 grid gap-3 sm:grid-cols-2">
        <input v-model="f.nom" class="champ" placeholder="Nom" autocomplete="name" aria-label="Nom">
        <input v-model="f.email" class="champ" type="email" placeholder="E-mail" autocomplete="email" aria-label="E-mail">
        <input v-model="f.telephone" class="champ sm:col-span-2" type="tel" placeholder="Téléphone (facultatif)" autocomplete="tel" aria-label="Téléphone">
      </div>
      <textarea
        v-model="f.message" class="champ mt-3 h-24 py-2" maxlength="2000"
        placeholder="Un mot pour l’atelier (facultatif)" aria-label="Message"
      />

      <p v-if="faute" class="mt-3 text-[13px] text-framboise">{{ faute }}</p>
      <p v-if="etat === 'envoi'" class="mt-3 text-[13px] text-txt">
        L’atelier prépare le fichier de fabrication de votre bague, quelques secondes…
      </p>

      <div class="mt-7 flex items-center justify-end gap-6">
        <button type="button" class="lien text-[14px]" :disabled="etat === 'envoi'" @click="fermer">Annuler</button>
        <button type="submit" class="btn-primary" :disabled="etat === 'envoi'">
          {{ etat === 'envoi' ? 'Envoi…' : 'Envoyer à l’atelier' }}
        </button>
      </div>
    </form>

    <div v-else class="px-7 py-8">
      <p class="eyebrow">C’est envoyé</p>
      <div class="filet-teinte mt-3" />
      <h2 class="mt-5 text-[30px]">« {{ envoye?.piece }} »</h2>
      <p class="mt-3 text-[15px] text-txt">
        est arrivée à l’atelier, avec votre empreinte et le fichier 3D. Nous revenons vers vous
        par e-mail sous 48 h ouvrées.
      </p>
      <p class="valeur mt-4 text-[12px] text-txt">Référence {{ envoye?.ref }}</p>
      <div class="mt-7 flex justify-end">
        <button type="button" class="btn-primary" @click="fermer">Fermer</button>
      </div>
    </div>
  </dialog>
</template>
