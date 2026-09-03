# Résultat SKULL-07.5

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : reconnexion Bluetooth contrôlée et locale.
- Autorisations : aucun accès distant, scan réel, appairage, connexion réelle
  ou lecture audio.
- Coexistence : les changements existants, notamment ceux de la phase 8, ont
  été conservés ; aucun fichier de configuration de phase 8 n’a été modifié.

## Réalisation

- `BluetoothReconnectController` lit uniquement l’état de l’adresse configurée
  et refuse toute reconnexion d’un appareil non trusted.
- Aucun scan global ni appairage automatique n’est déclenché.
- Les tentatives sont plafonnées, le délai est progressif et borné, et
  l’attente est interrompue par l’événement d’arrêt.
- Une adresse déjà connectée est traitée idempotemment.
- Le statut publie un état dégradé lorsque l’appareil est absent ; l’application
  reste donc disponible sans enceinte.
- Après une connexion, le démarrage d’une lecture exige encore la preuve
  séparée du profil A2DP et du sink PulseAudio.
- Le statut distingue `connected`, `trusted`, `audio_sink_capable`,
  `pulse_sink` et `audio_ready`.
- Le journal ne produit qu’une ligne par tentative, sans sortie brute de
  `bluetoothctl`.

## Commandes de validation

- `python -m pytest -q tests/unit/test_bluetooth_reconnect.py tests/unit/test_pulseaudio_output.py tests/contract/test_bluetooth_ui.py tests/unit/test_startup_determinism.py tests/unit/test_playlist_characterization.py`
- `python -m pytest -q`
- `python -m compileall -q api adapters_runtime.py services web_app.py tests`
- `node --check static/app.js`
- `git diff --check`

## Résultats

- Tests ciblés : `34 passed`, un avertissement externe connu de
  `pydub`/`audioop`.
- Suite complète : `245 passed`, un avertissement externe connu de
  `pydub`/`audioop`.
- Compilation Python, syntaxe JavaScript et contrôle du diff : OK.
- Les tests couvrent appareil non trusted, appareil déjà connecté, succès
  après retry, backoff, limite de tentatives, annulation, absence de scan et
  absence d’appairage automatique.

## Écarts ou risques restants

- La reconnexion et le sink doivent encore être confirmés sur le Raspberry,
  enceinte éteinte puis rallumée ; cette validation est matérielle.
- Aucun changement de service systemd ou de configuration de production n’a
  été effectué.

## Rollback

- Retirer le contrôleur, ses paramètres d’environnement, l’appel dans le
  runtime et les tests/preuves de `SKULL-07.5` après revue du diff.
- Conserver les appairages et la configuration audio réels ; aucun nettoyage
  Bluetooth ne fait partie du rollback.
