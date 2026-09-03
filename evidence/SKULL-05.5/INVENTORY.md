# SKULL-05.5 — inventaire runtime

## Périmètre

Inventaire statique de la candidate locale dans
`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`. Aucun Raspberry,
service, périphérique Bluetooth ou réseau réel n’a été sollicité.

| Fonction | Fichier / appel | Médium | Borne |
|---|---|---|---|
| Webhook fumée `Accueil` | `web_app.py` → `subprocess.run(curl)` | processus + HTTP sortant | `ACCUEIL_WEBHOOK_TIMEOUT`, total |
| ESP32 | `web_app.py` → `urllib.request.urlopen` | HTTP TCP | borne la plus stricte de `ESP32_CONNECT_TIMEOUT`/`ESP32_TOTAL_TIMEOUT` |
| Interface playlist → Skull | `playlist_web.py` → `requests.get/post` | HTTP TCP | couple connexion/lecture, variables `PLAYLIST_*_TIMEOUT` |
| Bluetooth / volume / scan / appairage | `web_app.py` → `subprocess.run(bluetoothctl)` | processus + BlueZ/DBus | `VOLUME_TIMEOUT`, total par commande |
| Redémarrage services | `web_app.py` → `subprocess.run(systemctl)` | processus + systemd | `SERVICE_RESTART_TIMEOUT` / `BLUETOOTH_RESTART_TIMEOUT` |
| Gaze | `gaze_receiver.py` → UDP `127.0.0.1:5005` | socket local non bloquant | `setblocking(False)`, TTL de commande |

Les appels `requests`, `urlopen` et `subprocess.run` de l’application sont
contrôlés par un test AST qui échoue si le mot-clé `timeout` disparaît. Les
commandes d’installation (`apt`, `pip`, `git`) restent hors du chemin de
requête/runtime et relèvent de la procédure de déploiement.

## Changements 05.5

- `ExecStartPre` ne tente plus `bluetoothctl connect` ; l’enceinte peut être
  éteinte au démarrage.
- Le journal servo est rotatif (10 MiB + 5 sauvegardes par défaut), les stats
  sont conservées sur 100 sessions, et les modes Linux visent `0750`/`0640`.
- Une panne de stockage des logs ne fait pas tomber le runtime : un handler
  standard de secours est utilisé.
- Les erreurs réseau et webhook renvoient des messages métier contrôlés ; URL
  webhook, tokens et identifiants d’URL ne sont pas recopiés.
