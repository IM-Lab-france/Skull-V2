# Résultat SKULL-03.4

- Date : 3 septembre 2026
- Statut : VALIDÉ
- Portée : contrats HTTP legacy testés localement avec Flask et adaptateurs
  factices ; aucun appel au Raspberry, réseau, Bluetooth, I²C, GPIO ou audio.
- Fichiers ajoutés dans le worktree :
  `tests/contracts/http_legacy_snapshots.json`,
  `tests/contracts/HTTP-MAP.md` et
  `tests/contract/test_http_legacy_contracts.py`.
- Validation de collecte : `python -m pytest --collect-only -q` — 25 tests
  collectés.
- Validation d’exécution : `python -m pytest -q` — 25 tests réussis ;
  `python -m compileall -q .` et `git diff --check` réussis.
- Contrats couverts : `/status`, `/api/sessions`, `/api/enqueue`, `/play`,
  pause/resume/stop, playlist GET/POST/delete/move/skip, catégories et
  passerelle ESP32 avec adaptateur simulé.
- Assertions : codes HTTP, `Content-Type: application/json`, clés requises et
  types JSON ; l’ordre des clés n’est pas utilisé. Les valeurs temporelles et
  identifiants dynamiques ne sont pas figés.
- Sécurité : les adaptateurs matériels et réseau sont factices ; les snapshots
  ne contiennent aucune IP privée, MAC, URL réelle, secret ou donnée de
  production.
- Écart ou risque : les contrats sont caractérisés depuis le code local de la
  branche isolée, pas depuis une requête au Skull ; la protection effective des
  routes reste à traiter dans la phase sécurité.
- Rollback : supprimer les fichiers de test, snapshots, carte HTTP et preuve
  de cette tâche ; aucune modification applicative ou distante n’a été faite.
