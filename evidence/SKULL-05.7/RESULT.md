# SKULL-05.7 — résultat de bascule runtime

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Cible : hôte `skull`.
- Production conservée : `servo-sync.service` sur le port 5000.
- Candidate déposée dans `/opt/skull-candidate`.
- `playlist-web.service` sur le port 5050 laissé inchangé.
- Aucun bouton, mouvement servo, lecture audio ou déclenchement fumée n’a été
  demandé pendant cette tentative.

## Opérations réalisées

1. Préflight distant : production et playlist actives, port 5000 occupé par
   l’ancienne application, candidate absente.
2. Archive candidate transférée avec empreinte vérifiée côté source et cible.
   Elle excluait `data/`, la configuration active, les journaux et les secrets.
3. Candidate installée sous `/opt/skull-candidate`, avec liens vers les
   répertoires de données et de configuration existants. L’unité candidate est
   statique et non activée au démarrage.
4. Test isolé simulé sur 5002 : `/health/live`, `/health/ready` et les routes
   legacy de lecture ont répondu correctement.
5. Une première tentative a été annulée par rollback à cause du flux SSE
   persistant ; le défaut a été corrigé localement.
6. Après transfert du correctif, production arrêtée proprement, puis candidate
   démarrée en mode réel sur 5000. Gunicorn a démarré avec un master et un
   worker.
7. Le rollback de la première tentative a été exécuté : candidate arrêtée,
   `servo-sync.service` redémarrée, port 5000 et route `/status` vérifiés à
   nouveau.

## Résultats

### Validé

- Déploiement isolé dans un chemin distinct, puis mise en service candidate.
- Démarrage réel de la candidate sur le port historique.
- Un seul processus Gunicorn matériel après démarrage candidate.
- Healthchecks et routes observés avec HTTP 200 : `/health/live`,
  `/health/ready`, `/status`, `/api/sessions`, `/playlist`, `/categories`,
  `/esp32/status` et `/esp32/button-config`.
- Requêtes invalides `/play` et `/api/enqueue` rejetées en HTTP 400 sans
  démarrer de lecture.
- `/logs/stream` répond en SSE borné, avec reconnexion native et sans bloquer
  les healthchecks.
- Rollback exécutable et effectivement réalisé ; l’ancienne production répond à
  nouveau sur `/status` avec HTTP 200.
- Le service playlist est resté actif.

### Bloquant

La configuration validée localement impose un worker Gunicorn synchrone unique.
Lors de la première tentative, la route persistante `/logs/stream` occupait ce
worker ; pendant cette connexion, `/health/ready` pouvait rester en attente et
les contrôles concurrents n’étaient plus fiables. Le journal candidate montre
l’abandon du worker sur cette route et son remplacement par Gunicorn.

La correction borne chaque fenêtre SSE à 0,5 seconde, émet un `retry` standard
et laisse `EventSource` gérer la reconnexion native. Le smoke Linux puis le
contrôle distant avec un flux ouvert et des healthchecks concurrents passent.

## État final distant

- `servo-sync.service` : active.
- `playlist-web.service` : active.
- `skull-candidate.service` : active.
- `servo-sync.service` : inactive, remplacée temporairement par la candidate.
- Port 5000 : candidate Gunicorn active.
- Aucun changement apporté à l’unité systemd historique.

## Validation

- `python -m pytest -q` : 90 tests passés.
- `python -m compileall -q` : OK.
- Smoke Gunicorn Linux simulé : flux SSE et `/health/live` concurrents, HTTP
  200, fermeture du flux confirmée.
- Validation distante : candidate active, ancienne unité inactive, ports 5000
  et 5050 présents, un master et un worker candidate, healthchecks et routes
  legacy vérifiés HTTP 200, flux SSE borné vérifié.
- `git diff --check` : OK.

## Suite obligatoire

La candidate est laissée active sur 5000. Le rollback reste la procédure de
retour si un problème apparaît ; aucune validation matérielle de lecture,
servo, bouton physique, sonnette ou fumée n’a été déclenchée dans cette tâche.
