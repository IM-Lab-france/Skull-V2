# SKULL-06.5 — machine à états de lecture

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Résultat

`domain/state_machine.py` fournit la table complète des transitions et des
effets déclarés pour le cycle de lecture. Les événements sont sérialisés par
un verrou unique, les transitions interdites sont rejetées sans mutation et
`stop` est idempotent.

`SyncPlayer` conserve ses champs de statut legacy. Son worker utilise un
événement d’arrêt interruptible, est joint sans timeout lors de `stop` ou
`cleanup`, et arrête l’audio avant la neutralisation en cas d’erreur. Les
tests démontrent l’absence de worker orphelin après stop ou erreur.

## Vérifications

- Tests ciblés : 74 passés.
- Suite complète : 190 tests passés, 1 avertissement externe connu.
- Compilation Python : OK.
- `git diff --check` : OK ; seuls les avertissements de fins de ligne Git
  existants sont signalés.
- Aucun secret, webhook, adresse réseau, MAC ou contenu de production n’est
  présent dans cette preuve.

## Limites

- Aucun Raspberry, service distant ou matériel n’a été sollicité.
- Les adaptateurs audio, timeline et fumée restent legacy ; leur extraction
  est réservée à `SKULL-06.6`.
