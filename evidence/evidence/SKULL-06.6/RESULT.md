# SKULL-06.6 — adaptateurs et injection

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Travail effectué uniquement dans le worktree local de production.
- Aucun accès au Raspberry, aucun redémarrage et aucune action matérielle.
- Les changements existants des tâches précédentes ont été conservés.
- Aucun commit ni push effectué.

## Réalisation

- Ajout de `adapters_runtime.py` avec wrappers injectables pour PCA9685, audio,
  Bluetooth/BlueZ, HTTP ESP32, fumée et gaze.
- Aucun client matériel ou réseau n’est construit à l’import du module.
- Le wrapper Bluetooth possède la construction des commandes et le parsing des
  listes et états `bluetoothctl`.
- Le wrapper ESP32 possède la construction HTTP, le décodage JSON et le
  timeout borné.
- Les détails techniques sont convertis en `InvalidInputError`,
  `NotFoundError` ou `DependencyUnavailableError` sans retransmettre de
  chemin, secret ou contenu sensible.
- Ajout de `services/playback.py`, dont les six dépendances sont reçues par
  constructeur ; le service conserve le comportement fumée non fatal de la
  façade actuelle.

## Vérifications

- Tests ciblés adaptateurs, service et régression état : 86 passés.
- `python -m pytest -q` : 202 tests passés, 1 avertissement externe connu.
- `python -m compileall -q .` : OK.
- `git diff --check` : OK ; avertissements de fins de ligne Git existants.
- Tests de panne indépendants : servo, audio, Bluetooth, ESP32, fumée et gaze.
- Tests de contrats HTTP legacy : inclus dans la suite complète et verts.
- Scan ciblé des secrets et URL sensibles : aucune valeur détectée.

## Limites et suite

- La façade `web_app.py` conserve ses appels legacy pendant cette étape ; le
  recâblage contrôlé des routes relève de `SKULL-06.7`.
- Aucune validation physique n’est incluse.
- Prochaine tâche autorisée : `SKULL-06.7`.
