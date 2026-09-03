# Résultat SKULL-07.2

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : sécurisation locale des commandes Bluetooth existantes.
- Autorisations : aucun accès distant, scan réel, appairage, connexion,
  changement de sink ou lecture audio.
- Coexistence : les changements observés de l’agent phase 8 ont été préservés ;
  aucun fichier de configuration de cette phase n’a été modifié.

## Réalisation

- `services/bluetooth_commands.py` centralise l’appel à `bluetoothctl` avec
  liste d’arguments, `shell=False`, timeout, sortie normalisée et limite de
  taille.
- Les sorties retirent les séquences ANSI et rédigent les formes courantes de
  credentials, tokens et secrets avant réutilisation.
- Un verrou réentrant partagé sérialise une opération complète de scan,
  appairage ou connexion, y compris ses sondages d’état.
- `BluetoothctlAdapter` et la façade legacy refusent les MAC qui ne suivent
  pas le format strict à six octets avant toute commande.
- Les commandes interactives contenant un retour ligne sont rejetées avant
  l’appel au processus ; aucune chaîne utilisateur libre n’est acceptée comme
  commande.
- Les appareils `pactl`/`wpctl` ne sont pas appelés dans cette tâche ; le sink
  reste traité par la tâche dédiée `SKULL-07.4`.

## Commandes de validation

- `python -m pytest -q tests/unit/test_bluetooth_commands.py tests/unit/test_runtime_adapters.py tests/unit/test_bluetooth_state.py`
- `python -m pytest -q`
- `python -m compileall -q services adapters_runtime.py web_app.py tests`
- `git diff --check`
- scan ciblé des nouveaux fichiers pour URL, IP, MAC de production et secret

## Résultats

- Tests ciblés : `20 passed`.
- Suite complète : `224 passed`, `1 warning` externe connu (`pydub`/`audioop`).
- Compilation Python : OK.
- `git diff --check` : OK ; avertissements Git limités aux conversions de fins
  de ligne déjà présentes dans le worktree candidat.
- L’injection par retour ligne, les arguments en liste, `shell=False`, le
  timeout, la rédaction et la sérialisation concurrente sont couverts.
- Aucun secret, valeur de production ou appel système Bluetooth réel n’a été
  utilisé.

## Écarts ou risques restants

- La sélection et la vérification du sink PulseAudio restent à faire dans
  `SKULL-07.4`.
- Les contrats d’IHM séparant scan/appairage/confiance/connexion appartiennent
  à `SKULL-07.3`.
- La validation physique du JBL reste exclue de cette tâche.

## Rollback

- Retirer `services/bluetooth_commands.py` et le contrat associé, puis
  restaurer dans `adapters_runtime.py` et `web_app.py` les appels d’exécution
  précédents, sans toucher aux modifications de phase 8.
- Retirer les tests ajoutés et annuler uniquement les mises à jour de preuve,
  TODO et mémoire relatives à `SKULL-07.2`.
- Aucun état Bluetooth réel n’a été changé ; aucun rollback matériel n’est
  nécessaire.
