/**
 * La marque sous laquelle l'outil s'affiche.
 *
 * Rainbow Ant Workshop à la racine ; ses clients en marque blanche sous leur
 * propre adresse (`/joia`). Les pages sont les mêmes : seuls l'en-tête, le
 * titre et la marque inscrite sur chaque envoi changent — l'atelier sait ainsi
 * pour qui il fabrique.
 */
export interface Marque {
  id: 'raw' | 'joia'
  nom: string
  logo: string
  base: string
  favicon: string
  iconeApple: string
}

const MARQUES: Record<Marque['id'], Marque> = {
  raw: { id: 'raw', nom: 'Rainbow Ant Workshop', logo: '/logo-mark.png', base: '',
    favicon: '/favicon-32.png', iconeApple: '/logo-mark.png' },
  // Client de l'atelier ; logo utilisé avec son accord (Thomas, 16/11/2026).
  joia: { id: 'joia', nom: 'Joia Bijou', logo: '/marques/joia.jpg', base: '/joia',
    favicon: '/marques/joia-favicon-32.png', iconeApple: '/marques/joia-apple-touch-icon.png' },
}

export function useMarque(): Marque {
  const route = useRoute()
  return route.path === '/joia' || route.path.startsWith('/joia/') ? MARQUES.joia : MARQUES.raw
}
