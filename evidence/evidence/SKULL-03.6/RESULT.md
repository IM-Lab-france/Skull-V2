# Résultat SKULL-03.6

- Date : 3 septembre 2026
- Statut : VALIDÉ
- Portée : caractérisation locale des dépendances webhook et ESP32 avec
  serveur HTTP factice, réponses synthétiques et adaptateurs factices ; aucun
  endpoint réel, Raspberry, relais, fumée, Bluetooth, I²C, GPIO ou audio.
- Fichier ajouté dans le worktree :
  `tests/unit/test_external_dependencies_characterization.py`.
- Validation : `python -m pytest --collect-only -q` — 40 tests collectés ;
  `python -m pytest -q` — 40 tests réussis ; `python -m compileall -q .` et
  `git diff --check` réussis.
- Webhook : serveur local éphémère ; une seule requête `POST` pour `Accueil`
  (casse normalisée), aucune pour une autre session ; timeout transmis ;
  timeout, refus et HTTP 500 n’annulent pas la lecture déjà démarrée.
- ESP32 : indisponibilité réseau et réponse JSON invalide transformées en
  réponse locale `reachable=false`, sans fuite de contenu sensible.
- Sécurité : aucune URL de production, MAC, clé, secret ou donnée réelle dans
  les fixtures ; les serveurs factices sont arrêtés après chaque test.
- Écart ou risque : le webhook est appelé par `curl` dans le code actuel et son
  erreur est journalisée sans faire échouer la lecture ; la politique future de
  reprise/alerte relève des phases runtime et sécurité.
- Rollback : supprimer le test et la preuve de cette tâche ; aucune
  modification applicative ou distante n’a été effectuée.
