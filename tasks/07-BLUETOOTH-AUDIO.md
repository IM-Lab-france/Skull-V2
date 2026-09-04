# Phase 07 — fiabiliser Bluetooth et audio

## État de référence

La sortie audio de validation actuelle est une Bose SoundLink Mini II. Un
périphérique découvert ne doit jamais être considéré comme enceinte tant que
le profil A2DP Audio Sink (`0000110b-0000-1000-8000-00805f9b34fb`) n’est pas
disponible.

Les essais de scan sont sans effet matériel. Appairage, confiance, connexion,
changement de sink ou lecture audio exigent une confirmation avant action sur le
Raspberry.

## SKULL-07.1 — créer un modèle d’état Bluetooth explicite

### Champs minimaux

`address`, `name`, `discovered`, `paired`, `trusted`, `connected`,
`audio_sink_capable`, `pulse_sink`, `last_error`, `updated_at`.

### Étapes

1. Valider les MAC avec une expression stricte avant toute commande.
2. Lire propriétés BlueZ et UUID séparément.
3. Déduire `audio_sink_capable` uniquement depuis les UUID/profils.
4. Distinguer périphérique inconnu et information temporairement indisponible.
5. Ne jamais transformer `connected=true` en preuve que le sink PulseAudio est
   prêt.

### Acceptation

- fixtures JBL, SoundLink et périphérique BLE non audio ;
- aucun périphérique BLE seul proposé comme sortie audio.

## SKULL-07.2 — sécuriser l’exécution des commandes

### Étapes

1. Centraliser l’appel à `bluetoothctl`, `pactl` ou `wpctl`.
2. Utiliser une liste d’arguments, jamais une chaîne avec shell.
3. Ajouter timeout, code retour, sortie normalisée et message d’erreur redigé.
4. Empêcher deux scans/appairages concurrents.
5. Traiter explicitement timeout, agent indisponible, refus, appareil éteint et
   profil absent.
6. Tester avec sorties enregistrées, sans BlueZ réel.

### Acceptation

- aucune injection par nom ou MAC ;
- une commande suspendue ne bloque pas l’API ;
- erreurs stables et compréhensibles dans l’IHM.

## SKULL-07.3 — séparer les opérations de l’IHM

### Contrats

- `scan` découvre seulement ;
- `pair` appaire seulement ;
- `trust` autorise les reconnexions ;
- `connect` établit la liaison ;
- `select-output` choisit le sink audio ;
- `test-audio` joue un son borné, après confirmation.

### Étapes

1. Afficher chaque état séparément.
2. Désactiver les actions impossibles selon l’état.
3. Ne pas enchaîner automatiquement pair/trust/connect sans l’afficher.
4. Rendre chaque opération idempotente.
5. Rafraîchir l’état après chaque commande, même en cas d’échec.

### Acceptation

- l’IHM ne montre plus « connecté » si seul l’appairage est réussi ;
- le détail de l’échec est actionnable sans sortie brute sensible.

## SKULL-07.4 — sélectionner et vérifier le sink audio

### Étapes

1. Attendre de manière bornée l’apparition du sink après connexion.
2. Sélectionner le profil A2DP, puis le sink par identifiant exact.
3. Vérifier le sink par défaut et l’état non suspendu.
4. Ne modifier volume ou mute que si la configuration le demande.
5. Enregistrer l’identifiant stable, jamais seulement l’index PulseAudio.
6. Définir une sortie locale de secours explicite et désactivable.

### Acceptation

- `connected`, A2DP et sink par défaut sont trois preuves distinctes ;
- aucun basculement silencieux sur une enceinte différente.

## SKULL-07.5 — automatiser la reconnexion contrôlée

### Étapes

1. Au démarrage, lire l’adresse configurée sans lancer de scan global.
2. Si l’appareil est trusted mais absent, poursuivre le démarrage et publier un
   état dégradé.
3. Retenter avec nombre maximal, délai progressif et annulation à l’arrêt.
4. Après connexion, vérifier le sink avant de déclarer l’audio prêt.
5. Ne jamais lancer automatiquement un appairage.
6. Journaliser une ligne par tentative, sans boucle bruyante.

### Acceptation

- application disponible enceinte éteinte ;
- reconnexion autonome lorsque l’enceinte revient ;
- arrêt du service immédiat malgré une reconnexion en attente.

## SKULL-07.6 — tests logiciels

Créer des scénarios pour : scan vide, JBL A2DP, BLE non audio, appairage refusé,
connexion réussie sans sink, sink retardé, disparition pendant lecture, timeout,
reconnexion et arrêt pendant attente.

### Acceptation

- tests Windows/Linux sans matériel ;
- horloge simulée, donc aucun délai réel ;
- couverture de toutes les transitions d’état.

## SKULL-07.7 — validation physique de la Bose SoundLink Mini II

### Confirmation requise

Tout changement Bluetooth ou émission sonore sur le Skull.

### Séquence

1. Noter état BlueZ et sink avant action.
2. Allumer la Bose sans mode appairage : vérifier la reconnexion.
3. Vérifier A2DP et sink par défaut.
4. Jouer un fichier de test court au volume minimal convenu.
5. Éteindre la Bose, attendre l’état dégradé, rallumer et vérifier la reprise.
6. Redémarrer le service puis le Raspberry dans deux essais séparés.
7. Après chaque essai, vérifier absence de processus audio orphelin.

