<script setup lang="ts">
const marque = useMarque()
// L'icône d'onglet suit la marque. La clé remplace celle de nuxt.config au
// lieu d'en ajouter une seconde, que le navigateur aurait pu préférer.
useHead({
  link: [
    { key: 'icone', rel: 'icon', type: 'image/png', href: marque.favicon },
    { key: 'icone-apple', rel: 'apple-touch-icon', href: marque.iconeApple },
  ],
})
</script>

<template>
  <header class="border-b border-line">
    <div class="flex items-center justify-between gap-4 px-5 py-4 lg:px-10">
      <NuxtLink :to="marque.base || '/'" class="flex items-center gap-3">
        <img :src="marque.logo" :alt="marque.nom" class="h-8 w-auto">
        <span class="hidden text-[17px] font-medium tracking-tight sm:inline">{{ marque.nom }}</span>
      </NuxtLink>
      <nav class="flex items-center gap-5 text-[14px]">
        <NuxtLink :to="marque.base || '/'" class="lien-nav" exact-active-class="actif">Alliance</NuxtLink>
        <NuxtLink :to="`${marque.base}/chevaliere`" class="lien-nav" active-class="actif">Chevalière</NuxtLink>
        <!-- L'atelier n'a rien à faire sur l'adresse d'un client. -->
        <NuxtLink v-if="marque.id === 'raw'" to="/atelier" class="text-[13px] text-muted hover:text-ink">Atelier</NuxtLink>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.lien-nav { color: var(--txt); text-underline-offset: 6px; }
.lien-nav:hover { color: var(--ink); }
.actif { color: var(--ink); text-decoration: underline; text-decoration-color: var(--vert); text-decoration-thickness: 2px; }
</style>
