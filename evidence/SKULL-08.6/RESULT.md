# SKULL-08.6 — noms internes et résolution DNS

- Date : 3 septembre 2026, Europe/Paris
- Statut : `PARTIEL`
- Portée : modèle local de résolution, fallback explicite et tests injectés.

## Validé localement

- L’endpoint primaire ESP32 doit être un nom DNS interne ; une IP ou une URL
  est refusée.
- Une résolution réussie sélectionne toujours le nom primaire.
- Une absence DNS ou un timeout est borné et visible.
- Un fallback IP n’est utilisé que si `allow_fallback=True` ; le résultat
  expose explicitement `used_fallback=True`.
- Aucun ACL, route, enregistrement DNS ou configuration réseau n’est modifié.

## Vérifications

- Tests phase 8 ciblés : `29 passed`.
- Résolveur injecté uniquement ; aucune requête DNS réelle.
- Aucun secret, URL de production ou adresse réelle ajouté.

## Reste à faire

La création et la validation des enregistrements DNS appartiennent à la phase
réseau approuvée. La résolution depuis le réseau source prévu et la coexistence
avec les routes legacy ne sont donc pas déclarées validées ici.