### Rollback

Restaurer configuration audio sauvegardée, sink précédent et version de service.
Ne jamais supprimer les appairages existants comme méthode de rollback.

### Acceptation

- trois cycles extinction/rallumage réussis ;
- reconnexion après redémarrage ;
- preuve audio explicitement confirmée par l’utilisateur.

## SKULL-07.8 — découpler la reconnexion Bluetooth de l’IHM

### Constat

La reconnexion actuelle est bornée et protégée par un verrou, mais elle peut
encore être déclenchée dans le traitement synchrone d’une requête web :
notamment lors de `/status`, au démarrage d’une session et lorsqu’une action de
volume ne trouve pas de transport. Avec un worker Gunicorn unique, une commande
BlueZ lente peut donc retarder ou bloquer les autres routes de l’IHM.

### Objectif

Une route de lecture d’état doit rester rapide et sans effet de bord. La
reconnexion automatique doit être un travail séparé, à instance unique,
annulable et observable ; la connexion demandée explicitement par l’utilisateur
doit rester distincte de cette politique automatique.

### Étapes

1. Inventorier tous les appelants de la reconnexion et les classer en
   lecture d’état, action utilisateur ou démarrage de lecture.
2. Interdire toute commande Bluetooth mutante dans `/health/*`, `/status` et
   les rafraîchissements périodiques de l’IHM.
3. Remplacer la reconnexion depuis une route de lecture par la publication d’un
   état (`connected`, `connecting`, `retrying`, `degraded`, `audio_ready`) et
   l’envoi d’une demande à un worker ou ordonnanceur de reconnexion unique.
4. Garantir une seule tentative active par périphérique, avec délai minimal,
   nombre maximal d’essais, expiration externe, annulation à l’arrêt et
   suppression des demandes obsolètes.
5. Ne jamais lancer automatiquement `pair`, `trust`, un scan global ou une
   sélection de sink d’une autre adresse.
6. Faire dépendre `audio_ready` de trois preuves séparées : connexion BlueZ,
   profil A2DP actif et sink PulseAudio exact, non suspendu et par défaut.
7. Retourner à l’IHM un résultat stable et non bloquant ; mapper un timeout
   technique en état dégradé ou HTTP 504 selon l’action explicite, sans exposer
   la sortie brute des outils.
8. Tester les sondages `/status` concurrents, les doubles clics, la disparition
   de l’enceinte, l’annulation du service, le redémarrage et la reprise après
   retour de l’enceinte.

### Acceptation

- `/health/*` et `/status` restent disponibles pendant une reconnexion lente ;
- un seul appel `bluetoothctl connect` est actif à la fois ;
- les sondages périodiques ne déclenchent pas de boucle bruyante ni d’appairage ;
- l’IHM distingue clairement état lu, reconnexion en cours, échec et audio prêt ;
- aucun worker HTTP n’est occupé par une attente Bluetooth non bornée ;
- les tests d’annulation et de concurrence passent sans matériel réel.

## SKULL-07.9 — découpler et temporiser la supervision ESP32

### Objectif

La supervision automatique de l’ESP32 doit être séparée des commandes
utilisateur. Les rafraîchissements périodiques ne doivent pas ouvrir une
requête réseau à chaque appel HTTP ni se concurrencer entre onglets, boutons ou
workers. Une indisponibilité doit produire un état dégradé avec backoff et
circuit breaker, puis permettre une reprise contrôlée au retour du firmware.

### Étapes

1. Inventorier les appels ESP32 et distinguer lecture automatique, lecture
   manuelle explicite et commandes mutantes.
2. Faire alimenter `/esp32/status` par un instantané cache ; réserver la
   vérification immédiate à une action manuelle distincte et bornée.
3. Créer un superviseur à instance unique, annulable à l’arrêt, avec une seule
   sonde active et une source (`automatic` ou `manual`) observable.
4. Ajouter un délai nominal, un backoff progressif borné et un circuit breaker
   après plusieurs échecs ; ne pas relancer une boucle agressive lorsque
   l’ESP32 est indisponible.
5. Sérialiser les sondes et commandes réseau ESP32, sans bloquer deux appels
   concurrents ni exposer de sortie brute ou de secret.
6. Distinguer dans l’IHM l’état en ligne, hors ligne, en vérification et la
   dernière erreur ; ne pas confondre supervision automatique et test manuel.
7. Tester la panne, la reprise, le polling firmware, l’annulation, les doubles
   sondes, la concurrence et la disponibilité des routes pendant une sonde
   lente.

### Acceptation

- `/esp32/status` reste rapide et ne déclenche pas de requête réseau ;
- une seule sonde ESP32 est active à la fois ;
- les échecs activent un backoff et un circuit breaker bornés ;
- une sonde manuelle peut provoquer une reprise sans créer de boucle ;
- les commandes relais/boutons restent distinctes et sérialisées ;
- l’annulation à l’arrêt ne laisse aucun worker de supervision orphelin ;
- les tests de panne/reprise et de concurrence passent sans matériel réel.
