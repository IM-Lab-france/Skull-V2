# Contrat de reconnexion Bluetooth

La reconnexion de démarrage et de lecture utilise uniquement
`PLAYLIST_BT_DEVICE_ADDR`. Elle lit `bluetoothctl info` pour cet appareil ; elle
ne lance pas de scan global et ne lance jamais `pair`.

Une adresse non trusted reste en état dégradé sans tentative de connexion. Une
adresse trusted absente est tentée au plus
`PLAYLIST_BT_RECONNECT_MAX_ATTEMPTS` fois, avec délai progressif borné par
`PLAYLIST_BT_RECONNECT_INITIAL_DELAY` et
`PLAYLIST_BT_RECONNECT_MAX_DELAY`. Chaque tentative utilise le timeout
`PLAYLIST_BT_RECONNECT_CONNECT_TIMEOUT`.

L’attente entre tentatives est interruptible par l’événement d’arrêt du runtime.
Une connexion n’est pas considérée comme audio prête tant que le profil A2DP et
le sink PulseAudio n’ont pas été vérifiés par `SKULL-07.4`.
