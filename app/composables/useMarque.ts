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
}

const MARQUES: Record<Marque['id'], Marque> = {
  raw: { id: 'raw', nom: 'Rainbow Ant Workshop', logo: '/logo-mark.png', base: '' },
  // Client de l'atelier ; logo utilisé avec son accord (Thomas, 16/11/2026).
  joia: { id: 'joia', nom: 'Joia Bijou', logo: '/marques/joia.jpg', base: '/joia' },
}

export function useMarque(): Marque {
  const route = useRoute()
  return route.path === '/joia' || route.path.startsWith('/joia/') ? MARQUES.joia : MARQUES.raw
}
