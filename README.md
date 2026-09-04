# Skull Servo Sync Player

Plateforme de pilotage d’un crâne animatronique : synchronisation de quatre servos avec un MP3, interface web moderne pour charger des sessions, ajuster les offsets, suivre les logs en direct et exposer une interface publique facultative.

Fichiers de pilotage du projet :

- [OBJECTIF.md](OBJECTIF.md) : cible et contraintes non négociables ;
- [TODO.md](TODO.md) : ordre des travaux et validations ;
- [MEMOIRE.md](MEMOIRE.md) : état observé et décisions prises ;
- [OPERATIONS.md](OPERATIONS.md) : exploitation, architecture et procédures ;
- [LUNA.md](LUNA.md) : protocole obligatoire pour confier une tâche à Luna ;
- [tasks/README.md](tasks/README.md) : fiches d’exécution détaillées par phase.

## Tableau de mission local

`TODO.md` reste la source de vérité. Pour afficher son état dans une IHM web
locale, lancer depuis PowerShell :

```powershell
& "C:\Skull-V2\Start-SkullTaskDashboard.ps1"
```

Le tableau de bord s'ouvre sur `http://127.0.0.1:5055`, relit `TODO.md` toutes
les cinq secondes et n'écrit rien dans le dépôt. Les tâches validées comptent
pour 100 % et les tâches partielles pour 50 % dans l'indicateur global.


## Installation automatisee

### Prerequis
- Debian / Raspberry Pi OS avec sudo
- Connexion Internet
- Optionnel : definir `SKULL_INSTALL_USER` pour viser un autre compte utilisateur que celui qui lance `sudo`

### Procedure rapide
1. Cloner le depot puis se placer a la racine : `git clone https://github.com/IM-Lab-france/Skull-V2.git && cd Skull-V2`
2. Rendre le script executable : `chmod +x install_skull.sh`
3. Lancer l'installation : `sudo ./install_skull.sh`
4. (Facultatif) relancer le service plus tard : `sudo systemctl restart servo-sync.service`

Le script realise automatiquement :
- installation / mise a jour des paquets systeme indispensables (git, python3, ffmpeg, pulseaudio, bluetooth, etc.) ;
- activation de l'I2C et configuration de `bluetoothctl` avec demande d'appairage et memorisation de l'enceinte ;
- clonage / mise a jour du code Skull-V2 dans `/opt/skull` et creation de l'environnement Python ;
- generation / activation du service systemd `servo-sync.service` (logs bornes et reconnexion Bluetooth a la demande).

Si vous devez relancer l'installation, vous pouvez remettre a zero le fichier `config/bluetooth_device.env` pour choisir une autre enceinte, ou reexecuter simplement le script qui vous proposera la selection des peripheriques.

### Recuperer et lancer le script

```bash
wget -O install_skull.sh https://raw.githubusercontent.com/IM-Lab-france/Skull-V2/main/install_skull.sh
chmod +x install_skull.sh
sudo ./install_skull.sh
```

Astuce : pour passer l'etape d'appairage Bluetooth (par exemple en installation non surveillee), executer `SKULL_SKIP_BLUETOOTH=1 sudo ./install_skull.sh`. Le script prepare egalement l'environnement de l'interface playlist (virtualenv dedie) et active les services systemd `servo-sync.service` et `playlist-web.service`.

## Aperçu fonctionnel

- **Synchronisation audio/servos** : `sync_player.py` lit un MP3 tout en rejouant une timeline JSON (différents formats acceptés) à 60 fps.
- **Pilotage matériel** : `rpi_hardware.py` s’appuie sur la carte PCA9685 (I²C) pour commander « jaw », « eye_left », « eye_right », « neck_pan » avec clamps mécaniques et logging systématique.
- **Interface web Flask** (`web_app.py`) :
  - upload de paires MP3/JSON vers `data/<nom_scene>/` ;
  - contrôle Play/Pause/Resume/Stop, affichage de l’état courant ;
  - réglage des canaux actifs & offsets permanents (persistés dans `config/`) ;
  - accès aux logs et statistiques.
- **Journalisation avancée** : `logger.py` produit des logs quotidiens rotatifs + fichiers JSON de stats (durées, dérive, cadence de commandes…)
- **Gaze tracking (optionnel)** : `gaze_receiver.py` écoute un flux UDP (`127.0.0.1:5005`) et `SyncPlayer` peut se laisser piloter (cou/yeux) par ces commandes.
- **Interface playlist publique** (`playlist_web.py`) : file d’attente visiteurs, cooldown par utilisateur et appels HTTP vers le serveur principal ; se lance indépendamment.

