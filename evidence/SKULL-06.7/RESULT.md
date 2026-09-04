# SKULL-06.7 — façade HTTP legacy

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Travail effectué uniquement dans le worktree local de production.
- Aucun accès au Raspberry, aucun redémarrage et aucune action matérielle.
- Les changements existants des tâches précédentes ont été conservés.
- Aucun commit ni push effectué.

## Réalisation

- Ajout de `api/legacy.py` et d’une fabrique de blueprint par application.
- Toutes les routes historiques de `web_app.py` sont enregistrées par le
  blueprint `legacy`, sans modifier leurs URLs, méthodes ou payloads.
- Les appels de démarrage, pause, reprise, arrêt, remplacement et skip passent
  par `LegacyPlaybackService` avec dépendances runtime explicites.
- Les comportements spécifiques de playlist, boutons, sonnette et fumée sont
  conservés dans la façade existante.
- Aucun avertissement de dépréciation n’est ajouté aux clients legacy.

## Vérifications

- Tests ciblés blueprint, façade et contrats legacy : 28 passés.
- `python -m pytest -q` : 208 tests passés, 1 avertissement externe connu.
- `python -m compileall -q .` : OK.
- `git diff --check` : OK ; avertissements de fins de ligne Git existants.
- Test de rechargement : aucun doublon de route.
- Matrice de règles HTTP et snapshots legacy : inchangés.
- Scan ciblé des secrets et URL sensibles : aucune valeur détectée.

## Limites et suite

- La façade reste techniquement dans `web_app.py`, mais sa frontière
  d’enregistrement est désormais le blueprint dédié ; une extraction physique
  des handlers n’est pas nécessaire pour préserver les clients.
- Aucune validation physique ou client ESP32/sonnette n’est incluse.
- Prochaine tâche autorisée : `SKULL-06.8`.
