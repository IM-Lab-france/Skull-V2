# Contrat HTTP `/api/v1`

Cette API est ajoutée pendant la transition. Elle est en lecture seule pour
`SKULL-06.8` : aucune route v1 ne démarre, ne met en pause, n’arrête, ne
reconfigure ou ne commande un équipement.

## Convention JSON

Toute réponse v1 est un objet JSON avec exactement une enveloppe de succès ou
d’erreur :

```json
{"ok": true, "data": {}}
```

```json
{
  "ok": false,
  "error": {"code": "invalid_input", "message": "Entree invalide"}
}
```

Les messages d’erreur sont génériques. Ils ne contiennent ni traceback,
commande, chemin système, secret, webhook, adresse ou adresse MAC.

## Routes

| Route | Entrée validée | Réponse `data` | Effet matériel |
|---|---|---|---|
| `GET /api/v1/status` | aucune | état de lecture public, boucle et taille de playlist | aucun |
| `GET /api/v1/sessions` | aucune | sessions et catégories | aucun |
| `GET /api/v1/sessions/<nom>` | nom direct, non vide, 128 caractères maximum, sans séparateur ni contrôle | validité de la session et compteurs JSON/MP3 | aucun |
| `GET /api/v1/playlist?limit=N` | `N` décimal entre 1 et 100, facultatif ; 100 par défaut | élément courant, file bornée et taille totale | aucun |

La route d’inspection peut retourner `404 not_found` si la session n’existe
pas. Un `limit` invalide retourne `400 invalid_input`.

## Correspondance legacy → v1

| Contrat legacy conservé | Contrat v1 correspondant | Différence volontaire |
|---|---|---|
| `GET /status` | `GET /api/v1/status` | enveloppe `ok/data` et sous-ensemble public sans diagnostic sensible |
| `GET /sessions` | `GET /api/v1/sessions` | enveloppe `ok/data` |
| `GET /api/sessions` | `GET /api/v1/sessions` | v1 ne reproduit pas le snapshot de transition de playlist |
| `GET /playlist` | `GET /api/v1/playlist` | enveloppe `ok/data`, file bornable par `limit` |
| `POST /play`, `/pause`, `/resume`, `/stop` | aucune migration v1 en `SKULL-06.8` | commandes matérielles laissées legacy |
| `POST /api/enqueue` | aucune migration v1 en `SKULL-06.8` | boutons et sonnette inchangés |
| routes ESP32, Bluetooth, relais, fumée et administration | aucune migration v1 en `SKULL-06.8` | reportées aux tâches sécurité/IoT |

Les clients existants continuent d’utiliser leurs URLs legacy. Aucun client,
firmware ou service distant n’a été modifié.
