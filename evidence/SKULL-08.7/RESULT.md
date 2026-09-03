# SKULL-08.7 — déploiement de la configuration

- Date : 3 septembre 2026, Europe/Paris
- Statut : `PARTIEL`
- Portée : préparation locale du validateur, de la candidate parallèle et du
  rollback ; aucun déploiement réel.

## Validé localement

- `python -m config.validate config/skull.example.toml` valide le candidat
  sans initialiser le matériel et masque la référence de secret.
- Les chemins code/config/secrets/données/logs sont distincts dans le schéma.
- Le runbook [configuration-deployment-runbook.md](../../docs/configuration-deployment-runbook.md)
  définit sauvegarde, permissions minimales, candidate parallèle, bascule,
  surveillance et restauration.

## Blocage volontaire

Les écritures sous `/etc/skull`, les changements de permissions, le démarrage
systemd, la validation live et le rollback réel nécessitent une confirmation
explicite et un accès Raspberry. Aucun de ces changements n’a été effectué.
