# SKULL-05.6 — matrice candidate / contrat legacy

La candidate est comparée aux snapshots de contrat gelés dans
`tests/contract/http_legacy_snapshots.json`. La comparaison porte sur la
méthode, le statut HTTP, le `Content-Type`, les clés obligatoires et leurs
types. Les valeurs variables explicitement ignorées sont les identifiants
client, les horodatages, les cooldowns, les listes dépendantes du contenu et
les détails de sélection aléatoire.

| Cas legacy | Méthode | Statut | Content-Type | Schéma contrôlé |
|---|---:|---:|---|---|
| `/status` | GET | 200 | application/json | running bool, channels object, playlist_size int, loop object |
| `/api/sessions` | GET | 200 | application/json | playlist object, categories list |
| `/api/enqueue` invalide | POST | 400 | application/json | success bool, error str |
| `/api/enqueue` valide | POST | 200 | application/json | success bool, requested str, session str |
| `/play` invalide | POST | 400 | application/json | error str |
| `/play` valide | POST | 200 | application/json | session str, random_mode object |
| `/pause` | POST | 200 | application/json | status str |
| `/resume` | POST | 200 | application/json | status str |
| `/stop` | POST | 200 | application/json | status str |
| `/playlist` lecture | GET | 200 | application/json | current nullable object, queue list |
| `/playlist` ajout invalide | POST | 400 | application/json | error str |
| `/playlist` ajout valide | POST | 201 | application/json | status str, item object, position int |
| `/playlist/999` suppression | DELETE | 404 | application/json | error str |
| `/playlist/999/move` invalide | POST | 400 | application/json | error str |
| `/playlist/skip` | POST | 200 | application/json | status str |
| `/categories` lecture | GET | 200 | application/json | categories list |
| `/categories` création | POST | 201 | application/json | category str, categories list |
| `/esp32/status` | GET | 200 | application/json | reachable bool |
| `/esp32/relay` | POST | 200 | application/json | success bool, reachable bool, response object |
| `/esp32/button-config` | GET | 200 | application/json | reachable bool, buttonCount int, assignments list, categories list |

Les 21 cas sont exécutés avec client Flask et adaptateurs factices. Aucun
appel ne sort du poste et aucune action servo, audio, Bluetooth ou relais n’est
déclenchée.
