import type { Config } from 'tailwindcss'

// Palette et typographie reprises de rainbowantworkshop.fr (CHARTE-GRAPHIQUE.md).
export default <Partial<Config>>{
  content: ['./app/components/**/*.{vue,ts}', './app/pages/**/*.vue', './app/app.vue'],
  theme: {
    extend: {
      colors: {
        paper: '#FFFFFF',
        'paper-2': '#FBF9F9',
        ink: '#000000',
        'ink-2': '#1A1A1A',
        txt: '#33373D',
        muted: '#A6A6A6',
        vert: '#A3C471',
        rose: '#C47396',
        bleu: '#739DC4',
        'vert-pale': '#E1E9D3',
        'rose-pale': '#EEC5D7',
        'bleu-pale': '#CADFF3',
        'vert-texte': '#485D27',
        'rose-texte': '#5D273F',
        'bleu-texte': '#27435D',
        framboise: '#EE2852',
        line: '#E6E6E6',
        'line-2': '#F0F0F0',
      },
      fontFamily: {
        sans: ['Jost', 'Futura', 'Century Gothic', 'sans-serif'],
      },
    },
  },
}
