# Skull Servo Sync Player

Plateforme de pilotage d’un crâne animatronique : synchronisation de quatre servos avec un MP3, interface web moderne pour charger des sessions, ajuster les offsets, suivre les logs en direct et exposer une interface publique facultative.

## Aperçu fonctionnel

- **Synchronisation audio/servos** : `sync_player.py` lit un MP3 tout en rejouant une timeline JSON (différents formats acceptés) à 60 fps.
- **Pilotage matériel** : `rpi_hardware.py` s’appuie sur la carte PCA9685 (I²C) pour commander « jaw », « eye_left », « eye_right », « neck_pan » avec clamps mécaniques et logging systématique.
- **Interface web Flask** (`web_app.py`) :
  - upload de paires MP3/JSON vers `data/<nom_scene>/` ;
  - contrôle Play/Pause/Resume/Stop, affichage de l’état courant ;
  - réglage des canaux actifs & offsets permanents (persistés dans `config/`) ;
  - accès aux logs et statistiques.
- **Journalisation avancée** : `logger.py` produit des logs quotidiens + fichiers JSON de stats (durées, dérive, cadence de commandes…)
- **Gaze tracking (optionnel)** : `gaze_receiver.py` écoute un flux UDP (`127.0.0.1:5005`) et `SyncPlayer` peut se laisser piloter (cou/yeux) par ces commandes.
- **Interface publique** (`public_interface.py`) : file d’attente visiteurs, WebSocket vers le serveur principal, cooldown par utilisateur ; se lance indépendamment.

## Structure du dépôt

```
.
├── web_app.py            # Serveur Flask + API REST/JSON
├── sync_player.py        # Lecture synchronisée audio/servos
├── rpi_hardware.py       # Pilote PCA9685 + helpers hardware
├── timeline.py           # Chargement / interpolation des timelines
├── logger.py             # Collecte des logs + stats de session
├── gaze_receiver.py      # Réception UDP des données de regard
├── public_interface.py   # UI publique (file d'attente websocket)
├── static/               # Frontend (JS, CSS, viewer logs)
├── templates/            # Templates HTML (interface principale)
├── launch_servo_sync.sh  # Script de lancement (web_app)
├── launch_public.sh      # Script de lancement UI publique
└── config/ & data/       # Créés au runtime pour persistance & sessions
```

## Matériel requis

- Raspberry Pi 4 (ou équivalent Linux + I²C actif)
- Carte PCA9685 (Adresse I²C par défaut `0x40`)
- 4 servos câblés :
  - **CH0** : jaw
  - **CH1** : eye_left
  - **CH2** : eye_right
  - **CH3** : neck_pan
- Alimentation adaptée aux servos + bus I²C câblé.

## Pré-requis logiciels

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg libasound2 i2c-tools pulseaudio pulseaudio-utils pulseaudio-module-bluetooth
```

Les dépendances Python principales : `flask`, `pydub`, `simpleaudio`, `adafruit-circuitpython-pca9685`, `adafruit-blinka`, `websocket-client` (pour l’interface publique). Les scripts `launch_*.sh` créent et alimentent les environnements virtuels nécessaires.

## Installation & lancement rapide

```bash
git clone https://github.com/<votre-compte>/Skull-V2.git
cd Skull-V2
./launch_servo_sync.sh
```

Le script crée `.venv/`, installe les dépendances, prépare `logs/` puis lance `web_app.py` sur `http://localhost:5000`.

### Service systemd (exemple)

