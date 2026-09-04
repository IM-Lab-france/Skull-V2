# Résultat SKULL-07.4

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : sélection et vérification locale d’une sortie PulseAudio Bluetooth
  dans le worktree candidat `Skull-V2-production-2026`.
- Autorisations : aucun accès distant, commande `pactl` réelle, changement de
  sink réel ou lecture audio.

## Réalisation

- La carte Bluetooth et le profil A2DP sont traités séparément de la liaison
  Bluetooth.
- Le sink est attendu de manière bornée, sélectionné par nom stable exact,
  puis vérifié comme sink par défaut et non suspendu.
- Aucun réglage de volume ou de mute n’est exécuté.
- Le fallback local est désactivé par défaut et son activation est explicite.

## Commandes de validation

- `python -m pytest -q tests/unit/test_pulseaudio_output.py tests/unit/test_bluetooth_commands.py tests/unit/test_bluetooth_state.py tests/unit/test_runtime_adapters.py tests/contract/test_bluetooth_ui.py`
- `python -m pytest -q`
- `python -m compileall -q api adapters_runtime.py services web_app.py tests`
- `node --check static/app.js`
- `git diff --check`

## Résultats

- `33 passed` sur les tests ciblés.
- `237 passed` sur la suite complète, avec un avertissement externe connu
  `pydub`/`audioop`.
- Aucun secret, accès distant, sink réel ou émission sonore n’a été utilisé.

## Écarts ou risques restants

- La correspondance réelle des noms PulseAudio et les cycles de reconnexion
  restent à valider sur le Raspberry dans les tâches dédiées.

## Rollback

- Retirer uniquement les changements de `SKULL-07.4` du worktree candidat après
  revue du diff ; préserver les travaux parallèles et les appairages réels.
