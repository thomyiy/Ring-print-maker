/** Une pièce à afficher dans la vue 3D (la chevalière, son relief…) :
 *  positions, indices, et ses normales si elle les porte. `cle` change quand
 *  la pièce change ; la vue ne reconstruit que celles-là. */
export interface Piece {
  cle: string
  positions: Float32Array
  normales?: Float32Array
  indices: Uint16Array | Uint32Array
}
