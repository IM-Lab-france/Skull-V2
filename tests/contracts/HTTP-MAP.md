# Carte des contrats HTTP legacy

Cette carte décrit le périmètre observé par les tests locaux. Les tests
utilisent le client Flask et des adaptateurs factices ; aucune requête ne
quitte le poste.

| Route | Appelant legacy | Classe | Effet | Contrat figé |
|---|---|---|---|---|
| `GET /status` | IHM / diagnostic | lecture publique | état lecture, canaux, playlist et boucle | statut 200, JSON |
| `GET /api/sessions` | ESP32 boutons | lecture appareil | état playlist et catégories | statut 200, JSON |
| `POST /play` | sonnette / IHM | pilotage matériel | démarrage d’une session | valide 200, invalide 400 |
| `POST /api/enqueue` | ESP32 boutons | pilotage matériel | ajout ou démarrage d’une session | valide 200, invalide 400 |
| `POST /pause`, `/resume`, `/stop` | IHM | pilotage matériel | contrôle du lecteur et des servos | statut 200, JSON |
| `GET/POST /playlist` | IHM | administration lecture | consultation ou ajout en file | GET 200, ajout 201 |
| `DELETE /playlist/<id>` | IHM | administration lecture | suppression d’un élément en file | 404 si absent |
| `POST /playlist/<id>/move`, `/playlist/skip` | IHM | pilotage lecture | réordonnancement ou saut | 400/404 selon entrée |
| `GET/POST /categories` | IHM | administration données | lecture ou modification des catégories | GET 200, création 201 |
| `GET /esp32/status` | IHM | passerelle réseau | interrogation de l’ESP32 | JSON avec `reachable` |
| `POST /esp32/relay` | IHM / domotique | passerelle matériel distant | commande d’un relais ESP32 | JSON `success`/`reachable` |
| `GET /esp32/button-config` | IHM | passerelle réseau | lecture de la configuration boutons | JSON avec affectations |

## Limites de sécurité observées

La classification décrit l’usage, pas une protection effective. Les routes
legacy ne sont pas authentifiées dans cette version et la séparation public /
administration est une priorité des phases sécurité et IoT ultérieures.

Les snapshots ne contiennent aucune IP privée, MAC, URL de webhook ou donnée de
production.
