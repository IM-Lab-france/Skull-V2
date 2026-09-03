# Dependances reproductibles du Skull

## Methode

Les fichiers `requirements.in` contiennent les dependances directes deduites
des imports reels. Les fichiers `requirements*.lock` reprennent les versions
observees dans les `pip freeze` de production exportes par `SKULL-01.2`.
Ils servent de reference de reconstruction ; ils ne constituent pas encore un
lock genere par `pip-compile` sur ARM64.

Avant une mise a jour, reconstruire chaque environnement sur une machine Linux
Python 3.11 ARM64, puis comparer le resultat au freeze de production. Ne pas
installer les dependances depuis un lanceur applicatif et ne jamais inclure un
`.env` dans un lock ou un rapport.

## Separation des environnements

- `requirements.in` : `web_app.py`, `sync_player.py`, `loop_player.py`, la
  couche PCA9685/audio et Gunicorn pour la candidate WSGI principale.
- `requirements-playlist.in` : `playlist_web.py`, service HTTP public qui
  utilise Flask, Gunicorn et requests.
- Les paquets transitifs sont conserves uniquement dans les locks. Exemple :
  Jinja2, Werkzeug, click, blinker et les bibliotheques de transport HTTP.

## Dependances systeme Raspberry

- FFmpeg : requis par pydub pour la lecture/conversion des formats audio.
- PortAudio et ses en-tetes : requis par sounddevice.
- ALSA/PulseAudio selon le sink actif : routage de la sortie audio Bluetooth.
- I2C active et acces `/dev/i2c-*` : PCA9685 via Blinka.
- BlueZ et `bluetoothctl` : scan, appairage, confiance et connexion audio.
- `lgpio`/GPIO Raspberry : selon les chemins materiels effectivement utilises.
- `curl` : utilise par le declenchement webhook `Accueil` du patch actuel.

## Runtime et persistance des logs

Le journal servo utilise `RotatingFileHandler` avec, par defaut, un fichier de
10 MiB et 5 sauvegardes (`SKULL_LOG_MAX_BYTES` et
`SKULL_LOG_BACKUP_COUNT`). Les statistiques JSON conservent 100 sessions
(`SKULL_STATS_RETENTION`). Le service cree `logs/` en `0750` et les fichiers en
`0640`, sous le compte `skull`; si le volume devient indisponible, le runtime
reste actif et bascule vers le journal standard sans persister de contenu.

Les connexions sortantes ont des bornes explicites : `bluetoothctl`, `curl` et
les commandes systemd ont un timeout total ; les appels HTTP playlist utilisent
un couple connexion/lecture ; l’ESP32 utilise la limite de socket configuree.
La connexion Bluetooth de l’enceinte est declenchee a la demande et ne bloque
pas le demarrage systemd.

## Candidate WSGI

`gunicorn.conf.py` impose un seul worker synchrone, un seul thread, aucun
prechargement et des timeouts de requete/arret bornes. `launch_wsgi.sh` lance
la candidate sur `127.0.0.1:5002` par defaut. En mode
`SKULL_HARDWARE_MODE=simulated`, le worker sert les routes sans initialiser de
materiel reel ; la route `/health/ready` peut ainsi etre verifiee localement.
En production, l’initialisation reelle est faite par le hook Gunicorn apres
creation de l’unique worker, puis liberee par les hooks d’arret.

L’unite candidate d’exemple est
`deploy/skull-candidate.service.example`. Elle vise un chemin distinct,
`127.0.0.1:5002`, le mode simule et ne contient volontairement aucune section
`[Install]` : elle ne peut pas etre activee automatiquement. La matrice
legacy candidate est dans `evidence/SKULL-05.6/ROUTE-MATRIX.md`.

## Limites de validation

La compilation Python et la verification syntaxique JavaScript ont ete
validees dans le worktree. La creation d’un venv neuf n’est pas executee sur
Windows, car les paquets materiels ARM64 ne sont pas representatifs de cet
environnement et aucune installation n’est autorisee dans cette tache.
