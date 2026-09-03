# SKULL-06.1 — types et erreurs du domaine

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Exécution locale dans le worktree isolé de production.
- Aucun accès distant ni action matérielle.
- Aucun commit ni push effectué.

## Résultat

Le package pur `domain/` a été créé avec les types immuables de session,
d’événement timeline, d’élément de playlist et d’état de lecture. Les erreurs
métier distinctes couvrent l’absence, l’invalidité, le conflit, la dépendance
indisponible et l’opération interdite.

Les validations existantes de session, timeline et chargement utilisent ces
erreurs. Les classes conservent la compatibilité avec `ValueError`,
`FileNotFoundError`, `ConnectionError` et `PermissionError`, ce qui préserve
la traduction de la façade legacy.

## Preuves

- Tests ciblés : 4 passés.
- Suite complète : 94 tests passés, 1 avertissement externe connu.
- Compilation Python : OK.
- `git diff --check` : OK ; seuls les avertissements de fins de ligne Git
  existants sont signalés.
- Le domaine s’importe sous Windows sans Flask, réseau, subprocess ni
  bibliothèque Raspberry.

## Limites

Les dictionnaires internes de la façade legacy et l’extraction complète des
services restent volontairement en place. Aucun comportement HTTP, matériel ou
réseau n’a été modifié.
