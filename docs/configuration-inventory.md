# Inventaire de configuration — SKULL-08.1 à SKULL-08.4

Statut de `SKULL-08.1` : `VALIDÉ` — inventaire local des sources, des clés,
des propriétaires et des destinations cibles. Les tâches `08.2` à `08.4`
restent des étapes distinctes et ne sont pas déclarées validées par ce
document. Aucune installation, rotation de secret, écriture réseau ou écriture
Raspberry n’a été effectuée.

## Cibles et règles

Le code déployé est immuable dans `/opt/skull/current`. Le TOML actif cible
`/etc/skull/config.toml`, les références de secrets restent dans un fichier
distinct `/etc/skull/secrets.env` ou dans un gestionnaire approuvé, les données
vont dans `/var/lib/skull` et les journaux dans `/var/log/skull`.

La précédence unique est : arguments de maintenance autorisés, variables
d’environnement explicitement listées, fichier TOML, puis valeurs par défaut
sûres. Les arguments HTTP ne peuvent jamais remplacer un réglage matériel.

## Inventaire des clés de la configuration cible

| Clé | Source legacy observée | Type / défaut | Sensible | Propriétaire / destination | Rechargement |
|---|---|---|---|---|---|
| Clé | Source observée | Type / défaut sûr | Sensible | Propriétaire / destination | Rechargement |
| `runtime.mode` | `SKULL_RUNTIME_MODE`, alias `SKULL_HARDWARE_MODE` | enum / `production` | non | runtime / TOML | redémarrage |
| `runtime.app_version` | `SKULL_APP_VERSION` | texte / `dev` | non | release / TOML | redémarrage |
| `http.bind_host` | lanceur WSGI | texte / `127.0.0.1` | non | service HTTP / TOML | redémarrage |
| `http.port` | unité candidate et façade | entier 1–65535 / `5000` | non | service HTTP / TOML | redémarrage |
| `http.request_timeout_s` | nouvelle politique | nombre 0,1–60 / `5.0` | non | service HTTP / TOML | redémarrage |
| `hardware.pca9685_address` | `Hardware`, PCA9685 | entier `0x03`–`0x77` / `0x40` | non | propriétaire matériel / TOML | redémarrage |
| `hardware.frequency_hz` | `PCA9685Controller` | entier 1–1000 / `50` | non | propriétaire matériel / TOML | redémarrage |
| `hardware.servos.jaw.channel` | `rpi_hardware.py`, JSON legacy indirect | entier 0–15 / `0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.jaw.min_deg` | `rpi_hardware.py` | nombre / `110.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.jaw.max_deg` | `rpi_hardware.py` | nombre / `185.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.jaw.neutral_deg` | `rpi_hardware.py` | nombre inclus dans les limites / `145.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.jaw.offset_deg` | `pitch_offsets.json` | nombre -45–45 / `0.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.jaw.enabled` | `channels_state.json` | bool / `true` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_left.channel` | `rpi_hardware.py` | entier 0–15 / `1` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_left.min_deg` | `rpi_hardware.py` | nombre / `60.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_left.max_deg` | `rpi_hardware.py` | nombre / `120.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_left.neutral_deg` | `rpi_hardware.py` | nombre inclus dans les limites / `90.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_left.offset_deg` | `pitch_offsets.json` | nombre -45–45 / `-14.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_left.enabled` | `channels_state.json` | bool / `true` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_right.channel` | `rpi_hardware.py` | entier 0–15 / `2` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_right.min_deg` | `rpi_hardware.py` | nombre / `60.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_right.max_deg` | `rpi_hardware.py` | nombre / `120.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_right.neutral_deg` | `rpi_hardware.py` | nombre inclus dans les limites / `90.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_right.offset_deg` | `pitch_offsets.json` | nombre -45–45 / `0.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.eye_right.enabled` | `channels_state.json` | bool / `true` | non | mécanique / TOML | redémarrage |
| `hardware.servos.neck_pan.channel` | `rpi_hardware.py` | entier 0–15 / `3` | non | mécanique / TOML | redémarrage |
| `hardware.servos.neck_pan.min_deg` | `rpi_hardware.py` | nombre / `0.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.neck_pan.max_deg` | `rpi_hardware.py` | nombre / `180.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.neck_pan.neutral_deg` | `rpi_hardware.py` | nombre inclus dans les limites / `90.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.neck_pan.offset_deg` | `pitch_offsets.json` | nombre -45–45 / `0.0` | non | mécanique / TOML | redémarrage |
| `hardware.servos.neck_pan.enabled` | `channels_state.json` | bool / `true` | non | mécanique / TOML | redémarrage |
| `audio.library_dir` | `DATA_DIR`, `PLAYLIST_LIBRARY_DIR` | chemin / `data` | non | lecture audio / TOML | redémarrage |
| `audio.volume_max` | `PLAYLIST_VOLUME_MAX`, façade volume | entier 0–127 / `127` | non | lecture audio / TOML | redémarrage |
| `audio.output` | sélection PulseAudio | texte / `local` | non | audio / TOML | redémarrage |
| `bluetooth.address` | `.env` Bluetooth, `PLAYLIST_BT_DEVICE_ADDR` | MAC ou vide / vide | non | audio Bluetooth / TOML | redémarrage |
| `bluetooth.name` | `.env` Bluetooth, `PLAYLIST_BT_DEVICE_NAME` | texte informatif / vide | non | audio Bluetooth / TOML | redémarrage |
| `bluetooth.auto_reconnect` | nouvelle politique | bool / `true` | non | audio Bluetooth / TOML | redémarrage |
| `bluetooth.max_attempts` | `PLAYLIST_BT_RECONNECT_MAX_ATTEMPTS` | entier borné / `3` | non | audio Bluetooth / TOML | redémarrage |
| `bluetooth.retry_initial_s` | nouvelle politique | nombre / `1.0` | non | audio Bluetooth / TOML | redémarrage |
| `bluetooth.retry_max_s` | nouvelle politique | nombre / `30.0` | non | audio Bluetooth / TOML | redémarrage |
| `bluetooth.fallback_output` | `PLAYLIST_PULSE_AUDIO_FALLBACK_*` | texte / `local` | non | audio Bluetooth / TOML | redémarrage |
| `esp32.host` | `esp32_settings.json`, `PLAYLIST_ESP32_*` | DNS interne ou vide / vide | non | propriétaire ESP32 / TOML | redémarrage |
| `esp32.port` | `esp32_settings.json` | entier 1–65535 / `80` | non | propriétaire ESP32 / TOML | redémarrage |
| `esp32.enabled` | `esp32_settings.json` | bool / `false` | non | propriétaire ESP32 / TOML | redémarrage |
| `esp32.fallback_host` | configuration DNS explicite | DNS ou vide / vide | non | exploitation réseau / TOML | redémarrage |
| `smoke.enabled` | politique fumée | bool / `false` | non | domotique / TOML | redémarrage |
| `smoke.endpoint_ref` | webhook legacy, `SKULL_SMOKE_WEBHOOK_URL` | référence `env:`/`file:` | oui | secret manager / `/etc/skull/secrets.env` | redémarrage |
| `smoke.timeout_s` | `PLAYLIST_ACCUEIL_WEBHOOK_TIMEOUT` | nombre 0,1–60 / `2.0` | non | domotique / TOML | redémarrage |
| `storage.code_dir` | chemins de déploiement | chemin / `/opt/skull/current` | non | exploitation / TOML | redémarrage |
| `storage.config_file` | chemins de déploiement | chemin / `/etc/skull/config.toml` | non | exploitation / TOML | redémarrage |
| `storage.secrets_file` | chemins de déploiement | chemin / `/etc/skull/secrets.env` | non | exploitation / TOML | redémarrage |
| `storage.data_dir` | `DATA_DIR` | chemin / `/var/lib/skull` | non | données / TOML | redémarrage |
| `storage.log_dir` | `logs`, `SKULL_LOG_*` | chemin / `/var/log/skull` | non | exploitation / TOML | redémarrage |
| `logging.level` | `SKULL_LOG_LEVEL` | enum / `INFO` | non | exploitation / TOML | redémarrage |
| `logging.max_bytes` | `SKULL_LOG_MAX_BYTES` | entier positif / `10485760` | non | exploitation / TOML | redémarrage |
| `logging.backup_count` | `SKULL_LOG_BACKUP_COUNT` | entier positif / `5` | non | exploitation / TOML | redémarrage |
| `security.allowed_env` | liste blanche du loader | liste / valeurs documentées | non | sécurité / TOML | redémarrage |
| `security.redact_configuration` | politique de diagnostic | bool / `true` | non | sécurité / TOML | redémarrage |

