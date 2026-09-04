# SKULL-05.3 — résultat

## Statut

**VALIDÉ — serveur WSGI à un worker validé localement, non déployé.**

Date : 2026-09-03.

La candidate a été construite dans le worktree isolé de production. Aucun
fichier, service systemd ou matériel du Raspberry n’a été modifié.

## Choix et configuration

- serveur WSGI : Gunicorn `22.0.0` ;
- `workers = 1` ;
- `threads = 1` ;
- `worker_class = "sync"` ;
- `preload_app = False` ;
- timeout de requête : 30 secondes ;
- timeout d’arrêt gracieux : 10 secondes ;
- bind local par défaut : `127.0.0.1:5002` ;
- aucune activation automatique ni modification de l’unité systemd existante.

Le choix d’un worker et d’un thread évite de dupliquer l’état matériel tant que
le PCA9685 et l’audio appartiennent au processus applicatif. Le préchargement
est désactivé afin que l’initialisation réelle ait lieu dans l’unique worker,
après son fork.

## Fichiers créés ou modifiés

- `requirements.in` et `requirements.lock` : Gunicorn et sa dépendance
  verrouillée `packaging` ;
- `requirements-playlist.in` et `requirements-playlist.lock` : mêmes versions
  disponibles pour l’interface playlist ;
- `gunicorn.conf.py` : configuration unique et hooks de cycle de vie ;
- `wsgi_entry.py` : cible WSGI sans effet de lancement à l’import ;
- `launch_wsgi.sh` : commande Linux locale avec contrôle du venv ;
- `DEPENDENCIES.md` : procédure et contraintes documentées ;
- `tests/unit/test_wsgi_runtime.py` : tests de configuration, import simulé,
  hooks et lanceur.

## Validations locales

```text
python -m pytest tests/unit/test_wsgi_runtime.py tests/unit/test_startup_determinism.py -q
8 passed, 1 warning

python -m pytest -q
74 passed, 1 warning

python -m compileall -q web_app.py playlist_web.py sync_player.py runtime_lock.py tests
git diff --check
bash -n launch_wsgi.sh
```

Le warning restant est celui, déjà connu, de `pydub` concernant le module
Python déprécié `audioop`.

## Smoke test Linux en mode simulé

La commande `launch_wsgi.sh` a été reproduite dans un conteneur Linux ARM64
éphémère avec `SKULL_HARDWARE_MODE=simulated` et Gunicorn `22.0.0` :

```text
GET /health/live
{"checks":{"configuration":true,"process":true},"mode":"simulated","status":"ok","version":"dev"}

GET /health/ready
503 — readiness attendue tant que les adaptateurs ne sont pas initialisés
```

Le relevé `/proc` a montré deux processus Gunicorn applicatifs : un master et
un worker unique. Le processus Python utilisé uniquement pour lire `/proc` a
été exclu du comptage. Le conteneur a été supprimé après le test.

## Signaux et arrêt

Les hooks `worker_int` et `worker_exit` appellent `cleanup_runtime()`. Le
cleanup applicatif est idempotent : un double appel ne répète pas la fermeture
des threads, de l’audio ou du PCA9685. Le test dédié vérifie les hooks et les
tests de `SKULL-05.2` vérifient l’idempotence des composants.

## Critères d’acceptation

- commande WSGI reproductible : **validé** par `launch_wsgi.sh` et la
  configuration verrouillée ;
- un seul worker démontré dans un environnement Linux simulé : **validé** par
  le smoke test master + worker unique ;
- fermeture propre vérifiée en simulation : **validé** par les hooks et les
  tests d’arrêt idempotent ;
- aucun changement de production : **confirmé**.

## Risques et limites

- Gunicorn ne s’exécute pas nativement sous Windows ; la validation d’exécution
  a donc été réalisée sous Linux dans Docker, sans matériel réel ;
- en mode simulé, le hook WSGI ne construit volontairement aucun adaptateur
  matériel réel ; le smoke test couvre l’import et le healthcheck, pas la
  lecture d’une session ;
- l’unité systemd actuelle utilise encore l’ancien lanceur jusqu’à une future
  étape de préparation/bascule (`SKULL-05.6`/`SKULL-05.7`) ;
- les routes legacy et les boutons/sonnette devront être comparés avec la
  candidate dans les étapes prévues.

## Rollback

Aucun déploiement n’ayant été effectué, aucun rollback distant n’est requis.
La candidate locale peut être écartée après revue du diff en conservant les
modifications antérieures du worktree ; ne pas utiliser de reset ou nettoyage
Git destructif.

## Prochaine tâche autorisée

`SKULL-05.4` : compléter les healthchecks `/health/live` et `/health/ready`
avec leurs contrats 200/503 et la preuve d’absence d’effets de bord.
