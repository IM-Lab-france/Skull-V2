# SKULL-08.7 — déploiement de la configuration

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : déploiement contrôlé de la configuration TOML sur la candidate
  existante, avec vérification de santé, permissions et retour arrière.

## Validé localement

- `python -m config.validate config/skull.example.toml` valide le candidat
  sans initialiser le matériel et masque la référence de secret.
- Les chemins code/config/secrets/données/logs sont distincts dans le schéma.
- Le runbook [configuration-deployment-runbook.md](../../docs/configuration-deployment-runbook.md)
  définit sauvegarde, permissions minimales, candidate parallèle, bascule,
  surveillance et restauration.

## Déploiement contrôlé effectué

- Confirmation explicite reçue avant l’opération sur `192.168.1.116`.
- Archive filtrée vérifiée avant transfert : 90 entrées, aucune preuve, test,
  donnée, configuration active, log ou secret ; SHA-256
  `A79861B4382B2478FE40716C74FBCA945DB865E14DDC7D8FDACBC8B5B3A2F538`.
- Migration des JSON legacy vers TOML exécutée sans modifier les sources ; le
  validateur distant Python 3.11 a répondu avec succès après correction de la
  valeur par défaut mutable du schéma.
- `/etc/skull/config.toml` installé en `root:skull 0640` et
  `/etc/skull/secrets.env` en `skull:skull 0600`, sans valeur secrète ajoutée.
- Code phase 8 installé dans la candidate existante sur le port `5000` ; les
  données et fichiers de configuration legacy ont été conservés.
- `skull-candidate.service` est `active`, les healthchecks `live` et `ready`
  répondent HTTP 200, et `servo-sync.service` reste `inactive`.
- L’état TOML effectif est `runtime.mode=production` avec `esp32.enabled=false`.
- Sauvegarde de rollback :
  `/var/backups/skull/skull-08.7-deploy-5000-20260903-162934/`.

## Critères de clôture

- L’ancien runtime a été observé avant migration, puis la candidate a démarré
  avec la configuration TOML sans initialisation matérielle lors de la
  validation.
- Les tentatives de déploiement échouées ont restauré automatiquement la
  candidate précédente ; la sauvegarde finale de rollback est présente et les
  données legacy ont été conservées.
- Après le déploiement final, le service est resté actif, `live` et `ready` ont
  répondu HTTP 200, et `servo-sync.service` est resté inactif.

## Hors périmètre de SKULL-08.7

- Le lien final `/opt/skull/current` et l’unité indépendante de la version
  appartiennent à `SKULL-10` ; ils ne sont pas des critères de cette fiche.
- L’unité candidate porte encore le nom legacy `skull-candidate.service` et
  conserve son chemin de travail historique ; l’adoption complète de TOML
  comme source runtime unique sera validée avec les releases de la phase 10.
- La rotation réelle du secret fumée et la résolution DNS réelle restent
  respectivement couvertes par les tâches `SKULL-08.5` et `SKULL-08.6`.
