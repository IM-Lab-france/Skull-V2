# Résultat SKULL-02.4

- Date : 2 septembre 2026
- Statut : VALIDÉ
- Portée : exemples neutres pour les configurations JSON et l’environnement
  Bluetooth ; aucun accès distant ni matériel.
- Fichiers modifiés dans le worktree : `.gitignore`, `config/README.md`,
  `config/*.json.example`, `config/bluetooth_device.env.example` et
  `tests/test_configuration_examples.py`.
- Commandes de validation : `python -m unittest discover -s tests -p
  'test_*.py'`, `python -m compileall -q .`, `git diff --check` et
  `git check-ignore -v` sur des fichiers actifs et exemples.
- Résultats : 3 tests réussis ; JSON valides ; schémas ESP32 contrôlés ; les
  fichiers actifs restent ignorés ; les exemples sont explicitement suivis ;
  le contrôle des URLs de webhook et des valeurs de secret échoue si une valeur
  sensible est introduite dans le diff ou les exemples.
- Écarts ou risques restants : la configuration réellement présente sur le
  Raspberry n’a pas pu être relue, car SSH vers `192.168.1.116:22` a expiré.
  Les noms de sessions et la MAC Bluetooth réels doivent être fournis au
  déploiement, hors Git.
- Rollback : supprimer les nouveaux exemples et le test, puis restaurer les
  seules exceptions `.example` de `.gitignore` ; aucune configuration active
  ni donnée de production n’a été modifiée.

Aucun secret, `.env` actif, webhook, venv persistant, log, audio ou changement
Raspberry n’a été ajouté.
