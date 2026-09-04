# SKULL-06.3 — parsing et interpolation des timelines

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Travail effectué uniquement dans le worktree local de production.
- Aucun accès au Raspberry, aucun redémarrage et aucune action matérielle.
- Les changements existants des tâches précédentes ont été conservés.

## Réalisation

- Extraction dans `domain/timeline.py` du parsing, de la validation, de la
  normalisation et de l’interpolation.
- `timeline.py` conservé comme façade d’import legacy pour `SyncPlayer` et les
  appelants existants.
- Conservation des quatre racines JSON caractérisées : `timeline`,
  `keyframes`, `frames` et canaux top-level.
- Validation des timestamps non décroissants, avec égalité autorisée pour les
  événements simultanés, des canaux connus et des valeurs numériques finies.
- Erreurs métier indexées par événement, sans recopie du contenu complet.
- Conservation de 60 Hz, des arrondis millisecondes, mappings de mâchoire,
  offsets neutres et absence de clamp des valeurs hors limites observée.
- Ajout d’une vue typée `Timeline.events`, sans changer `Timeline.frames`.

## Vérifications

- `python -m pytest -q tests/unit/test_domain_timeline.py tests/unit/test_timeline_characterization.py` : 19 tests passés.
- `python -m pytest -q` : 109 tests passés, 1 avertissement externe connu.
- Comparaison automatique avec l’implémentation du commit de référence sur
  9 fixtures : `REFERENCE_TRACE_EQUIVALENCE_OK=9`.
- `python -m compileall -q domain web_app.py timeline.py sync_player.py tests` : OK.
- `git diff --check` : OK ; avertissements de fins de ligne Git existants,
  aucune normalisation appliquée.
- Aucun secret, webhook, adresse réseau, MAC ou contenu de production n’est
  présent dans cette preuve.

## Limites et suite

- Les dictionnaires de frames restent exposés par compatibilité ; leur retrait
  est réservé à une étape ultérieure avec adaptation contrôlée du lecteur.
- Aucune validation physique n’est incluse.
- Prochaine tâche autorisée : `SKULL-06.4`.
