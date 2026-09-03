# Risques mécaniques observés — SKULL-03.2

Cette caractérisation ne corrige pas le parseur et ne commande aucun servo.

- Le format `timeline` inverse `jawOpening` : 0 % produit 185 degrés et 100 %
  produit 0 degré.
- Les formats `keyframes`, `frames` et canaux top-level interprètent une valeur
  de mâchoire entre 0 et 100 comme un pourcentage croissant vers 185 degrés.
- Les angles de cou et d’yeux sont translatés de 90 degrés sans validation des
  limites mécaniques ; des entrées hors plage produisent donc des angles hors
  plage.
- Une durée nulle dans la racine `keyframes` produit tout de même deux frames
  (`t=0` et `t=1/60`) lorsque le canal contient une keyframe à zéro.
- Deux keyframes au même instant conservent un comportement dépendant de
  l’ordre et de `bisect_left` ; aucune déduplication n’est appliquée.

Toute correction ou validation physique de ces comportements relève d’une
tâche ultérieure avec adaptateur simulé puis confirmation matérielle.
