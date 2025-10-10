# Skull-v2-ESP32

Skull-v2-ESP32 pilote une tete animatronique via un ESP32-S2 (LOLIN S2 mini). Le microcontroleur gere deux relais, cinq boutons physiques et des appels HTTP vers un serveur de diffusion audio. Il met a disposition une interface web locale et une API REST pour superviser et piloter l'installation.

## Fonctionnalites

- Pilotage du relais principal et d'un relais auxiliaire dedie aux boutons.
- Mise a jour automatique de l'etat des relais en fonction de la lecture audio exposee par une API externe.
- Association persistante (NVS/Preferences) de cinq boutons physiques a des sessions audio.
- Interface web integree pour le suivi temps reel et la configuration.
- API REST locale a destination d'une supervision domotique ou d'une integration tierce.
- Service mDNS (`http://SkullHard.local`) pour un acces simplifie sur le reseau local.

## Prerequis materiel

- ESP32-S2 LOLIN S2 mini (ou carte compatible avec la meme pinout).
- Relais principal cable sur GPIO10 (commande active LOW).
- Relais auxiliaire/bouton cable sur GPIO8 (commande active selon le cablage: LOW pour OFF dans la configuration fournie).
- Cinq boutons poussoirs cables en `INPUT_PULLUP` sur les GPIO 1, 2, 4, 5 et 7.
- LED de statut optionnelle sur GPIO15 (active LOW).

## Configuration

1. Ouvrir `config.h` et adapter:
   - `WIFI_SSID` et `WIFI_PASS`.
   - `local_IP`, `gateway`, `subnet`, `dns1` si vous souhaitez une IP statique differente.
   - `MDNS_NAME` pour personnaliser le nom mDNS.
2. Dans `Skull-v2-ESP32.ino`, ajuster si besoin:
   - `HTTP_ENQUEUE_URL` (URL du serveur externe pour creer une file de lecture).
   - `HTTP_SESSIONS_URL` (API externe fournissant l'etat de la lecture audio).
   - `API_CHECK_INTERVAL` pour modifier la cadence d'interrogation (1 seconde par defaut).

Les associations boutons/sessions sont sauvegardees dans la NVS de l'ESP32. Un redemarrage conserve donc la configuration.

## Compilation et flash

1. Installer l'IDE Arduino (>= 2.0) et le support des cartes ESP32 (via le gestionnaire de cartes).
2. Selectionner la carte `LOLIN S2 mini` (ou une carte ESP32-S2 equivalente) ainsi que le bon port serie.
3. Ouvrir `Skull-v2-ESP32.ino`, compiler puis televerser.
4. Surveiller le port serie (115200 bauds) pour verifier la connexion Wi-Fi et les journaux API.

## Utilisation

- Acceder a l'interface web via `http://<ip-esp>/` ou `http://SkullHard.local/`.
- Configurer chaque bouton dans l'interface (ou via l'API) avec l'identifiant de session attendu par votre serveur audio.
- Lorsqu'un bouton est presse, l'ESP32 envoie une requete POST a `HTTP_ENQUEUE_URL` pour declencher la lecture correspondante.
- En mode automatique (`autoRelayEnabled = true`), l'ESP32 interroge `HTTP_SESSIONS_URL` toutes les secondes pour synchroniser les relais avec l'etat de lecture (`playlist.current`).

## API HTTP locale

Tous les points d'entree incluent des en-tetes CORS permissifs (`Access-Control-Allow-Origin: *`). Les reponses d'erreur utilisent le format JSON `{"error":"... "}`.

### GET `/`

Retourne la page HTML integree (`webinterface.h`). Permet de piloter l'installation depuis un navigateur.

### GET `/api/status`

Etat courant de l'ESP32.

**Reponse 200**

```json
{
  "wifi": {
    "ip": "192.168.1.212",
    "rssi": -55
  },
  "relay": 1,
  "autoRelay": true,
  "currentSession": "DayOBananaBoat",
  "buttons": [1, 1, 0, 1, 1]
}
```

- `relay`: 1 si le relais principal est alimente (LOW sur GPIO10), 0 sinon.
- `autoRelay`: etat du mode automatique.
- `currentSession`: identifiant de session en cours (vide si aucune musique).
- `buttons`: etat stable des 5 boutons (`1` = relache, `0` = appuye).

### POST `/api/relay`

Permet un controle manuel du relais principal. Active automatiquement la sortie LED si elle est presente.

**Corps JSON**

```json
{ "on": true }
```

- `on = true`: active le relais principal (`setRelay(true)`); `false` pour le couper.
- En cas d'utilisation, le mode auto-relay est desactive (reste `false` jusqu'a reactivation explicite).

**Reponse 200**

```json
{ "relay": 1 }
```

### POST `/api/auto-relay`

Active ou desactive le mode automatique qui pilote le relais principal en fonction de l'API externe.

**Corps JSON**

```json
{ "enabled": true }
```

**Reponse 200**

```json
{
  "autoRelay": true,
  "success": true
}
```

### GET `/api/button-config`

Recupere l'association courante bouton -> session.

**Reponse 200**

```json
{
  "sessions": ["Intro", "Piece1", "", "", ""]
}
```

### POST `/api/button-config`

Enregistre l'association d'un bouton physique a une session (stockage en NVS).

**Corps JSON**

```json
{
  "button": 0,
  "session": "Intro"
}
```

- `button`: index 0 a 4 (Bouton 1 = index 0).
- `session`: identifiant attendu par le serveur externe. Peut etre vide pour effacer l'association.

**Reponse 200**

```json
{ "success": true }
```

**Reponse 400**

```json
{ "error": "invalid button index" }
```

(si `button` sort de l'intervalle 0-4 ou si le JSON est invalide)

### POST `/api/restart`

Demande un redemarrage logiciel de l'ESP32.

**Reponse 200**

```json
{ "restarting": true }
```

La reponse est envoyee avant l'appel a `ESP.restart()`.

### OPTIONS `/api/*`

Requête preflight pour les clients CORS. Retourne `204 No Content` avec les en-tetes CORS adequats.

## Bonnes pratiques d'integration

- Verifier que l'ESP32 et le serveur audio partagent le meme reseau ou qu'un routage approprie est defini.
- Adapter les timeouts (`http.setTimeout`) si le serveur distant met plus de 5 secondes a repondre.
- Journaliser le port serie pendant les phases de test pour verifier les transitions de relais et les reponses HTTP.
- Prevoir une alimentation stable pour les relais et les optocoupleurs afin d'eviter les rebonds mecaniques.

## Licence

Ce projet n'indique pas (encore) de licence explicite. Ajouter un fichier `LICENSE` si necessaire avant toute diffusion publique.