Les valeurs mécaniques ci-dessus sont des valeurs observées ou des valeurs
neutres de référence ; elles ne constituent pas une autorisation de modifier
un servo, un offset ou une limite.

## Variables d’environnement legacy supplémentaires

Ces variables sont réellement lues par les lanceurs ou modules actuels mais ne
sont pas toutes encore intégrées au schéma cible. Elles sont donc des entrées
de `SKULL-08.2`/`SKULL-08.3`, et non des réglages cachés à conserver.

| Variable | Consommateur | Défaut observé | Sensibilité / destination cible |
|---|---|---|---|
| `SKULL_WSGI_BIND`, `SKULL_WSGI_TIMEOUT`, `SKULL_WSGI_GRACEFUL_TIMEOUT` | Gunicorn | loopback:5002, 30, 10 | non / `http` et exploitation |
| `SKULL_LOG_STREAM_WINDOW_SECONDS`, `SKULL_LOG_STREAM_POLL_INTERVAL` | `web_app.py` | 0.5, 0.1 | non / `logging` |
| `SKULL_RUNTIME_LOCK_PATH`, `SKULL_RUNTIME_LOCK_TIMEOUT` | verrou runtime | temporaire + `skull-runtime.lock`, 2.0 | non / `runtime` |
| `PLAYLIST_LIBRARY_DIR`, `PLAYLIST_COOLDOWN` | `playlist_web.py` | `data`, 180 | non / `audio` et compatibilité |
| `PLAYLIST_BACKEND_BASE` | proxy playlist | dérivé de l’hôte HTTP | non / `http` |
| `PLAYLIST_FORWARD_TIMEOUT`, `PLAYLIST_FORWARD_CONNECT_TIMEOUT` | proxy playlist | 10, 2 | non / `http.request_timeout_s` |
| `PLAYLIST_STATUS_TIMEOUT`, `PLAYLIST_STATUS_CONNECT_TIMEOUT` | proxy playlist | 6, 2 | non / `http.request_timeout_s` |
| `PLAYLIST_VOLUME_TIMEOUT`, `PLAYLIST_VOLUME_STEP`, `PLAYLIST_VOLUME_CLI` | volume legacy | 5, 8, `bluetoothctl` | non / `audio` |
| `PLAYLIST_BT_CONNECT_COMMAND_TIMEOUT` | Bluetooth legacy | 20 | non / `bluetooth` |
| `PLAYLIST_PULSE_AUDIO_TIMEOUT`, `PLAYLIST_PULSE_AUDIO_WAIT_TIMEOUT`, `PLAYLIST_PULSE_AUDIO_POLL_INTERVAL`, `PLAYLIST_PULSE_AUDIO_CLI` | PulseAudio | 5, 5, 0.2, `pactl` | non / `audio` |
| `PLAYLIST_PULSE_AUDIO_FALLBACK_SINK`, `PLAYLIST_PULSE_AUDIO_FALLBACK_ENABLED` | PulseAudio | vide, faux | non / `bluetooth.fallback_output` |
| `PLAYLIST_ESP32_TIMEOUT`, `PLAYLIST_ESP32_CONNECT_TIMEOUT` | HTTP ESP32 | 3.0, 1.0 | non / `esp32` |
| `PLAYLIST_ESP32_STATUS_INTERVAL`, `PLAYLIST_ESP32_STATUS_INITIAL_BACKOFF`, `PLAYLIST_ESP32_STATUS_MAX_BACKOFF` | superviseur ESP32 | 5, 5, 60 | non / `esp32` |
| `PLAYLIST_ESP32_STATUS_FAILURE_THRESHOLD`, `PLAYLIST_ESP32_STATUS_CIRCUIT_COOLDOWN` | superviseur ESP32 | 3, 30 | non / `esp32` |
| `PLAYLIST_BT_RECONNECT_INTERVAL`, `PLAYLIST_BT_RECONNECT_CONNECT_TIMEOUT` | reconnexion Bluetooth | 10, 3 | non / `bluetooth` |
| `PLAYLIST_BT_RECONNECT_INITIAL_DELAY`, `PLAYLIST_BT_RECONNECT_MAX_DELAY` | reconnexion Bluetooth | 0.5, 8 | non / `bluetooth` |
| `PLAYLIST_SERVICE_RESTART_CMD`, `PLAYLIST_SERVICE_RESTART_TIMEOUT` | administration legacy | commande systemd historique, 15 | commande privilégiée / sécurité |
| `PLAYLIST_BLUETOOTH_RESTART_CMD`, `PLAYLIST_BLUETOOTH_RESTART_TIMEOUT` | administration Bluetooth | commande systemd historique, 15 | commande privilégiée / sécurité |
| `PLAYLIST_TRANSITION_HOLD` | lecture/ESP32 | 4.0 | non / `runtime` |
| `GAZE_FORCE_START`, `FLASK_DEBUG`, `WERKZEUG_RUN_MAIN` | démarrage gaze/reloader | absentes ou faux | contrôle de processus / runtime |
| `PULSE_SERVER`, `XDG_RUNTIME_DIR` | contexte PulseAudio/verrou | fourni par session | non / exploitation, jamais secret |

