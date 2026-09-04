# Résultat SKULL-08.3

- Date : 4 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : règle de précédence du chargeur typé, liste des surcharges
  autorisées, provenance non sensible et garde-fou contre la dépendance au
  répertoire courant.
- Fichiers modifiés : `config/loader.py`, `config/README.md`,
  `docs/configuration-precedence.md`, `tests/config/test_schema.py` et cette
  preuve.
- Aucun Raspberry, service distant, DNS, Bluetooth, audio, servo ou webhook
  réel n’a été sollicité.

## Règle validée

La précédence est unique et déterministe :

1. arguments de maintenance autorisés ;
2. variables d’environnement explicitement listées ;
3. fichier TOML explicite ;
4. défauts sûrs du schéma.

Les arguments sont limités à `runtime.mode` et `logging.level`; aucun argument
HTTP ne peut modifier le matériel. `SKULL_RUNTIME_MODE` est prioritaire sur
`SKULL_HARDWARE_MODE`. Le chemin TOML par défaut est absolu et le chargement
ne dépend pas du répertoire courant.

## Vérifications

- `python -m pytest -q tests/config/test_schema.py` → `13 passed`.
- `python -m pytest -q` → `271 passed`, un avertissement externe connu
  `pydub/audioop`.
- `python -m compileall -q config tests web_app.py` → succès.
- `git diff --check` → aucune erreur.
- Les collisions défaut/TOML/environnement/arguments sont testées sur des
  valeurs texte, entières et niveaux de journalisation.
- Les tests vérifient qu’un réglage matériel passé en argument est refusé et
  que la provenance renvoyée reste non sensible.

## Compatibilité legacy

Les variables `PLAYLIST_*` et certaines constantes lues directement par les
modules historiques restent des consommateurs de compatibilité. Elles sont
documentées, mais leur absorption complète relève de `SKULL-08.4`; elles ne
peuvent pas ajouter une clé au chargeur typé.

## Écarts ou risques restants

- Les JSON et `.env` legacy ne sont pas encore tous convertis et comparés aux
  données réelles : `SKULL-08.4` reste nécessaire.
- Le déploiement DNS réel et la panne DNS bornée restent dans `SKULL-08.6`.
- `SKULL-08.5` reste annulée ; aucune sonnette ni automatisation Home Assistant
  n’est reconfigurée.

## Rollback

Le changement est local et réversible : restaurer les fichiers modifiés depuis
le commit précédent et supprimer uniquement `evidence/SKULL-08.3/`. Aucun état
Raspberry, réseau ou matériel n’a changé.
