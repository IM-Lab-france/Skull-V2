# Résultat SKULL-07.1

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : modèle Bluetooth local et parsing d’observations synthétiques.
- Autorisations : aucune action distante ou matérielle ; aucun scan, appairage,
  connexion, sélection de sink ou lecture audio.

## Réalisation

- `domain/bluetooth.py` contient le modèle `BluetoothDeviceState` avec les
  champs `address`, `name`, `discovered`, `paired`, `trusted`, `connected`,
  `audio_sink_capable`, `pulse_sink`, `last_error` et `updated_at`.
- Les MAC sont validées avec le format strict à six octets hexadécimaux avant
  toute commande de l’adaptateur runtime.
- Les propriétés `Name`, `Paired`, `Trusted` et `Connected` sont parsées
  séparément des UUID BlueZ.
- `audio_sink_capable` est vrai uniquement si l’UUID A2DP Audio Sink est
  présent ; `connected` seul ne rend jamais un périphérique audio disponible.
- `pulse_sink` reste `None` jusqu’à une vérification PulseAudio ultérieure.
- Les fixtures synthétiques couvrent JBL Quantum 360, SoundLink Mini et un
  périphérique BLE sans profil audio.

## Commandes de validation

- `python -m pytest -q tests/unit/test_bluetooth_state.py tests/unit/test_runtime_adapters.py`
- `python -m pytest -q`
- `python -m compileall -q domain adapters_runtime.py tests`
- `git diff --check`
- scan ciblé des nouveaux fichiers pour URL, IP, MAC de production et secret

## Résultats

- Tests ciblés : `17 passed`.
- Suite complète : `221 passed`, `1 warning` externe connu (`pydub`/`audioop`).
- Compilation Python : OK.
- `git diff --check` : OK ; avertissements Git limités aux conversions de fins
  de ligne déjà présentes dans le worktree candidat.
- Le test BLE non audio vérifie que `audio_sink_capable` vaut `False` malgré
  `connected=True`.
- Aucun secret, adresse de production ou sortie système réelle n’est présent
  dans les nouveaux fichiers.

## Écarts ou risques restants

- Le sink PulseAudio n’est pas encore sélectionné ni vérifié ; cela appartient
  à `SKULL-07.4`.
- Les commandes Bluetooth restent à centraliser et sécuriser dans `SKULL-07.2`.
- La validation physique du JBL reste exclue de cette tâche.

## Rollback

- Retirer `domain/bluetooth.py`, la fixture et le test ajoutés, puis retirer les
  imports et l’utilisation du modèle dans `adapters_runtime.py`.
- Aucun changement de configuration Bluetooth, d’appairage, de sink ou de
  service n’a été réalisé ; aucun rollback matériel n’est nécessaire.
