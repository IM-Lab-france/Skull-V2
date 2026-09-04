# Résultat SKULL-07.9

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : supervision ESP32 découplée des commandes et des rafraîchissements
  HTTP, déployée sur `/opt/skull-candidate`.

## Réalisation

- `/esp32/status` lit désormais un instantané cache et ne déclenche aucune
  requête réseau.
- La vérification immédiate est séparée dans `POST /esp32/status/check` et
  reste une action explicite, bornée et protégée contre les sondes concurrentes.
- `ESP32Supervisor` possède une seule instance de polling, une seule sonde
  active, un backoff progressif borné, un circuit breaker et une annulation
  rapide à l’arrêt.
- Les commandes ESP32 et les sondes utilisent une même serrure réseau ; les
  commandes relais/boutons restent distinctes de la supervision.
- L’IHM distingue le polling automatique du contrôle manuel via la métadonnée
  `supervision.source` et expose les états `online`, `degraded`,
  `circuit_open`, `probing` et `disabled`.
- Aucun scan, appairage ou autre effet de bord Bluetooth n’est impliqué.

## Validation

- Suite complète du worktree candidat : `269 passed`.
- Compilation Python de `web_app.py` et `services/esp32_supervisor.py` : OK.
- Syntaxe JavaScript de `static/app.js` : OK.
- Le test de cache prouve que `GET /esp32/status` ne touche pas le réseau.
- Les tests couvrent backoff, circuit breaker, reprise manuelle, concurrence,
  annulation, timeout et erreurs réseau sans matériel réel.
- Déploiement contrôlé sur la candidate : healthchecks live/ready HTTP 200,
  candidate active et `servo-sync.service` inactif.
- État live actuel : supervision `disabled`, car la configuration ESP32 est
  désactivée ; aucun polling réseau n’est donc lancé sans activation explicite.

## Limite connue

La panne et la reprise du firmware réel n’ont pas été forcées sur le réseau de
production puisque l’ESP32 est actuellement désactivé. Elles sont couvertes
par les scénarios sans matériel ; un essai réel nécessitera l’activation
explicite de la configuration ESP32.

## Rollback

La candidate précédente est sauvegardée sous
`/var/backups/skull/skull-07.9-deploy-20260903-172554/`. En cas d’échec,
arrêter la candidate, restaurer les fichiers de cette sauvegarde et redémarrer
`skull-candidate.service`. La phase 8 et le service legacy n’ont pas été
modifiés.
