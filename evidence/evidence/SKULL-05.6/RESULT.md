# Résultat SKULL-05.6

- Date : 2026-09-03
- Statut : VALIDÉ localement
- Portée : préparation d’une candidate parallèle, sans action distante

## Résultat obtenu

La candidate est préparée dans le worktree isolé
`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026` avec :

- unité d’exemple distincte `deploy/skull-candidate.service.example` ;
- chemin cible `/opt/skull-candidate` ;
- mode simulé ;
- port loopback `127.0.0.1:5002` ;
- aucune section `[Install]`, donc aucune activation automatique ;
- Gunicorn limité à un worker, un thread et sans préchargement.

La matrice legacy couvre 21 cas et compare méthode, statut, `Content-Type`,
clés et types. Les champs volatils exclus sont listés dans
`ROUTE-MATRIX.md`.

## Validations

Dans le worktree candidat :

```text
python -m pytest tests/unit/test_parallel_candidate.py -q
3 passed, 1 warning

python -m pytest -q
89 passed, 1 warning

python -m compileall -q ...
git diff --check
```

Smoke Docker Linux éphémère, dépôt monté en lecture seule : `GET
/health/live → 200`, deux processus Gunicorn (master + worker), puis arrêt et
suppression du conteneur.

## Limites / rollback

La production Raspberry n’a pas été démarrée en parallèle et aucun venv,
service, port ou fichier distant n’a été créé ou modifié. Le baseline réel n’a
pas été exécuté : la comparaison repose sur les snapshots de contrats issus de
la caractérisation et les adaptateurs factices.

Aucun rollback distant n’est requis. La candidate locale reste réversible par
revue et suppression ciblée de ses seuls artefacts.

## Prochaine tâche

`SKULL-05.7`, avec confirmation explicite avant arrêt de la production et
démarrage de la candidate sur le port historique.
