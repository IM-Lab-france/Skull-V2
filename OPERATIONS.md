# Skull-V2 — documentation opérationnelle

## 1. Objet

Ce document décrit l’installation Skull actuellement observée sur le Raspberry
de production du réseau legacy. Il complète le README technique et doit être
utilisé avant toute intervention sur la machine ou le matériel.

Statut du diagnostic : **PARTIEL — services actifs, test matériel en mouvement
non exécuté**.

## 2. Installation de production observée

| Élément | Valeur observée |
|---|---|
| Hôte | `skull` |
| Adresse IPv4 | `192.168.1.116` |
| OS | Debian 12 |
| Architecture | ARM64 / Raspberry Pi |
| Répertoire applicatif | `/opt/skull` |
| Utilisateur des services | `skull` |
| Interface principale | `http://192.168.1.116:5000/` |
| Interface playlist | `http://192.168.1.116:5050/` |
| SSH | port 22 |
| Stockage | 29 Go, 5,6 Go utilisés, 22 Go disponibles au diagnostic |
| I²C | `/dev/i2c-1` présent |
| Audio | PulseAudio actif sous l’utilisateur `skull` |

Le compte `skull` dispose de `sudo` sans mot de passe et appartient aux groupes
`i2c`, `gpio`, `audio`, `video`, `dialout` et `spi`. Toute modification système
doit rester volontaire, tracée et réversible.

## 3. Services systemd

Les deux services sont activés au démarrage et actifs :

```text
servo-sync.service   → /opt/skull/.venv/bin/python /opt/skull/web_app.py
playlist-web.service → /opt/skull/launch_playlist_web.sh
```

Diagnostic :

```bash
systemctl status servo-sync.service playlist-web.service
systemctl is-enabled servo-sync.service playlist-web.service
journalctl -u servo-sync.service -u playlist-web.service --since today
```

Redémarrage, uniquement après confirmation :

```bash
sudo systemctl restart servo-sync.service
sudo systemctl restart playlist-web.service
```

## 4. Contrôles sans mouvement

```bash
curl -sS http://127.0.0.1:5000/status
curl -sS http://127.0.0.1:5000/api/sessions
systemctl is-active servo-sync.service playlist-web.service
bluetoothctl show
pactl info
ls -l /dev/i2c-1 /dev/gpiochip*
df -h / /opt/skull
```

État observé : application accessible, lecture arrêtée, playlist vide, quatre
canaux activés, boucle audio disponible mais arrêtée, Bluetooth alimenté mais
enceinte non connectée.

## 5. Architecture

```text
Visiteur / ESP32
        │ HTTP
        ▼
playlist-web :5050 ──HTTP──► web_app :5000
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
       Timeline JSON       PulseAudio/Bluetooth     PCA9685/I²C
             │                                         │
             └──────────────► SyncPlayer ────────► 4 servos

ESP32 192.168.1.212 ──HTTP──► API ESP32 de web_app
Gaze local 127.0.0.1:5005 ──► SyncPlayer (optionnel)
```

Servos : `jaw` CH0, `eye_left` CH1, `eye_right` CH2, `neck_pan` CH3. Les
limites mécaniques et offsets ne doivent pas être modifiés sans essai
progressif et arrêt électrique accessible.

## 6. Données et sauvegarde

Les données de production sont dans `/opt/skull/data`, les réglages dans
`/opt/skull/config` et les journaux dans `/opt/skull/logs`. Ces données sont
ignorées par Git : un `git pull` ne constitue pas une sauvegarde.

Le Raspberry contient 22 sessions éligibles au mode aléatoire, des MP3, JSON,
WAV mis en cache et deux boucles audio. Avant toute mise à jour :

```bash
sudo tar --exclude='.venv' --exclude='.venv_playlist' \
  -czf /var/backups/skull-data-$(date +%F-%H%M).tgz \
  /opt/skull/data /opt/skull/config
```

Copier ensuite l’archive hors du Raspberry et vérifier son intégrité. Cette
procédure n’a pas encore été exécutée.

## 7. Dérive Git et déploiement

La production est basée sur le commit `57455ce`, mais contient des
modifications locales sur `web_app.py`, `loop_player.py`, l’interface web et le
lanceur playlist, ainsi qu’un `requirements.txt` généré localement.

Avant toute synchronisation :

```bash
cd /opt/skull
git status --short --branch
git diff --stat
```

Ne pas utiliser `git reset`, `git clean` ou un déploiement automatique avant
export du diff et sauvegarde de `data/` et `config/`.

## 8. Bluetooth et audio

```bash
systemctl status bluetooth.service
bluetoothctl show
bluetoothctl devices
pactl info
pactl list short sinks
```

Le contrôleur était alimenté mais l’enceinte non connectée. Une session audio
n’est pas validée tant qu’une enceinte n’est pas connectée et qu’un test audio
contrôlé n’a pas été réalisé.

