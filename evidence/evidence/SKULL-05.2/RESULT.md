# SKULL-05.2 — résultat

## Statut

**VALIDÉ — démarrage déterministe validé localement, non déployé.**

Date : 2026-09-03.

La tâche a été exécutée dans le worktree isolé de la production. Aucun fichier
du Raspberry, aucune unité systemd distante et aucun matériel réel n’ont été
modifiés.

## Changements réalisés

- `web_app.py` n’importe ni ne construit plus `SyncPlayer` ou `LoopPlayer` au
  chargement du module ; les proxies de compatibilité déclenchent une
  initialisation unique à la première utilisation ;
- `initialize_runtime()` valide le mode avec `resolve_runtime_mode()` avant
  d’importer ou construire le matériel, puis construit les deux composants sous
  un verrou intra-processus ;
- l’entrée explicite `main()` initialise le runtime, installe les handlers
  `SIGTERM`/`SIGINT` et force `debug=False` et `use_reloader=False` ;
- `playlist_web.py` force également `debug=False` et `use_reloader=False` ;
- `runtime_lock.py` fournit un verrou de fichier borné, utilisé par l’entrée
  matérielle principale avant construction ;
- `SyncPlayer.cleanup()` arrête ses threads, le gaze, l’audio et le PCA9685
  une seule fois, sans commander de position neutre ;
- `cleanup_runtime()` ferme la boucle audio, le lecteur et le verrou sans
  masquer une exception de fermeture ;
- l’absence de variable webhook n’empêche plus l’import du module et ne
  révèle aucune valeur sensible.

## Tests et validations

Commandes exécutées dans
`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026` :

```text
python -m pytest tests/unit/test_startup_determinism.py -q
4 passed, 1 warning

python -m pytest -q
70 passed, 1 warning

python -m compileall -q web_app.py playlist_web.py sync_player.py runtime_lock.py tests
git diff --check
```

Les tests dédiés couvrent :

- import sans construction du runtime ni thread matériel ;
- options Flask sans debug ni reloader ;
- deux initialisations simultanées en mode simulé donnant une seule paire de
  composants ;
- nettoyage appelé deux fois sans double arrêt ;
- échec borné d’un second verrou de runtime.

Le warning restant est celui, déjà connu, de `pydub` concernant le module
Python déprécié `audioop`.

## Critères d’acceptation

- un seul runtime est construit par processus : **validé par verrou
  intra-processus et test concurrent** ;
- le point d’entrée réel ne lance plus de reloader : **validé par code et
  test** ;
- l’import du module ne démarre ni serveur, ni thread, ni audio, ni I²C :
  **validé par test isolé** ;
- l’arrêt est idempotent et ne neutralise pas deux fois les servos : **validé
  par test et par `SyncPlayer.cleanup()`** ;
- la production Raspberry n’a pas encore été basculée : **non exécuté dans
  cette tâche**.

## Fichiers modifiés dans cette tâche

- `web_app.py` ;
- `playlist_web.py` ;
- `sync_player.py` ;
- `runtime_lock.py` ;
- `tests/unit/test_startup_determinism.py`.

Les modifications antérieures présentes dans le worktree ont été conservées.

## Risques et limites

- la production distante conserve encore l’ancien runtime Flask jusqu’à une
  future étape de déploiement ;
- le serveur WSGI à un worker relève de `SKULL-05.3` et n’est pas inclus ici ;
- l’arrêt matériel réel et le rollback sur le Raspberry restent à valider
  dans les tâches de déploiement et de validation matérielle.

## Rollback

Aucun déploiement n’ayant été effectué, la production n’a rien à restaurer.
Pour annuler la candidate locale, conserver ou archiver les cinq fichiers
modifiés de cette tâche puis restaurer leurs versions de référence dans le
worktree isolé après revue du diff ; ne pas utiliser de reset ou de nettoyage
Git destructif.

## Prochaine tâche autorisée

`SKULL-05.3` : ajouter et valider le serveur WSGI à un worker, sans l’installer
sur le Raspberry dans cette exécution.
