# SKULL-06.6 — adaptateurs et injection

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Résultat

`adapters_runtime.py` ajoute les implémentations injectables des six
frontières : PCA9685, audio legacy, Bluetooth/BlueZ, HTTP ESP32, webhook de
fumée et gaze. Le module n’importe aucun client Raspberry et n’effectue aucun
appel à l’import.

`BluetoothctlAdapter` centralise la construction et le parsing des commandes
Bluetooth. `ESP32HTTPAdapter` centralise URL, requêtes JSON et timeouts. Les
erreurs techniques sont traduites en erreurs métier stables. `PlaybackService`
reçoit ses adaptateurs par constructeur et orchestre le cycle de lecture sans
singleton caché.

## Vérifications

- Tests ciblés : 86 passés.
- Suite complète : 202 tests passés, 1 avertissement externe connu.
- Compilation Python : OK.
- `git diff --check` : OK ; seuls les avertissements de fins de ligne Git
  existants sont signalés.
- Aucun secret, webhook complet, adresse réseau, MAC ou contenu de production
  n’est présent dans cette preuve.

## Limites

- La façade web legacy n’est pas encore recâblée sur ces wrappers ; cela est
  réservé à `SKULL-06.7`.
- Aucun Raspberry, service distant ou matériel n’a été sollicité.
