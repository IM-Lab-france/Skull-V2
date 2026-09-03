# SKULL-08.4 — configuration et migration legacy

- Date : 3 septembre 2026, Europe/Paris
- Statut local : `PARTIEL`
- Portée : inventaire, schéma TOML, précédence, migration locale et références
  de secrets ; aucun Raspberry, service distant, DNS ou réseau sollicité.

## Validé localement

- Les sections `runtime`, `http`, `hardware`, `audio`, `bluetooth`, `esp32`,
  `smoke`, `storage`, `logging` et `security` sont typées et immuables après
  chargement.
- Les clés inconnues, types invalides, plages invalides et contraintes servo
  incohérentes sont refusés avant toute initialisation matérielle.
- La précédence est unique : arguments de maintenance autorisés, variables
  d’environnement documentées, TOML, puis défauts sûrs.
- Le convertisseur lit les JSON et `.env` legacy sans les modifier, refuse une
  cible existante, produit un TOML déterministe et signale les clés inconnues.
- Les valeurs de webhook sont converties en référence et ne sont jamais
  écrites dans le candidat, le rapport ou les diagnostics.
- Une ancienne IP ESP32 devient uniquement un fallback explicite et désactivé,
  avec un blocage demandant un nom DNS.

## Vérifications

- `python -m pytest -q tests/config` : `18 passed`.
- `python -m compileall -q config tests/config` : OK.
- `python -m config.validate config/skull.example.toml` : OK, sortie redigée.
- Scan ciblé des nouveaux fichiers : aucune URL ou affectation directe de
  secret.

## Restant / blocages contrôlés

- `SKULL-08.5` : la rotation du secret fumée et le test ancien/nouveau restent
  bloqués jusqu’à confirmation explicite et accès au consommateur domotique.
- `SKULL-08.6` : aucun enregistrement DNS n’est créé dans cette phase ; la
  résolution réelle et les ACL restent à valider pendant la phase réseau.
- `SKULL-08.7` : aucune écriture sous `/etc/skull`, permission réelle,
  redémarrage ou rollback de service n’est exécuté.

## Rollback local

Les changements sont isolés dans `codex/phase8-skull-2026`. La branche phase 7
reste indépendante ; l’intégration devra appliquer les commits phase 7 puis
phase 8, avant la suite complète des tests.