`PLAYLIST_ACCUEIL_WEBHOOK` et `SKULL_SMOKE_WEBHOOK_URL` sont regroupées sous
`smoke.endpoint_ref`. Leur contenu n’est volontairement ni inventorié, ni
affiché, ni copié. La tâche `SKULL-08.5` est annulée ; aucune sonnette ni
automatisation Home Assistant ne doit être reconfigurée dans cette phase.

## Fichiers legacy et constantes non sensibles

| Source | Clés ou contenu | Consommateur | Destination cible |
|---|---|---|---|
| `config/pitch_offsets.json` | quatre offsets de servo | `web_app.py` / `Hardware` | `hardware.servos.*.offset_deg` |
| `config/channels_state.json` | quatre activations logiques | `web_app.py` / `SyncPlayer` | `hardware.servos.*.enabled` |
| `config/esp32_settings.json` | `host`, `port`, `enabled` | passerelle et superviseur ESP32 | `esp32.*` |
| `config/esp32_button_categories.json` | `assignments` | routes de configuration ESP32 | phase IoT, puis `esp32` |
| `config/session_categories.json` | `categories`, `sessions` | catalogue et IHM playlist | `/var/lib/skull` |
| `config/bluetooth_device.env` | adresse et nom Bluetooth | unité systemd / audio | `bluetooth.address`, `bluetooth.name` |
| `config/loop_audio/*.mp3` | audio de boucle | `LoopPlayer` | `/var/lib/skull` |
| `data/<session>/*` | JSON timeline et MP3 | catalogue/lecture | `/var/lib/skull` |
| `logs/*`, `session_stats_*.json` | journaux et statistiques | logger/IHM | `/var/log/skull` |
| `127.0.0.1:5005` | gaze UDP local | `GazeReceiver` | configuration runtime locale |
| adresse historique du backend playlist | URL codée dans le lanceur legacy | `playlist_web.py` | nom DNS interne, traité par `SKULL-08.6` |

