# Exécution des commandes Bluetooth

Le runner `services/bluetooth_commands.py` est la frontière commune utilisée
par `BluetoothctlAdapter` et la façade legacy pour les commandes interactives
Bluetooth actuellement présentes dans le dépôt.

- le binaire est transmis comme une liste d’arguments à `subprocess.run` ;
- `shell=False` est imposé ;
- chaque commande interactive est rejetée si elle contient un retour ligne ;
- le timeout est appliqué à chaque invocation ;
- les sorties sont décodées, débarrassées des séquences ANSI, bornées et
  rédigées avant journalisation ou exposition ;
- un verrou réentrant partagé sérialise les opérations multi-commandes ;
- les MAC sont validées au format strict avant la construction de `info`,
  `pair`, `trust` ou `connect`.

Le dépôt ne contient pas encore d’appel `pactl` ou `wpctl` dans ce périmètre ;
la sélection et la vérification du sink sont réservées à `SKULL-07.4`. Aucun
fallback audio silencieux n’est ajouté par ce runner.
