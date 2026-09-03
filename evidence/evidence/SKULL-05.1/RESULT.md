# SKULL-05.1 — résultat

## Statut

**VALIDÉ — collecte live en lecture seule terminée.**

Date de collecte : 2026-09-03.

Aucun redémarrage, arrêt de service, écriture ou changement de configuration
n’a été effectué.

## Cible et accès

- cible : `skull@192.168.1.116` ;
- accès SSH par la clé locale dédiée, en mode `BatchMode` ;
- identité observée : utilisateur `skull`, hôte `skull` ;
- `servo-sync.service` et `playlist-web.service` : `active (running)` et
  `enabled`.

## Unités systemd observées

`servo-sync.service` :

- `User=skull`, `Group=skull`, `WorkingDirectory=/opt/skull` ;
- PID principal `727` ;
- commande : `/opt/skull/.venv/bin/python /opt/skull/web_app.py` ;
- `Restart=on-failure`, `RestartSec=3` ;
- cgroup : PID `727` et enfant PID `796`.

`playlist-web.service` :

- `User=skull`, `Group=skull`, `WorkingDirectory=/opt/skull` ;
- PID principal `703` ;
- commande : `/opt/skull/launch_playlist_web.sh` ;
- `Restart=on-failure`, `RestartSec=3` ;
- cgroup : PID `703` et enfant PID `762`.

Les sorties `systemctl status` montrent explicitement le reloader Flask :
`Debug mode: on`, serveur de développement et `Restarting with stat`. Aucun
identifiant de diagnostic ou contenu de log sensible n’est conservé ici.

## Processus et threads observés

| Service | PID | PPID | Utilisateur | Threads | Commande |
|---|---:|---:|---|---:|---|
| `playlist-web.service` | 703 | 1 | `skull` | 1 | `python playlist_web.py` |
| `playlist-web.service` | 762 | 703 | `skull` | 2 | `.venv_playlist/bin/python playlist_web.py` |
| `servo-sync.service` | 727 | 1 | `skull` | 8 | `.venv/bin/python web_app.py` |
| `servo-sync.service` | 796 | 727 | `skull` | 9 | `.venv/bin/python web_app.py` |

Le nombre live de processus dans les deux cgroups est donc quatre, dont deux
processus par application Flask. Les PID et la hiérarchie ci-dessus viennent
de `ps` exécuté sur le Skull.

## Ports et ressources matérielles observés

- TCP `0.0.0.0:5000` : PID `727` et PID `796` ;
- TCP `0.0.0.0:5050` : PID `703` et PID `762` ;
- UDP `127.0.0.1:5005` : PID `727` et PID `796` ;
- `/dev/i2c-1` : PID `727` et PID `796` détiennent chacun un descripteur ;
- les périphériques `/dev/i2c-20` et `/dev/i2c-21` n’ont aucun détenteur
  observé ;
- PulseAudio expose un sink ALSA actif et deux clients Python observés.

Le nombre actuel de propriétaires du PCA9685/I²C est donc **deux**. Le
double accès n’est pas une hypothèse : il est confirmé par `fuser` sur
`/dev/i2c-1` et par l’arbre systemd. Deux clients Python audio sont également
observés ; le relevé n’expose pas leur correspondance PID détaillée.

## Cause identifiée par fichier et ligne

Audit statique du worktree
`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026` :

- `web_app.py:74-75` construit `SyncPlayer` et `LoopPlayer` au niveau module ;
- `sync_player.py:39` construit `Hardware`, donc le PCA9685 est initialisé
  pendant la construction de `SyncPlayer` ;
- `sync_player.py:73` construit `GazeReceiver` ;
- `gaze_receiver.py:65-66` démarre automatiquement le récepteur dans le
  processus qui n’est pas différé ;
- `loop_player.py:81-84` charge la boucle et ouvre le flux audio dans le
  constructeur ;
- `web_app.py:3158` appelle `app.run(..., debug=True)` sur le port 5000 ;
- `playlist_web.py:335` appelle `app.run(..., debug=True)` sur le port 5050.

La cause observée du double démarrage est donc le reloader Flask activé par
`debug=True`, qui crée l’enfant de reloader dans chaque service. Les
initialisations au niveau module expliquent pourquoi les deux processus du
service principal possèdent l’I²C et initialisent l’audio.

## Commandes de validation

Collecte distante exécutée sans `sudo` :

```text
systemctl cat servo-sync.service; systemctl cat playlist-web.service
systemctl show ...; systemctl status ...
ps -eo pid=,ppid=,user=,nlwp=,args= --forest
ss -lntup
fuser -v /dev/i2c-1
pactl list short sinks
pactl list short clients
```

Audit local :

```text
rg -n --glob '*.py' --glob '*.sh' 'debug=True|use_reloader|app.run|...'
```

## Écarts et risques restants

- le runtime actuel possède deux propriétaires I²C ;
- les deux applications utilisent encore le serveur Flask de développement
  avec reloader ;
- les sockets UDP et audio sont initialisés dans les deux processus du
  service principal ;
- aucun redémarrage contrôlé n’a été effectué, conformément à la fiche et à
  l’absence de fenêtre de maintenance confirmée ;
- la correction relève de `SKULL-05.2` et des tâches suivantes, non de cette
  mesure.

## Rollback

Aucun changement n’ayant été appliqué, aucun rollback n’est nécessaire. La
prochaine correction devra être préparée et validée localement avant toute
écriture sur le Raspberry.

## Prochaine tâche autorisée

`SKULL-05.2` peut maintenant être traitée dans une exécution séparée. Elle
devra rendre le démarrage déterministe, désactiver le debug/reloader en
production et garantir un seul propriétaire matériel.
