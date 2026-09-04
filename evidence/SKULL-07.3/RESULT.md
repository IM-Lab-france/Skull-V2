# Résultat SKULL-07.3

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : séparation locale des opérations Bluetooth dans l’IHM.
- Autorisations : aucun accès distant, scan réel, appairage, connexion,
  sélection de sink ou lecture audio.
- Coexistence : les changements existants, notamment ceux de la phase 8, ont
  été conservés ; aucun fichier de configuration de phase 8 n’a été modifié.

## Réalisation

- `api/bluetooth.py` expose des routes indépendantes pour `scan`, `pair`,
  `trust`, `connect`, `select-output` et `test-audio`.
- L’IHM affiche séparément découverte, appairage, confiance, connexion,
  profil Audio Sink et sink PulseAudio.
- L’IHM n’appelle plus la route legacy combinée `/pair`.
- Les callbacks `pair`, `trust` et `connect` sont idempotents et ne déclenchent
  pas les étapes suivantes.
- Chaque opération renvoie un état rafraîchi ; les erreurs restent stables,
  actionnables et sans sortie brute de `bluetoothctl`.
- Le test audio impose `confirm: true`, une durée bornée de 100 à 3000 ms et
  un volume borné de 0 à 20.
- La sélection PulseAudio et l’émission sonore réelle restent volontairement
  retenues par les tâches dédiées suivantes.

## Commandes de validation

- `python -m pytest -q tests/contract/test_bluetooth_ui.py tests/contract/test_legacy_blueprint.py`
- `python -m pytest -q`
- `python -m compileall -q api adapters_runtime.py web_app.py tests`
- `node --check static/app.js`
- `git diff --check`

## Résultats

- Contrats ciblés : `11 passed`, un avertissement externe connu de
  `pydub`/`audioop`.
- Suite complète : `232 passed`, un avertissement externe connu de
  `pydub`/`audioop`.
- Compilation Python et syntaxe JavaScript : OK.
- `git diff --check` : OK ; les avertissements Git restants concernent les
  conversions LF/CRLF déjà présentes dans le worktree candidat.
- Les tests vérifient l’absence d’enchaînement pair → trust → connect, le
  rafraîchissement après échec, la validation MAC, la confirmation audio et
  l’absence de détails techniques dans les réponses.

## Écarts ou risques restants

- La capacité Audio Sink et le sink PulseAudio ne sont pas encore prouvés par
  l’adaptateur de production ; cela appartient à `SKULL-07.4`.
- La lecture audio physique reste exclue et appartient à la validation
  matérielle dédiée.
- La route legacy `/pair` conserve son comportement combiné pour les clients
  historiques ; elle n’est plus utilisée par cette IHM.

## Rollback

- Retirer `api/bluetooth.py`, les callbacks explicites dans `web_app.py`, les
  contrôles IHM et les tests/preuves de `SKULL-07.3`.
- Rétablir l’appel IHM vers la route legacy `/pair` uniquement après revue du
  diff ; ne pas supprimer les appairages ni modifier l’état Bluetooth réel.
- Aucun service, équipement, configuration de phase 8 ou état distant n’a été
  modifié.
