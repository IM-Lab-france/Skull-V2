# SKULL-05.6 — résultat

## Statut

**VALIDÉ — instance candidate parallèle préparée et contrats legacy vérifiés
localement.**

Date : 2026-09-03.

La candidate a été préparée dans le worktree isolé de production. Aucun venv,
service systemd, port ou fichier du Raspberry n’a été créé ou modifié.

## Réalisation

- `deploy/skull-candidate.service.example` décrit une unité distincte dans
  `/opt/skull-candidate`, non activable automatiquement : aucune section
  `[Install]`, `Restart=no`.
- La candidate utilise le mode simulé et `127.0.0.1:5002` par défaut.
- `gunicorn.conf.py` impose un worker, un thread, aucun préchargement et des
  timeouts de requête/arret bornés.
- La matrice couvre les 21 cas legacy gelés : méthode, statut,
  `Content-Type`, clés et types. Les champs volatils exclus sont listés dans
  `ROUTE-MATRIX.md`.

## Validations

Dans `C:\Users\cedri\Documents\Codex\Skull-V2-production-2026` :

```text
python -m pytest tests/unit/test_parallel_candidate.py -q
3 passed, 1 warning

python -m pytest -q
89 passed, 1 warning

python -m compileall -q web_app.py playlist_web.py logger.py gaze_receiver.py runtime_factory.py runtime_lock.py wsgi_entry.py tests
git diff --check
```

Smoke WSGI Linux en conteneur éphémère, dépôt monté en lecture seule :

```text
GET /health/live  → 200
processus Gunicorn candidate → 2 (master + worker)
arrêt du conteneur → CANDIDATE_STOPPED
```

Le mode simulé à froid conserve `GET /health/ready → 503`, conformément au
contrat de readiness ; ce cas est validé par les tests sans initialiser le
matériel réel.

## Limites et arrêt

- La production n’a pas été démarrée en parallèle : le worktree reste une
  candidate locale et l’ancien runtime Raspberry n’a pas été sollicité.
- Le baseline de production n’a pas été exécuté directement, car il ouvre le
  matériel réel ; la comparaison utilise les snapshots de contrats issus de
  la caractérisation et des adaptateurs factices.
- Le smoke Docker a été arrêté et supprimé automatiquement ; aucune unité
  candidate distante n’est active.

## Rollback

Aucun rollback distant n’est nécessaire. Localement, supprimer uniquement la
candidate après revue du diff ou revenir au commit de travail précédent ; ne
pas utiliser de reset ou nettoyage Git destructif.

## Prochaine tâche autorisée

`SKULL-05.7` : basculer le runtime, uniquement après confirmation explicite
pour l’arrêt de la production et le démarrage de la candidate sur le port
historique.
