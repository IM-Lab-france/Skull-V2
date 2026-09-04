# SKULL-08.5 — rotation du secret fumée

- Date : 4 septembre 2026, Europe/Paris
- Statut : `ANNULÉE`
- Portée : la rotation du secret fumée est retirée du périmètre ; aucune
  reconfiguration de la sonnette ni rotation réelle exécutée.

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
- Le plan logiciel a été préparé sans valeur sensible ; aucune activation
  distante n’est prévue dans cette fiche annulée.
- Les anciens JSON et `.env` sont lus en copie locale ; une valeur webhook est
  seulement convertie en référence et signalée `redacted`.

## Décision d’annulation

La décision du 4 septembre 2026 annule `SKULL-08.5`. L’automatisation Home
Assistant `Sonnette` reste inchangée ; aucun secret, webhook ou service n’est
modifié par cette tâche.

La confirmation de l’utilisateur a été reçue le 3 septembre 2026. Home
Assistant est maintenant accessible via `ha.home.arpa` et une session
administrateur est disponible.

Le Skull est désormais joignable en SSH sur `192.168.40.20`. Depuis cette
adresse, la candidate reste active et `servo-sync.service` reste inactif ; le
service Home Assistant n’est pas exposé directement sur `8123` mais passe par
le proxy web.

L’interface Home Assistant expose une automatisation `Sonnette` avec un
déclencheur webhook local-only et une action `Lampe Bureau`. Cette
automatisation est explicitement hors périmètre et ne doit pas être
reconfigurée. La gestion configurable événement → action, dont bouton →
webhook fumée, est reportée à la phase 13.

Le relevé distant en lecture seule du 3 septembre 2026 confirmait que
`/etc/skull/secrets.env` existe mais est vide (`0600`) et que le fichier legacy
inspecté ne contient que les paramètres Bluetooth. La référence fonctionnelle
du consommateur fumée n’a pas été poursuivie, puisque cette rotation est
annulée.

Les éléments non exécutés sont volontairement reportés à la phase 13 ou à une
future décision distincte :

1. définir le consommateur et l’action fumée dans le modèle événement → action ;
2. décider séparément si un secret dédié doit être créé ;
3. appliquer alors une procédure de rotation approuvée, sans toucher à
   `Sonnette`.

## Vérifications

- Tests phase 8 ciblés : `23 passed` après ajout du plan et de ses tests.
- Tests ciblés relancés : `13 passed` (`test_smoke_rotation.py`,
  `test_secrets.py`, `test_migration.py`).
- Aucun secret réel, URL webhook complète, appel de déclenchement ou écriture
  distante.
