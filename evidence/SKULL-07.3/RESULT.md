# Résultat SKULL-07.3

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : séparation locale des opérations Bluetooth dans l’IHM du worktree
  candidat `Skull-V2-production-2026`.
- Autorisations : aucun accès distant, scan réel, appairage, connexion,
  sélection de sink ou lecture audio.

## Réalisation

- L’IHM utilise des routes indépendantes `scan`, `pair`, `trust`, `connect`,
  `select-output` et `test-audio` sous `/bluetooth`.
- Les états découverte, appairage, confiance, connexion, Audio Sink et sink
  PulseAudio sont affichés séparément.
- L’appairage ne déclenche plus automatiquement confiance ou connexion dans la
  nouvelle surface IHM ; la route legacy combinée est conservée pour les
  anciens clients.
- Chaque réponse rafraîchit l’état et ne contient pas de sortie brute
  `bluetoothctl`.
- Le test audio est confirmé explicitement et borné ; la sélection PulseAudio
  et le son réel restent réservés aux tâches suivantes.

## Commandes de validation

- `python -m pytest -q tests/contract/test_bluetooth_ui.py tests/contract/test_legacy_blueprint.py`
- `python -m pytest -q`
- `python -m compileall -q api adapters_runtime.py web_app.py tests`
- `node --check static/app.js`
- `git diff --check`

## Résultats

- `11 passed` sur les contrats ciblés.
- `232 passed` sur la suite complète, avec un avertissement externe connu
  `pydub`/`audioop`.
- Compilation Python, syntaxe JavaScript et contrôle du diff : OK.
- Aucun secret, adresse de production ou sortie système réelle n’a été ajouté
  à la preuve.

## Écarts ou risques restants

- La sélection et la vérification du sink PulseAudio restent à réaliser dans
  `SKULL-07.4`.
- La validation physique audio reste exclue.
- Les fichiers de configuration de la phase 8 ont été préservés.

## Rollback

- Retirer uniquement les changements de `SKULL-07.3` dans le worktree candidat
  après revue du diff ; ne toucher ni aux changements parallèles ni aux
  appairages réels.