## 9. Remise en route matérielle

1. Vérifier l’alimentation du Raspberry, du PCA9685 et des servos.
2. Vérifier que l’arrêt électrique des servos reste accessible.
3. Vérifier `/dev/i2c-1` et le câblage SDA/SCL.
4. Tester l’interface et le statut, sans lecture.
5. Tester un seul servo à faible amplitude, zone dégagée.
6. Tester l’audio Bluetooth à volume réduit.
7. Jouer une session courte connue.
8. Vérifier les logs et la température avant une session longue.

Ne jamais lancer une session pendant qu’une personne travaille dans la zone de
mouvement du crâne.

## 10. Sécurité et limites

Les interfaces Flask écoutent sur toutes les interfaces réseau et plusieurs
routes contrôlent la lecture, le Bluetooth, l’ESP32, les fichiers et les
services. La version actuelle est adaptée à un réseau legacy de confiance,
pas à une exposition Internet directe.

Priorités : désactiver `debug=True`, ajouter une authentification ou filtrer le
réseau, séparer les routes publiques des routes d’administration, sauvegarder
les données runtime et ajouter des tests de timeline/playlist.

## 11. État du diagnostic — 2 septembre 2026

- Services : **VALIDÉ — actifs et activés**.
- HTTP : **VALIDÉ — `/status` et `/api/sessions` répondent**.
- OS et espace disque : **VALIDÉ**.
- I²C : **PARTIEL — périphérique présent, PCA9685 non détecté par outil dédié**.
- Bluetooth : **PARTIEL — contrôleur actif, enceinte déconnectée**.
- Audio : **PARTIEL — PulseAudio actif, sortie configurée**.
- Servos : **NON TESTÉ — aucun mouvement déclenché à distance**.
- Sauvegarde : **NON VALIDÉE — aucune archive créée**.
- Alignement GitHub : **BLOQUÉ — modifications locales à préserver**.

## 12. Interactions entre les sous-ensembles

### 12.1 Skull principal

Le Skull est le point d’orchestration de la lecture. `web_app.py` charge une
session, vérifie la présence du MP3 et du JSON, demande la connexion Bluetooth,
charge la timeline, suspend la boucle d’ambiance, puis démarre `SyncPlayer`.
`SyncPlayer` commande le PCA9685 par I²C et joue l’audio via PulseAudio.

Le Skull expose notamment :

| Appelant | Appel | Médium | Effet |
|---|---|---|---|
| Interface locale ou playlist | `POST /play` ou `/api/enqueue` | HTTP | Lecture directe ou ajout en file |
| ESP32 boutons | `POST /api/enqueue` | HTTP | Ajout/lecture d’une session |
| ESP32 boutons | `GET /api/sessions` | HTTP, toutes les secondes | État de `playlist.current` pour les relais |
| Sonnette | `POST /play` | HTTP | Déclenchement de la session `Accueil` |
| Skull | PCA9685 | I²C local | Commandes des quatre servos |
| Skull | PulseAudio/BlueZ | IPC local + Bluetooth | Sortie audio |
| Skull | webhook domotique | HTTP sortant | Déclenchement de la fumée lors du démarrage de `Accueil` |

Le webhook fumée n’est appelé que lorsque le nom de session normalisé est
`Accueil`, après le démarrage du lecteur. Il possède un timeout court et son
échec est journalisé sans annuler automatiquement la lecture. L’URL contient
un secret et ne doit jamais être recopiée dans la documentation.

### 12.2 Gestion des boutons ESP32

Le firmware de l’ESP32 boutons utilise cinq entrées `INPUT_PULLUP`. Après
anti-rebond, un front d’appui déclenche un `POST` JSON vers le Skull :

```text
ESP32 bouton → POST http://<skull>:5000/api/enqueue
             {"session":"<session associee>"}
```

Les associations sont conservées dans la NVS de l’ESP32. En parallèle, si le
mode automatique est activé, l’ESP32 interroge `GET /api/sessions` chaque
seconde. Une playlist active allume le relais principal et coupe le relais
associé aux boutons ; au repos, l’état est inversé.

Le firmware prévoit **5 boutons**, tandis que `web_app.py` expose actuellement
`ESP32_BUTTON_COUNT = 3` affectations côté serveur. Cette asymétrie doit être
résolue avant migration ou exploitation complète des cinq boutons.

### 12.3 Sonnette à optocoupleur

La sonnette est un ESP32 séparé, avec détection d’impulsion sur son entrée
GPIO. L’interruption ne fait pas d’appel réseau directement : elle incrémente
un compteur protégé, puis la boucle principale consomme les événements et
effectue un appel HTTP.

Configuration observée dans le firmware :

