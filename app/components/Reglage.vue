<script setup lang="ts">
// Un réglage numérique : curseur + valeur saisissable, bornés par le schéma
// du moteur (moteur/parametres.py), pour qu'une borne n'existe qu'à un endroit.
const props = defineProps<{ libelle: string; min: number; max: number; pas: number; unite?: string; aide?: string }>()
const v = defineModel<number>({ required: true })
const id = useId()
const decimales = computed(() => Math.max(0, -Math.floor(Math.log10(props.pas || 1))))
</script>

<template>
  <div>
    <div class="flex items-baseline justify-between gap-3">
      <label :for="id" class="champ-intitule">{{ libelle }}</label>
      <span class="flex items-baseline gap-1">
        <input
          :value="Number(v).toFixed(decimales)"
          class="valeur w-20 border-b border-line bg-transparent text-right focus:border-ink focus:outline-none"
          inputmode="decimal"
          @change="v = Math.min(max, Math.max(min, parseFloat(($event.target as HTMLInputElement).value.replace(',', '.')) || min))"
        >
        <span class="valeur text-muted">{{ unite }}</span>
      </span>
    </div>
    <input :id="id" v-model.number="v" type="range" :min="min" :max="max" :step="pas" class="mt-2 w-full">
    <p v-if="aide" class="mt-1 text-[13px] text-txt">{{ aide }}</p>
  </div>
</template>
