<!-- La fenêtre d'envoi : le nom de la pièce, puis la confirmation qui le
     reprend. Rien d'autre (Thomas, 16/11/2026 : « juste le nom de la pièce ») —
     c'est par ce nom que l'atelier retrouve la commande dans /atelier.

     Un `<dialog>` natif, comme la fenêtre de devis de rainbowantworkshop.fr :
     piège de focus, Échap et voile sans rien réécrire. -->
<script setup lang="ts">
export interface Formulaire {
  nom_piece: string
}

const props = defineProps<{ resume: string; envoyer: (f: Formulaire) => Promise<{ piece: string; ref: string }> }>()

const fenetre = ref<HTMLDialogElement>()
const nomPiece = ref('')
const etat = ref<'saisie' | 'envoi' | 'envoye'>('saisie')
const faute = ref('')
const envoye = ref<{ piece: string; ref: string } | null>(null)
const champNom = ref<HTMLInputElement>()

function ouvrir() {
  nomPiece.value = ''
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
  if (!nomPiece.value.trim()) return (faute.value = 'Donnez un nom à la pièce : c’est par lui que l’atelier la retrouve.')
  etat.value = 'envoi'
  try {
    envoye.value = await props.envoyer({ nom_piece: nomPiece.value.trim() })
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
         à la touche Entrée, et la pièce calculée serait perdue. -->
    <form v-if="etat !== 'envoye'" method="dialog" novalidate class="px-7 py-7" @submit.prevent="soumettre">
      <p class="eyebrow">Envoyer à l’atelier</p>
      <div class="filet-teinte mt-3" />
      <p class="mt-4 text-[14px] text-txt">{{ resume }}</p>

      <label for="env-piece" class="champ-intitule mt-6">Nom de la pièce</label>
      <input
        id="env-piece" ref="champNom" v-model="nomPiece" class="champ mt-2" maxlength="80"
        autocomplete="off" spellcheck="false" placeholder="Alliance de Camille"
      >

      <p v-if="faute" class="mt-3 text-[13px] text-framboise">{{ faute }}</p>
      <p v-if="etat === 'envoi'" class="mt-3 text-[13px] text-txt">
        L’atelier prépare le fichier de fabrication, quelques secondes…
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
      <p class="mt-3 text-[15px] text-txt">est arrivée à l’atelier, avec l’empreinte et le fichier 3D.</p>
      <p class="valeur mt-4 text-[12px] text-txt">Référence {{ envoye?.ref }}</p>
      <div class="mt-7 flex justify-end">
        <button type="button" class="btn-primary" @click="fermer">Fermer</button>
      </div>
    </div>
  </dialog>
</template>
