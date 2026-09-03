# SKULL-06.5 — machine à états de lecture

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Travail effectué uniquement dans le worktree local de production.
- Aucun accès au Raspberry, aucun redémarrage et aucune action matérielle.
- Les changements existants des tâches précédentes ont été conservés.
- Aucun commit ni push effectué.

## Réalisation

- Ajout de `domain/state_machine.py`, pur et importable sans dépendance runtime.
- Table complète des transitions pour `IDLE`, `STARTING`, `PLAYING`, `PAUSED`,
  `STOPPING` et `ERROR`, avec `TransitionNotAllowedError` sans mutation.
- Effets déclarés par transition : audio, timeline, fumée, publication d’état
  et sortie sûre.
- Verrou `RLock` unique et séquence monotone pour sérialiser les événements.
- `stop` idempotent depuis `IDLE`, `STOPPING` et `ERROR`.
- `SyncPlayer` relié aux transitions de démarrage, pause, reprise, arrêt,
  fin et erreur ; les statuts legacy restent inchangés.
- Attentes du worker interrompues par événement d’arrêt ; `stop` et `cleanup`
  attendent la fin du worker, et une erreur arrête l’audio avant `neutral`.

## Vérifications

- Tests ciblés machine à états et cycle worker : 74 passés.
- `python -m pytest -q` : 190 tests passés, 1 avertissement externe connu.
- `python -m compileall -q .` : OK.
- `git diff --check` : OK ; avertissements de fins de ligne Git existants.
- Scan ciblé des secrets sur les fichiers modifiés : aucune valeur sensible
  détectée.
- Tests de contrats HTTP legacy : inclus dans la suite complète et verts.

## Limites et suite

- Les effets déclarés restent exécutés par les composants legacy ; leur
  extraction en adaptateurs est la tâche `SKULL-06.6`.
- Aucune validation physique n’est incluse.
- Prochaine tâche autorisée : `SKULL-06.6`.
