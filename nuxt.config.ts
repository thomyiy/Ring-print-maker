// Outil interne de l'atelier : une page, un moteur Python appelé par Nitro.
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },
  modules: ['@nuxtjs/tailwindcss'],
  css: ['~/assets/css/main.css'],
  tailwindcss: { cssPath: false },
  runtimeConfig: {
    // Relu à chaque démarrage (préfixe NUXT_) : l'interpréteur et le dossier
    // de travail changent entre le poste et Railway.
    python: 'python3',
    dossierTravail: '',
    // Les bagues envoyées : sur un volume en production (voir moteur.ts).
    dossierEnvois: '',
    // Protège la liste des envois dans /atelier. Vide = liste fermée.
    jetonAtelier: '',
    // Facultatif : une adresse qui reçoit chaque envoi en JSON (service de leads…).
    webhookEnvoi: '',
  },
  app: {
    head: {
      htmlAttrs: { lang: 'fr' },
      title: 'Alliance empreinte — Rainbow Ant Workshop',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'robots', content: 'noindex, nofollow' },
      ],
      link: [
        { rel: 'icon', type: 'image/png', href: '/favicon-32.png' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600&display=swap',
        },
      ],
    },
  },
})
