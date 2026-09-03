# SKULL-06.1 — types et erreurs du domaine

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Travail effectué uniquement dans le worktree local de production.
- Aucun accès au Raspberry, aucun redémarrage et aucune action matérielle.
- Les changements existants des tâches précédentes ont été conservés.

## Réalisation

- Création du package pur `domain/`, sans import Flask, requests, subprocess,
  audio ou bibliothèque Raspberry.
- Ajout des types immuables `Session`, `TimelineEvent`, `PlaylistItem`,
  `PlaybackState` et `PlaybackSnapshot`.
- Ajout des erreurs métier `NotFoundError`, `InvalidInputError`,
  `ConflictError`, `DependencyUnavailableError` et
  `OperationNotAllowedError`.
- Adaptation des validations session, du parseur timeline et du chargement
  de session pour utiliser les erreurs métier.
- Les erreurs de compatibilité héritent des exceptions Python legacy
  correspondantes ; les routes HTTP conservent donc leurs statuts et messages.

## Vérifications

- `python -m pytest -q tests/unit/test_domain_types.py` : 4 tests passés.
- `python -m pytest -q` : 94 tests passés, 1 avertissement externe connu.
- `python -m compileall -q domain timeline.py sync_player.py web_app.py tests/unit/test_domain_types.py` : OK.
- `git diff --check` : OK ; avertissements de fins de ligne Git existants,
  aucune normalisation appliquée.
- Le test d’import en sous-processus confirme l’absence de dépendance runtime
  interdite pour `domain`.
- Aucun secret, webhook, adresse réseau, MAC ou contenu de production n’est
  présent dans cette preuve.

## Limites et suite

- Les dictionnaires legacy restent aux frontières de l’application ; leur
  remplacement complet est réservé aux tâches suivantes.
- Aucune validation physique n’est incluse.
- Prochaine tâche autorisée : `SKULL-06.2`.
