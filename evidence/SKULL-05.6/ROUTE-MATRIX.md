# Matrice SKULL-05.6

La candidate est comparée aux snapshots legacy de
`tests/contract/http_legacy_snapshots.json` sur méthode, statut HTTP,
`Content-Type`, clés obligatoires et types. Sont ignorés uniquement les
identifiants client, horodatages, cooldowns, listes dépendantes du contenu et
détails de sélection aléatoire.

Les 21 cas validés sont :

```text
GET  /status                         200
GET  /api/sessions                   200
POST /api/enqueue (invalide)         400
POST /api/enqueue (valide)           200
POST /play (invalide)                400
POST /play (valide)                  200
POST /pause                          200
POST /resume                         200
POST /stop                           200
GET  /playlist                       200
POST /playlist (invalide)            400
POST /playlist (valide)              201
DELETE /playlist/999                 404
POST /playlist/999/move (invalide)  400
POST /playlist/skip                  200
GET  /categories                     200
POST /categories                     201
GET  /esp32/status                   200
POST /esp32/relay                    200
GET  /esp32/button-config            200
```

Tous les cas utilisent client Flask et adaptateurs factices ; aucune action
servo, audio, Bluetooth, relais ou requête distante n’est exécutée.
