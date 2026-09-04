# Résultat SKULL-07.4

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : sélection et vérification locale d’une sortie PulseAudio Bluetooth.
- Autorisations : aucun accès distant, commande `pactl` réelle, changement de
  sink réel ou lecture audio.
- Coexistence : les changements existants, notamment ceux de la phase 8, ont
  été conservés ; aucun fichier de configuration de phase 8 n’a été modifié.

## Réalisation

- `PulseAudioOutputAdapter` utilise le runner commun avec liste d’arguments,
  `shell=False`, timeout et sérialisation.
- La carte Bluetooth est retrouvée par son identifiant exact, puis le profil
  `a2dp-sink` est activé et vérifié comme profil actif.
- Le sink est attendu avec un délai et un nombre de tentatives bornés.
- Un unique sink correspondant à l’adresse Bluetooth est accepté ; son nom
  stable est utilisé, jamais son index PulseAudio.
- Le sink sélectionné est vérifié comme non suspendu et comme sink par défaut.
- Aucun réglage de volume ou de mute n’est exécuté.
- Le fallback local est désactivé par défaut, configurable par environnement,
  validé par identifiant exact et marqué `fallback_used` lorsqu’il est utilisé.
- L’état IHM distingue désormais `connected`, profil Audio Sink et sink
  PulseAudio ; un fallback ne peut pas être silencieux.

## Commandes de validation

- `python -m pytest -q tests/unit/test_pulseaudio_output.py tests/unit/test_bluetooth_commands.py tests/unit/test_bluetooth_state.py tests/unit/test_runtime_adapters.py tests/contract/test_bluetooth_ui.py`
- `python -m pytest -q`
- `python -m compileall -q api adapters_runtime.py services web_app.py tests`
- `node --check static/app.js`
- `git diff --check`

## Résultats

- Tests ciblés : `35 passed`.
- Suite complète : `239 passed`, un avertissement externe connu de
  `pydub`/`audioop`.
- Compilation Python, syntaxe JavaScript et contrôle du diff : OK.
- Les tests couvrent profil A2DP absent, sink retardé, sink suspendu, sink par
  défaut incorrect, fallback désactivé/explicite, injection par retour ligne,
  absence de volume/mute et absence d’accès matériel.

## Écarts ou risques restants

- Les commandes `pactl` n’ont pas été exécutées sur le Raspberry ; la
  correspondance exacte des noms BlueZ/PulseAudio doit être confirmée pendant
  la validation matérielle.
- Les essais d’extinction/rallumage, de reconnexion et de lecture à faible
  volume restent réservés aux tâches suivantes.
- Le fallback local doit être fourni par la configuration de production, sans
  être activé implicitement.

## Rollback

- Retirer `PulseAudioOutputAdapter`, la configuration d’environnement de sortie
  et les branchements IHM/tests relatifs à `SKULL-07.4` après revue du diff.
- Restaurer uniquement la sélection précédente de sortie ; ne pas supprimer
  d’appairage et ne pas modifier les fichiers de configuration de phase 8.
- Aucun état distant, sink réel ou volume n’a été modifié.
