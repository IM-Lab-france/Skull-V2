# SKULL-08.6 — noms internes et résolution DNS

- Date : 4 septembre 2026, Europe/Paris
- Statut : `PARTIEL`
- Portée : remplacement local d’une IP legacy, modèle de résolution, tests
  injectés et vérification DNS depuis le poste de travail.

## Validé localement

- L’endpoint primaire ESP32 doit être un nom DNS interne ; une IP ou une URL
  est refusée.
- Une résolution réussie sélectionne toujours le nom primaire.
- Une absence DNS ou un timeout est borné et visible.
- Un fallback IP n’est utilisé que si `allow_fallback=True` ; le résultat
  expose explicitement `used_fallback=True`.
- `launch_playlist_web.sh` n’embarque plus l’ancienne IP du Skull et utilise
  `skull.home.arpa:5000` par défaut ; une surcharge reste explicite via
  `PLAYLIST_BACKEND_BASE`.
- Aucun ACL, route, enregistrement DNS ou configuration réseau n’est modifié.

## Vérifications

- Fichiers modifiés : `launch_playlist_web.sh`,
  `docs/configuration-inventory.md` et `tests/config/test_dns.py`.
- Test DNS ciblé : `7 passed`.
- Suite complète exécutée depuis un répertoire de travail isolé : `308 passed`,
  avec un avertissement de dépréciation `audioop` déjà connu.
- Depuis le poste de travail, `skull.home.arpa` résout vers l’adresse actuelle
  du Skull et `ha.home.arpa` résout également ; aucune réponse n’est obtenue
  pour `esp32-boutons.home.arpa`.
- La tentative SSH en lecture seule vers le Skull a atteint le port 22, mais
  la preuve depuis le réseau source est bloquée par l’authentification ; aucun
  mot de passe n’a été tenté ni enregistré.
- Aucun secret, URL de production ou adresse réelle ajouté.

## Reste à faire

La création et la validation des enregistrements DNS appartiennent à la phase
réseau approuvée. Le nom de production de l’ESP32 reste à décider et la
résolution depuis le réseau source prévu ainsi que la coexistence avec les
routes legacy ne sont donc pas déclarées validées ici.
