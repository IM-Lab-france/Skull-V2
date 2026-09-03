# SKULL-08.5 — rotation du secret fumée

- Date : 3 septembre 2026, Europe/Paris
- Statut : `BLOQUÉ`
- Portée : inventaire des producteurs/consommateurs et préparation locale
  d’une rotation sans valeur sensible ; aucune rotation réelle exécutée.

## Inventaire

- Producteur legacy observé : `web_app.py`, déclenchement nommé `Accueil`,
  appel sortant borné par `curl`.
- Frontière cible locale : `SmokeAdapter` dans `adapters.py` et
  `services/playback.py`.
- Fournisseur de secret cible : référence `env:` ou `file:` résolue par
  `config.secrets`, sans affichage ni journalisation de la valeur.
- Tests externes : scénarios simulés uniquement ; aucun consommateur domotique
  réel n’a été contacté.

## Préparation validée

- `SmokeRotationPlan` impose deux références distinctes, masque les références
  dans son diagnostic et fixe l’ordre consommateur → producteur → vérification
  → retrait de l’ancien secret.
- Le runbook [smoke-secret-rotation-runbook.md](../../docs/smoke-secret-rotation-runbook.md)
  fixe la garde d’approbation, la fenêtre de test et le rollback sans exposer
  de valeur sensible.
- Le plan reste bloqué tant que la double acceptation n’est pas confirmée par
  le système distant.
- Les anciens JSON et `.env` sont lus en copie locale ; une valeur webhook est
  seulement convertie en référence et signalée `redacted`.

## Blocage volontaire

La génération, la rotation, le test ancien/nouveau, le basculement du
producteur et le retrait de l’ancien secret nécessitent une confirmation
explicite, un mécanisme approuvé de gestion des secrets et l’accès au
consommateur domotique. Aucun de ces changements réels n’a été effectué.

Le relevé distant en lecture seule du 3 septembre 2026 confirme que
`/etc/skull/secrets.env` existe mais est vide (`0600`) et que le fichier legacy
inspecté ne contient que les paramètres Bluetooth. La référence fonctionnelle
du consommateur domotique, sa capacité de double acceptation, le nouveau
secret généré hors chat et la fenêtre de test ne sont donc pas établis.

Pour débloquer cette fiche, il faut confirmer séparément :

1. que le consommateur domotique accepte temporairement l’ancien et le nouveau
   secret ;
2. que le nouveau secret a été généré et stocké hors chat, dépôt Git et
   historique shell ;
3. la fenêtre de test et le rollback vers l’ancienne référence.

## Vérifications

- Tests phase 8 ciblés : `23 passed` après ajout du plan et de ses tests.
- Tests ciblés relancés : `13 passed` (`test_smoke_rotation.py`,
  `test_secrets.py`, `test_migration.py`).
- Aucun secret réel, URL webhook complète, appel de déclenchement ou écriture
  distante.