```ini
[Unit]
Description=Servo Sync Player
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/skull
ExecStart=/opt/skull/launch_servo_sync.sh
User=skull
Group=skull
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=PULSE_SERVER=unix:/run/user/1000/pulse/native
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Assurez-vous que l’utilisateur (`skull` ici) dispose d’une session user systemd active (`sudo loginctl enable-linger skull`) pour que PulseAudio et le Bluetooth restent disponibles.

## Utilisation de l’interface web

1. **Badge de connexion** (haut droite) : vert lorsque le serveur répond, rouge sinon.
2. **Bloc “Lancement des sessions”** :
   - sélection d’un dossier dans `data/` (1 MP3 + 1 JSON) ;
   - commandes Play/Pause/Resume/Stop (API `/play`, `/pause`, etc.) ;
   - état courant exposé (temps écoulé, servo tracking…).
3. **Préparation & réglages** (accordéon) :
   - **Uploader une session** : choisir un nom de scène → les fichiers sont enregistrés dans `data/<nom_scene>/`.
   - **Canaux actifs** : gel/dégel des servo-channels. L’état est persistant (fichier `config/channels_state.json`).
   - **Ajustements pitch** : offset permanents (°) appliqués par `rpi_hardware.Hardware`. Persistance dans `config/pitch_offsets.json`.
4. **Logs en direct** : iFrame sur `static/logs.html` (SSE et filtres). Les fichiers sont dans `logs/` (`servo_commands_YYYYMMDD.log`, `session_stats_*.json`).

## Format des sessions

Créer un dossier `data/<nom>/` contenant :

- `*.mp3` : audio (utilisé par `pydub`/`simpleaudio`).
- `*.json` : timeline. `timeline.py` supporte plusieurs structures :
  - `{ "timeline": [{"time":..,"motors":{...}}], ... }`
  - `{ "keyframes": {"jaw_deg": [...], ...}, "metadata": {"duration": ...}}`
  - `{ "frames": [{"timestamp_ms":..., ...}] }`
  - Canaux top-level (ex. `"jaw_deg": [{"time":...}]`).

Les angles en pourcentage (`jawOpening` 0-100) sont convertis en degrés automatiquement. Les valeurs sont clampées avec les limites définies dans `Hardware.SPECS`.

## Persistance & configuration

- `config/pitch_offsets.json` : offsets sauvegardés à chaque POST `/pitch`, rechargés au démarrage.
- `config/channels_state.json` : état des cases à cocher (yeux/cou/mâchoire), rechargé au démarrage.
- `logs/` : fichiers journaliers et statistiques (`session_stats_*.json`).
- `data/` : dossiers de sessions utilisateur.

## Interface publique (optionnelle)

`public_interface.py` fournit une UI queue/cooldown (port 5001 par défaut) qui communique avec le serveur principal via WebSocket (`MAIN_WS_URL`). Lancer avec :

```bash
./launch_public.sh
```

Points clés :
- File d’attente persistée (`data/playlist_state.json`).
- Cooldown par utilisateur (UUID navigateur) configurable (`COOLDOWN_MINUTES`).
- Dépend de `websocket-client`; ajuster `MAIN_WS_URL` pour pointer vers `ws://<host>:5000/ws` (implémentation côté serveur à fournir).

## Gaze tracking (optionnel)

`gaze_receiver.py` écoute en UDP (`5005`) et ignore les requêtes dans le process parent du reloader Flask. `SyncPlayer` utilise ces commandes pour piloter cou/yeux (PID simplifié) lorsque `track_enable` est `True`. En absence de flux regard, les valeurs de la timeline sont utilisées.

## Journaux & diagnostics

- `GET /logs?lines=200` → JSON avec les 200 dernières lignes.
- `GET /logs/stream` → flux SSE.
- `GET /logs/stats` → métadonnées récentes.
- `GET /status` → état complet (`running`, `paused`, `session`, `channels`, `track_enable`, diagnostics gaze).

Les scripts front-end (`static/app.js`) affichent un toast & badge OFFLINE si `/status` est inaccessible (backoff 5 s). Un toast “Skull en ligne” s’affiche lors de la reconnexion.

## Audio : bonnes pratiques

- PulseAudio doit tourner sous le même utilisateur que le service (`systemctl --user` recommandé).
- Si vous utilisez une enceinte Bluetooth, définissez le sink par défaut (`pactl set-default-sink ...`).
- Ajoutez `pcm.!default pulse` / `ctl.!default pulse` dans `/etc/asound.conf` pour rediriger ALSA vers PulseAudio.

## Développement

- Activez le mode debug Flask en exportant `FLASK_DEBUG=1` avant de lancer `web_app.py`.
- Le code respecte Python ≥ 3.9. Utilisez `ruff`/`black` pour garder un style cohérent.
- Front-end : JS vanilla (`static/app.js`), CSS (`static/style.css`). L’interface est entièrement statique, aucun bundler requis.
- Les tests matériels ne peuvent être simulés : l’application échoue si les librairies Adafruit ne trouvent pas de bus I²C.

## TODO / pistes

- Finaliser la terminaison WebSocket côté serveur principal pour l’UI publique.
- Ajouter des tests unitaires sur la normalisation `timeline.py`.
- Prévoir une API REST pour activer `track_enable` et surveiller l’état gaze.
- Éventuellement proposer un `requirements.txt` consolidé pour éviter la duplication des installations dans les scripts de lancement.

Bon hack !
