# Résultat SKULL-08.2

- Date : 4 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : validation typée de la configuration cible et garde-fou de
  démarrage avant toute initialisation matérielle.
- Fichiers modifiés : `web_app.py`,
  `tests/unit/test_startup_determinism.py` et cette preuve.
- Aucun Raspberry, service distant, DNS, Bluetooth, audio, servo ou webhook
  réel n’a été sollicité.

## Résultat obtenu

- `config.schema` couvre les sections `runtime`, `http`, `hardware`, `audio`,
  `bluetooth`, `esp32`, `smoke`, `storage`, `logging` et `security`.
- Les types, plages, clés inconnues, adresses Bluetooth, noms DNS ESP32,
  références de secret et contraintes croisées des servos sont validés avec
  un chemin de clé exploitable.
- Les quatre servos vérifient notamment l’unicité des canaux, l’ordre
  minimum/maximum et l’inclusion du neutre dans les limites.
- La configuration est immuable après chargement ; les diagnostics remplacent
  la valeur de secret par une référence neutre.
- `web_app.initialize_runtime()` charge et valide la configuration typée avant
  l’import ou la construction de `SyncPlayer` et `LoopPlayer`.
- Une configuration invalide échoue donc avant tout accès matériel et conserve
  le runtime non initialisé.

## Vérifications

- `python -m pytest -q tests/config tests/unit/test_startup_determinism.py tests/unit/test_healthchecks.py`
  → `38 passed`, un avertissement externe connu `pydub/audioop`.
- `python -m pytest -q` → `271 passed`, un avertissement externe connu
  `pydub/audioop`.
- `python -m compileall -q config web_app.py tests` → succès.
- `git diff --check` → aucune erreur.
- Contrôle ciblé du diff → aucune URL complète ni affectation de secret.

## Tâches suivantes vérifiées

- `SKULL-08.3` reste nécessaire pour formaliser et réduire les lectures
  d’environnement legacy à la précédence unique documentée.
- `SKULL-08.4` reste nécessaire pour comparer les données réelles legacy et
  le TOML candidat sans supprimer les sources.
- `SKULL-08.5` reste annulée ; aucune rotation ni reconfiguration de sonnette.
- `SKULL-08.6` reste partielle pour le DNS réel, la panne DNS et la
  coexistence réseau.
- `SKULL-08.7` reste validée pour le déploiement déjà effectué ; elle devra
  être recontrôlée après une nouvelle configuration déployée.

## Écarts ou risques restants

- Le schéma est chargé au démarrage mais ses valeurs ne remplacent pas encore
  toutes les constantes legacy des consommateurs ; cette intégration
  progressive relève de `08.3` et `08.4`.
- La preuve est locale et ne constitue pas une validation matérielle.

## Rollback

Le changement est local et réversible : restaurer `web_app.py` et le test
depuis le commit précédent, puis supprimer uniquement le dossier de preuve de
`SKULL-08.2`. Aucun état distant ou matériel n’a changé.
