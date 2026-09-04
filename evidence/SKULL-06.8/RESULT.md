# Résultat SKULL-06.8

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : ajout local de l’API `/api/v1` uniquement ; aucune écriture sur le
  Raspberry, aucun redémarrage, aucun scan et aucune action matérielle.
- Fichiers modifiés : `api/v1.py`, `web_app.py`, tests de contrat v1 et test de
  séparation du blueprint legacy ; documentation `tests/contracts/API-V1.md`.

## Réalisation

- Quatre routes v1 de lecture sont enregistrées sous le blueprint `v1` :
  statut, liste des sessions, inspection d’une session et playlist.
- Les succès utilisent `{"ok": true, "data": ...}` ; les erreurs utilisent
  `{"ok": false, "error": {"code": ..., "message": ...}}`.
- Les paramètres `session_name` et `limit` sont validés avant l’appel au
  contexte métier injecté.
- Les erreurs ne reflètent ni exception, ni traceback, ni commande, ni chemin,
  ni secret ; les réponses filtrent également les clés sensibles connues.
- La documentation contient la table de correspondance legacy/v1 et confirme
  qu’aucun client n’est migré pendant cette tâche.

## Commandes de validation

- `python -m pytest -q tests/contract/test_api_v1.py tests/contract/test_legacy_blueprint.py`
- `python -m pytest -q`
- `python -m compileall -q api web_app.py tests`
- `git diff --check`
- inventaire local des routes `legacy.*` et `v1.*`
- scan ciblé des nouveaux fichiers pour URL réelle, MAC et valeur secrète

## Résultats

- Tests ciblés : `7 passed`, `1 warning` externe connu.
- Suite complète : `212 passed`, `1 warning` externe connu (`pydub`/`audioop`).
- Compilation Python : OK.
- `git diff --check` : OK ; Git signale seulement les conversions de fins de
  ligne déjà présentes dans le worktree candidat.
- Coexistence confirmée : les routes legacy restent sous `legacy.*` et les
  quatre nouvelles routes sous `v1.*`.
- Aucun secret, webhook, adresse IP, MAC ou chemin système dans les nouveaux
  contrats, tests et documentation.

## Écarts ou risques restants

- La v1 reste volontairement en lecture seule. Les commandes de lecture,
  pause, reprise, arrêt, playlist mutante, Bluetooth, ESP32, relais, fumée,
  upload et administration restent legacy jusqu’aux tâches de sécurité et IoT.
- La validation physique et la migration des clients ne font pas partie de
  cette tâche.

## Rollback

- Supprimer uniquement les ajouts de cette tâche (`api/v1.py`, les tests et la
  documentation v1) et retirer l’import, les callbacks et l’enregistrement du
  blueprint v1 dans `web_app.py`.
- Restaurer dans `test_legacy_blueprint.py` le filtrage qui ne connaissait que
  le namespace legacy, sans toucher aux changements antérieurs.
- Aucun fichier de production ni client distant n’a été modifié ; le rollback
  local est donc réversible sans intervention matérielle.
