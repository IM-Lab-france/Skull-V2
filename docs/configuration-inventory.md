# Inventaire de configuration — SKULL-08.1 à SKULL-08.4

Statut local : `PARTIEL` — schéma, précédence et convertisseur sont présents ;
aucune installation, rotation de secret, écriture réseau ou écriture Raspberry
n’a été effectuée.

## Cibles et règles

Le code déployé est immuable dans `/opt/skull/current`. Le TOML actif cible
`/etc/skull/config.toml`, les références de secrets restent dans un fichier
distinct `/etc/skull/secrets.env` ou dans un gestionnaire approuvé, les données
vont dans `/var/lib/skull` et les journaux dans `/var/log/skull`.

La précédence unique est : arguments de maintenance autorisés, variables
d’environnement explicitement listées, fichier TOML, puis valeurs par défaut
sûres. Les arguments HTTP ne peuvent jamais remplacer un réglage matériel.

## Inventaire

| Clé | Source legacy observée | Type / défaut | Sensible | Propriétaire / destination | Rechargement |
|---|---|---|---|---|---|
| `runtime.mode` | `SKULL_HARDWARE_MODE` | texte / `production` | non | runtime / TOML | redémarrage |
| `runtime.app_version` | `SKULL_APP_VERSION` | texte / `dev` | non | runtime / TOML | redémarrage |
| `http.bind_host`, `http.port` | lanceurs WSGI et web | texte, entier / loopback, port valide | non | service HTTP / TOML | redémarrage |
| `hardware.pca9685_address` | pilote PCA9685 | entier / adresse I²C sûre | non | propriétaire matériel / TOML | redémarrage |
| `hardware.frequency_hz` | pilote PCA9685 | entier / `50` | non | propriétaire matériel / TOML | redémarrage |
| `hardware.servos.*` | pilote et JSON d’offsets | table typée / valeurs validées | non | propriétaire mécanique / TOML | redémarrage |
| `audio.library_dir`, `volume_max` | JSON et variables `PLAYLIST_*` | texte, entier / `data`, `127` | non | lecture audio / TOML | redémarrage |
| `bluetooth.*` | `.env` Bluetooth et variables legacy | texte, bool, entiers / reconnexion bornée | non | audio Bluetooth / TOML | redémarrage |
| `esp32.host`, `port`, `enabled` | `esp32_settings.json` | texte, entier, bool / désactivé | non | propriétaire ESP32 / TOML | redémarrage |
| `smoke.enabled`, `timeout_s` | variables legacy | bool, nombre / désactivé, borne | non | service fumée / TOML | redémarrage |
| `smoke.endpoint_ref` | webhook legacy | référence `env:` ou `file:` | oui | gestionnaire de secrets approuvé | redémarrage |
| `storage.*` | chemins d’installation | texte / chemins cibles | non | exploitation / TOML | redémarrage |
| `logging.*` | variables `SKULL_LOG_*` | niveau, entiers / valeurs sûres | non | exploitation / TOML | redémarrage |
| `security.*` | nouvelle politique | liste, bool / filtrage actif | non | sécurité / TOML | redémarrage |

## Migration et limites

`config.migrate_legacy.convert_legacy_config` lit uniquement une copie des
anciens JSON et `.env`, refuse d’écraser sa cible, génère un TOML déterministe
et un rapport trié. Une valeur de webhook est seulement signalée comme
`redacted` et convertie en référence ; elle n’est jamais copiée dans le TOML,
le rapport ou les tests.

La validation hors matériel est disponible par `python -m config.validate
config/skull.example.toml` ; sa sortie est redigée et inclut la provenance des
valeurs non sensibles.

La rotation du secret fumée reste `BLOQUÉE` sans confirmation explicite et sans
accès au consommateur domotique. La création d’enregistrements DNS reste
réservée à une phase réseau approuvée ; cette phase ne modifie donc aucun DNS
et ne prétend pas valider une résolution.