## Structure du dépôt

```
.
├── web_app.py            # Serveur Flask + API REST/JSON
├── sync_player.py        # Lecture synchronisée audio/servos
├── rpi_hardware.py       # Pilote PCA9685 + helpers hardware
├── timeline.py           # Chargement / interpolation des timelines
├── logger.py             # Collecte des logs + stats de session
├── gaze_receiver.py      # Réception UDP des données de regard
├── playlist_web.py       # UI publique (file d'attente HTTP)
├── static/               # Frontend (JS, CSS, viewer logs)
├── templates/            # Templates HTML (interface principale)
├── launch_servo_sync.sh  # Script de lancement (web_app)
├── launch_playlist_web.sh # Script de lancement UI publique
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
- `logs/` : fichiers journaliers rotatifs et statistiques (`session_stats_*.json`).
- La limite par défaut est de 10 MiB pour le fichier courant, avec 5 rotations
  conservées (environ 60 MiB maximum pour le journal servo) ; les statistiques
  conservent les 100 dernières sessions. Les paramètres sont
  `SKULL_LOG_MAX_BYTES`, `SKULL_LOG_BACKUP_COUNT` et `SKULL_STATS_RETENTION`.
- Sous Linux, le répertoire de logs est créé en `0750` et les fichiers en
  `0640`, avec le propriétaire du service. Si le stockage devient indisponible,
  l’application continue sur le journal de secours standard et signale la perte
  de persistance sans interrompre le runtime.
- `data/` : dossiers de sessions utilisateur.

## Interface publique (optionnelle)

`playlist_web.py` fournit une UI queue/cooldown (port 5050 par défaut) qui communique avec le serveur principal par HTTP. Lancer avec :

```bash
./launch_playlist_web.sh
```

Points clés :
- File d’attente persistée (`data/playlist_state.json`).
- Cooldown par utilisateur (UUID navigateur) configurable (`COOLDOWN_MINUTES`).
- L’URL du backend est définie par `PLAYLIST_BACKEND_BASE`.

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
- Exportez `PLAYLIST_BT_DEVICE_ADDR=AA:BB:CC:DD:EE:FF` (adresse MAC) pour que
  le serveur tente une reconnexion `bluetoothctl connect` lors des opérations
  qui en ont besoin (lecture, volume et état). La connexion n’est plus une
  précondition `ExecStartPre` : l’application peut démarrer enceinte éteinte.

## Timeouts et erreurs externes

- Les commandes `bluetoothctl`, `curl` et systemd utilisent un timeout total
  borné.
- Les appels HTTP ESP32 et playlist utilisent un timeout de socket/lecture et
  des limites de connexion configurées par environnement ; aucune URL webhook,
  clé ou valeur de secret n’est renvoyée dans les erreurs applicatives.
- Les appels vers l’ESP32 restent désactivés tant que la configuration n’est
  pas activée et valide.

## Candidate parallèle

La candidate WSGI locale se lance sur `127.0.0.1:5002` avec un seul worker via
`launch_wsgi.sh`. L’unité `deploy/skull-candidate.service.example` est un
modèle de validation, dans un chemin distinct, en mode simulé et sans activation
systemd automatique. La matrice des contrats legacy est conservée dans
`evidence/SKULL-05.6/ROUTE-MATRIX.md`.

## Développement

- En production, utilisez `launch_wsgi.sh` ou le service systemd ; le lancement
  applicatif force `debug=False` et désactive le reloader.
- Le code respecte Python ≥ 3.9. Utilisez `ruff`/`black` pour garder un style cohérent.
- Front-end : JS vanilla (`static/app.js`), CSS (`static/style.css`). L’interface est entièrement statique, aucun bundler requis.
- Les tests matériels ne peuvent être simulés : l’application échoue si les librairies Adafruit ne trouvent pas de bus I²C.

## TODO / pistes

- Ajouter une procédure de sauvegarde/restauration et des tests de validation des sessions.
- Ajouter des tests unitaires sur la normalisation `timeline.py`.
- Prévoir une API REST pour activer `track_enable` et surveiller l’état gaze.
- Éventuellement proposer un `requirements.txt` consolidé pour éviter la duplication des installations dans les scripts de lancement.

Bon hack !
