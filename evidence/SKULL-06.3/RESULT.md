# SKULL-06.3 — parsing et interpolation des timelines

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Exécution locale dans le worktree isolé de production.
- Aucun accès distant ni action matérielle.
- Aucun commit ni push effectué.

## Résultat

Le parsing, la validation, la normalisation et l’interpolation sont isolés
dans `domain/timeline.py`. La façade `timeline.py` conserve les imports
existants. Les quatre formats caractérisés restent pris en charge avec les
mêmes traces, fréquence, arrondis, mappings de mâchoire, offsets et valeurs
hors limites.

Les erreurs de structure sont désormais déterministes et indexées. Les
événements simultanés restent autorisés. Le module ne dépend d’aucun matériel,
réseau ou framework web.

## Preuves

- Tests ciblés : 19 passés.
- Suite complète : 109 tests passés, 1 avertissement externe connu.
- Équivalence avec le commit de référence : 9 fixtures identiques.
- Compilation Python : OK.
- `git diff --check` : OK ; seuls les avertissements de fins de ligne Git
  existants sont signalés.

## Limites

Les données de production n’ont pas été chargées et aucun mouvement de servo
n’a été déclenché. Aucun comportement HTTP, réseau ou matériel n’a été
modifié volontairement.