- IP statique prévue : `192.168.1.211` ;
- cible par défaut : Skull `192.168.1.116:5000` ;
- endpoint : `POST /play` ;
- session par défaut : `Accueil` ;
- timeout HTTP : 5 secondes ;
- jusqu’à 3 tentatives espacées de 200 ms ;
- anti-spam : un appel accepté au maximum toutes les 10 secondes ;
- entrée : GPIO4, niveau actif haut, anti-rebond 5 ms.

La sonnette ne reçoit pas de retour fonctionnel durable du Skull : elle
journalise le code HTTP et conserve le dernier résultat dans son interface. Une
perte réseau peut donc produire un événement perdu malgré les retries.

### 12.4 Fumée

La fumée n’est pas pilotée directement par le Skull ni par l’ESP32 boutons. Le
chemin actuel est :

```text
Déclencheur (bouton, sonnette ou interface)
        → session "Accueil" sur le Skull
        → POST webhook domotique
        → automatisation domotique
        → relais / machine à fumée
```

Le système dépend donc de trois conditions : la session `Accueil` doit être
valide, le Skull doit atteindre le contrôleur domotique, et l’automatisation
domotique doit être disponible. Le webhook est un appel HTTP sortant avec un
secret dans l’URL ; il faut le remplacer par un mécanisme authentifié et
segmenté avant le réseau IoT.

### 12.5 Flux de bout en bout

```text
Sonnette ──POST /play──────────────┐
                                   ▼
Bouton ESP32 ──POST /api/enqueue──► Skull web_app :5000
                                   │       │
Playlist :5050 ──HTTP─────────────┘       ├─► SyncPlayer ─► PCA9685/I²C ─► servos
                                           ├─► PulseAudio/BlueZ ─► casque/enceinte
                                           └─► POST webhook ─► domotique ─► fumée

ESP32 boutons ◄────GET /api/sessions──── Skull
       └─ adapte ses relais selon playlist.current
```

## 13. Contraintes de migration vers le réseau IoT

### Flux réseau à autoriser

Une migration ne doit pas être traitée comme un simple changement d’adresse.
Les flux minimums à prévoir sont :

| Source | Destination | Port/protocole | Sens | Usage |
|---|---|---|---|---|
| ESP32 boutons | Skull | TCP/5000 HTTP | IoT → Skull | enqueue et état des sessions |
| Sonnette | Skull | TCP/5000 HTTP | IoT → Skull | déclenchement `Accueil` |
| Playlist publique | Skull | TCP/5000 HTTP | réseau public contrôlé → Skull | file de lecture |
| Skull | ESP32 boutons | TCP/80 HTTP | Skull → IoT | relais, statut, configuration |
| Skull | contrôleur domotique | TCP/8123 HTTP actuellement | Skull → IoT/domotique | webhook fumée |
| Skull | DNS/NTP si utilisés | selon infrastructure | Skull → services | résolution et horloge |

Les flux I²C, GPIO, PulseAudio, Bluetooth et gaze `127.0.0.1:5005` restent
locaux au Skull et ne nécessitent aucun routage IoT.

### Risques et adaptations

1. **Adressage en dur** : le firmware boutons, la sonnette et le webhook
   utilisent des adresses legacy. Prévoir DNS interne ou configuration injectée,
   puis vérifier chaque firmware avant bascule.
2. **HTTP sans chiffrement** : les sessions, états et commandes relais passent
   en clair. Le réseau IoT doit être filtré ; l’étape cible est HTTPS avec
   authentification ou un broker MQTT avec ACL.
3. **Pas d’authentification applicative** : les endpoints Skull et ESP32
   contrôlent des actions physiques. L’isolation VLAN seule ne suffit pas si un
   poste compromis atteint le VLAN IoT.
4. **mDNS non routé** : `SkullHard.local` ne doit pas être considéré comme une
   dépendance inter-VLAN. Utiliser DNS ou IP réservée.
5. **Disponibilité** : le bouton et la sonnette ont des timeouts/retries mais
   pas de file persistante côté émetteur. Il faut décider si un événement perdu
   est acceptable.
6. **Décalage des boutons** : harmoniser les cinq entrées du firmware avec les
   trois affectations exposées par le serveur.
7. **Dépendance domotique** : définir le comportement si le webhook fumée est
   inaccessible : lecture maintenue, fumée non déclenchée et alarme explicite.
8. **Sécurité physique** : toute route réseau qui pilote relais ou servos doit
   être filtrée par source et protégée avant d’être accessible depuis l’IoT.

### Stratégie recommandée

Conserver une phase de coexistence : réserver les nouvelles adresses IoT,
autoriser temporairement les flux exacts entre legacy et IoT, vérifier les
appels en lecture seule, puis migrer un émetteur à la fois. La validation finale
doit couvrir : bouton, sonnette, lecture audio, servos, relais et fumée, avec
preuve de refus des ports non nécessaires.