## Vérification de l’ordre des tâches suivantes

- `SKULL-08.2` est bien nécessaire : le modèle typé doit devenir la validation
  obligatoire de toutes les clés ci-dessus, avant toute initialisation matérielle.
  Une partie du code existe déjà localement, mais sa preuve d’acceptation reste
  à produire séparément.
- `SKULL-08.3` est bien nécessaire : les modules legacy lisent encore des
  variables à l’import ; il faut imposer une seule précédence et supprimer les
  surcharges implicites.
- `SKULL-08.4` est bien nécessaire : les cinq JSON et le `.env` Bluetooth
  restent des sources de production à convertir et comparer sans les supprimer.
- `SKULL-08.5` est annulée par décision écrite : aucune rotation et aucune
  reconfiguration de la sonnette ne sont à faire.
- `SKULL-08.6` est bien nécessaire : le lanceur contient encore une dépendance
  d’adresse historique et la panne DNS doit rester visible et bornée.
- `SKULL-08.7` est déjà validée pour le déploiement réalisé ; elle devra être
  recontrôlée seulement après les changements locaux qui modifieraient la
  configuration candidate.

## Migration et limites

`config.migrate_legacy.convert_legacy_config` lit uniquement une copie des
anciens JSON et `.env`, refuse d’écraser sa cible, génère un TOML déterministe
et un rapport trié. Une valeur de webhook est seulement signalée comme
`redacted` et convertie en référence ; elle n’est jamais copiée dans le TOML,
le rapport ou les tests.

La validation hors matériel est disponible par `python -m config.validate
config/skull.example.toml` ; sa sortie est redigée et inclut la provenance des
valeurs non sensibles.

`config.secrets.resolve_secret` ne résout qu’une référence `env:NAME` ou
`file:/chemin/absolu`. Le contenu retourné est destiné au consommateur runtime
et n’est ni affiché ni inclus dans une erreur. Les permissions du fichier réel
et la rotation restent à démontrer sur la cible, hors de cette phase locale.

La création d’enregistrements DNS reste réservée à une phase réseau approuvée ;
`SKULL-08.6` ne modifie donc aucun DNS et ne prétend pas valider une résolution
réelle. Les fichiers actifs et les secrets de production restent hors Git.

## Dépendances DNS internes — SKULL-08.6

| Dépendance | Propriétaire attendu | Usage | État observé depuis le poste de travail |
|---|---|---|---|
| `skull.home.arpa` | DNS interne du réseau IoT | backend Skull et cible d’administration applicative | résout vers l’adresse actuelle du Skull |
| `ha.home.arpa` | DNS interne / administration domotique | cible Home Assistant, lorsque le flux sera approuvé | résout ; l’adresse retournée ne constitue pas une preuve depuis le Skull |
| ESP32 boutons | DNS interne / administration IoT | supervision et passerelle HTTP | aucun nom DNS de production approuvé ; l’ancien hôte reste désactivé |

Le lanceur `launch_playlist_web.sh` utilise désormais `skull.home.arpa:5000`
par défaut. Une valeur `PLAYLIST_BACKEND_BASE` ne remplace ce nom que si elle
est fournie explicitement ; aucune IP legacy n’est utilisée en silence. Les
ACL, routes et enregistrements restent inchangés et doivent être traités dans
la phase réseau approuvée.
