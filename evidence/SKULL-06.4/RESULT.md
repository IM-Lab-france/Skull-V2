# SKULL-06.4 — playlist et état de lecture

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Travail effectué uniquement dans le worktree local de production.
- Aucun accès au Raspberry, aucun redémarrage et aucune action matérielle.
- Les changements existants des tâches précédentes ont été conservés.

## Réalisation

- Extraction de la file thread-safe dans `domain/playlist.py` via
  `PlaylistStore`, avec façade `PlaylistManager` conservée dans `web_app.py`.
- Ajout de `PlaybackStateStore` pour l’état courant, avec copies défensives.
- Ajout de `RandomSessionSelector` avec fonctions `choice` et `shuffle`
  injectables pour des tests déterministes.
- Invariants explicites : identifiants uniques, position bornée, opérations
  atomiques sous verrou et doublons de session conservés comme comportement
  legacy.
- Persistance JSON optionnelle, écrite par fichier temporaire, `fsync`, puis
  remplacement atomique. Une erreur d’écriture laisse la file et le fichier
  précédent inchangés ; un fichier corrompu n’est jamais réparé.
- Le runtime web conserve la persistance désactivée par défaut et les formes
  dictionnaire attendues par les routes legacy.

## Vérifications

- `python -m pytest -q tests/unit/test_domain_playlist.py tests/unit/test_playlist_characterization.py tests/contract/test_http_legacy_contracts.py` : 21 tests passés.
- `python -m pytest -q` : 116 tests passés, 1 avertissement externe connu.
- `python -m compileall -q domain web_app.py tests` : OK.
- `git diff --check` : OK ; avertissements de fins de ligne Git existants,
  aucune normalisation appliquée.
- Tests de corruption et d’échec de remplacement : fichier valide conservé.
- Aucun secret, webhook, adresse réseau, MAC ou contenu de production n’est
  présent dans cette preuve.

## Limites et suite

- L’état de lecture physique reste fourni par le lecteur legacy ; la machine à
  états explicite relève de `SKULL-06.5`.
- La persistance optionnelle n’est pas activée dans le service candidat.
- Aucune validation physique n’est incluse.
- Prochaine tâche autorisée : `SKULL-06.5`.
