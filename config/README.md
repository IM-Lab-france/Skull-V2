# Exemples de configuration

Les fichiers actifs de ce dossier sont ignorés par Git. Copier uniquement le
fichier `.example` correspondant, puis remplacer les valeurs neutres.

Les fichiers JSON doivent rester valides en JSON strict : les commentaires et
les valeurs secrètes ne doivent pas être ajoutés aux exemples.

## Fichiers

- `esp32_settings.json.example` : adresse de l’ESP32, port TCP et activation.
  `host` accepte une IPv4 ou un nom mDNS ; `port` est un entier de 1 à 65535.
  Laisser `enabled` à `false` tant que l’adresse n’est pas validée.
- `esp32_button_categories.json.example` : trois affectations de boutons vers
  une catégorie de sessions ; une chaîne vide désactive l’affectation.
- `session_categories.json.example` : catégories et correspondance entre nom
  de session et catégorie. Les noms doivent correspondre aux répertoires de
  `data/`.
- `channels_state.json.example` : activation logique des quatre canaux. Cela
  ne modifie ni les limites ni les offsets mécaniques.
- `pitch_offsets.json.example` : offsets en degrés pour les quatre servos,
  bornés par l’application entre -45 et +45. Ne pas modifier sans validation
  mécanique.
- `bluetooth_device.env.example` : adresse et nom informatif du périphérique
  Bluetooth. Remplacer l’adresse neutre par la MAC réellement appairée ; ne
  jamais y placer une clé ou un mot de passe.

Les paramètres d’environnement complémentaires (`PLAYLIST_*`) sont injectés
par le service de déploiement. Le webhook fumée doit rester fourni hors Git,
par un mécanisme de secrets de production ; aucune URL n’est fournie ici.
