# Exemples de configuration

La cible phase 8 est `skull.example.toml`, lu par `config.loader`. Les anciens
JSON et `.env` restent acceptés uniquement par le convertisseur local
`config.migrate_legacy` ; ils ne sont pas chargés automatiquement par le
service.

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
par le service de déploiement historique. Pour la nouvelle configuration, seules
les variables documentées par `config.loader.ENV_FIELDS` sont autorisées. Le
webhook fumée reste fourni hors Git par une référence `env:` ou `file:` ; aucune
URL et aucun secret ne sont fournis ici.

Le sélecteur runtime accepte désormais `SKULL_RUNTIME_MODE` en priorité, avec
`SKULL_HARDWARE_MODE` conservé comme alias de coexistence. La sélection du mode
ne construit aucun adaptateur et le mode simulé reste soumis à une valeur
d’environnement explicite.
