# Précédence de configuration

Cette règle concerne le chargeur typé de la phase 8. Elle est unique et
déterministe, du plus prioritaire au moins prioritaire :

1. arguments de maintenance internes autorisés ;
2. variables d’environnement explicitement listées ;
3. fichier TOML explicite, par défaut `/etc/skull/config.toml` ;
4. valeurs par défaut sûres du schéma.

Le répertoire courant n’est jamais utilisé pour sélectionner le fichier TOML
par défaut. Un chemin différent doit être fourni explicitement au chargeur ou
au validateur hors production.

## Surcharges autorisées

Les seuls arguments de maintenance autorisés sont :

- `runtime.mode` ;
- `logging.level`.

Ils ne sont pas issus d’une requête HTTP et ne peuvent pas modifier un canal,
un offset, une limite, un périphérique audio ou un autre réglage matériel.

Les variables d’environnement autorisées par le chargeur typé sont :

| Variable | Clé cible | Type |
|---|---|---|
| `SKULL_HARDWARE_MODE` | `runtime.mode` | mode legacy |
| `SKULL_RUNTIME_MODE` | `runtime.mode` | mode |
| `SKULL_APP_VERSION` | `runtime.app_version` | texte |
| `SKULL_HTTP_BIND_HOST` | `http.bind_host` | texte |
| `SKULL_HTTP_PORT` | `http.port` | entier |
| `SKULL_HARDWARE_I2C_ADDRESS` | `hardware.pca9685_address` | entier |
| `SKULL_HARDWARE_FREQUENCY_HZ` | `hardware.frequency_hz` | entier |
| `SKULL_AUDIO_LIBRARY_DIR` | `audio.library_dir` | texte |
| `SKULL_AUDIO_VOLUME_MAX` | `audio.volume_max` | entier |
| `SKULL_BLUETOOTH_ADDRESS` | `bluetooth.address` | MAC |
| `SKULL_BLUETOOTH_AUTO_RECONNECT` | `bluetooth.auto_reconnect` | booléen |
| `SKULL_BLUETOOTH_MAX_ATTEMPTS` | `bluetooth.max_attempts` | entier |
| `SKULL_ESP32_HOST` | `esp32.host` | nom DNS |
| `SKULL_ESP32_PORT` | `esp32.port` | entier |
| `SKULL_ESP32_ENABLED` | `esp32.enabled` | booléen |
| `SKULL_SMOKE_ENABLED` | `smoke.enabled` | booléen |
| `SKULL_SMOKE_WEBHOOK_REF` | `smoke.endpoint_ref` | référence |
| `SKULL_LOG_LEVEL` | `logging.level` | niveau |

`SKULL_RUNTIME_MODE` est prioritaire sur l’alias legacy
`SKULL_HARDWARE_MODE` lorsqu’ils sont présents simultanément. La valeur d’une
référence de secret n’est jamais affichée ; seule sa provenance non sensible
peut apparaître dans un diagnostic.

## Compatibilité legacy

Les modules historiques lisent encore certaines variables `PLAYLIST_*`, les
fichiers JSON et le `.env` Bluetooth. Elles sont inventoriées dans
[`configuration-inventory.md`](configuration-inventory.md), mais ne peuvent
pas introduire une nouvelle clé dans le chargeur typé. Leur absorption
progressive relève de `SKULL-08.4`; cette compatibilité ne change pas la règle
de précédence du nouveau chargeur.

## Diagnostic et vérification

`config.validate` affiche la provenance des valeurs non sensibles et remplace
la valeur du endpoint fumée par une référence neutre. Les collisions entre
défauts, TOML, environnement et arguments de maintenance sont testées dans
`tests/config/test_schema.py`. Une configuration invalide est rejetée avant
toute initialisation matérielle.
