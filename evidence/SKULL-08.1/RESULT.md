# Résultat SKULL-08.1

- Date : 4 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : inventaire local des sources de configuration, des clés,
  propriétaires, destinations cibles, valeurs par défaut non sensibles,
  paramètres matériels et dépendances réseau.
- Fichiers modifiés : `docs/configuration-inventory.md` et cette preuve.
- Aucun Raspberry, service distant, DNS, Bluetooth, audio, servo ou webhook
  réel n’a été sollicité.

## Résultat obtenu

- Les clés de la configuration cible sont recensées individuellement pour les
  sections `runtime`, `http`, `hardware`, `audio`, `bluetooth`, `esp32`,
  `smoke`, `storage`, `logging` et `security`.
- Les quatre servos sont documentés avec canal, limites, neutre, offset et
  activation logique.
- Les variables d’environnement réellement lues par les modules legacy, le
  proxy playlist, Gunicorn, le logger, le verrou runtime et l’installateur
  sont distinguées des messages de journalisation qui ne sont pas des clés de
  configuration.
- Les JSON legacy, le `.env` Bluetooth, les données, les boucles audio et les
  journaux ont une destination cible et un propriétaire fonctionnel.
- Les adresses réseau codées en dur et le endpoint fumée sont identifiés sans
  reproduire leur valeur sensible. Le endpoint fumée est uniquement décrit
  comme une référence à externaliser ; aucune modification de sonnette n’est
  incluse.

## Commandes de validation

- `python -m pytest -q tests/config tests/test_configuration_examples.py`
  → `32 passed`.
- `python -m config.validate config/skull.example.toml` → succès ; la sortie
  de configuration est redigée.
- `git diff --check` → aucune erreur.
- Contrôle ciblé du diff → aucune URL complète et aucune affectation de secret
  détectées.
- Relecture de `tasks/08-CONFIGURATION.md` → chaque clé inventoriée possède un
  propriétaire et une destination cible dans l’inventaire.

## Tâches suivantes vérifiées

- `SKULL-08.2` est nécessaire pour transformer cet inventaire en validation
  obligatoire avant initialisation matérielle. Le code de schéma présent doit
  encore recevoir sa preuve dédiée.
- `SKULL-08.3` est nécessaire car des modules legacy lisent encore des
  variables d’environnement à l’import ; la précédence doit devenir unique et
  explicite.
- `SKULL-08.4` est nécessaire tant que les JSON et le `.env` legacy n’ont pas
  été comparés aux données réelles, sans suppression des sources.
- `SKULL-08.5` est annulée et ne doit pas être exécutée.
- `SKULL-08.6` est nécessaire pour traiter l’adresse historique du proxy et
  prouver les erreurs DNS bornées ; aucun changement DNS n’est inclus ici.
- `SKULL-08.7` est déjà validée pour le déploiement précédent et ne sera
  recontrôlée qu’après une modification de la configuration candidate.

## Écarts ou risques restants

- L’inventaire est local ; il ne prétend pas confirmer les valeurs actuellement
  installées sur le Raspberry.
- Les paramètres mécaniques sont documentés, mais aucune modification de servo,
  offset ou limite n’est autorisée par cette tâche.
- Les variables legacy supplémentaires devront être absorbées ou supprimées
  progressivement par `08.2` et `08.3`.

## Rollback

La tâche est documentaire. Le rollback consiste à restaurer les deux fichiers
locaux modifiés depuis Git ou à supprimer uniquement le dossier de preuve de
`SKULL-08.1`; aucun état distant ou matériel n’a changé.
