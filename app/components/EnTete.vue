<template>
  <header class="border-b border-line">
    <div class="flex items-center justify-between gap-4 px-5 py-4 lg:px-10">
      <NuxtLink to="/" class="flex items-center gap-3">
        <img src="/logo-mark.png" alt="" class="h-8 w-auto">
        <span class="hidden text-[17px] font-medium tracking-tight sm:inline">Rainbow Ant Workshop</span>
      </NuxtLink>
      <nav class="flex items-center gap-5 text-[14px]">
        <NuxtLink to="/" class="lien-nav" exact-active-class="actif">Alliance</NuxtLink>
        <NuxtLink to="/chevaliere" class="lien-nav" active-class="actif">Chevalière</NuxtLink>
        <NuxtLink to="/atelier" class="text-[13px] text-muted hover:text-ink">Atelier</NuxtLink>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.lien-nav { color: var(--txt); text-underline-offset: 6px; }
.lien-nav:hover { color: var(--ink); }
.actif { color: var(--ink); text-decoration: underline; text-decoration-color: var(--vert); text-decoration-thickness: 2px; }
</style>
