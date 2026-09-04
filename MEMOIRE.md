# Mémoire du projet Skull-V2

Dernière mise à jour : 4 septembre 2026.

## Audit de continuité — 4 septembre 2026

- Le dépôt de pilotage `C:\Skull-V2` reste sur `main` (`69cb37f`) avec ses
  documents, preuves et journaux de continuité non committés. Il ne contient pas
  la suite de tests : `python -m pytest -q` y collecte donc zéro test. Ce n'est
  pas une régression de test, mais la conséquence de la séparation des
  worktrees.
- Le code modernisé, les tests et la configuration phase 8 sont dans
  `C:\Users\cedri\Documents\Codex\Skull-V2-phase8-2026`, branche
  `codex/phase8-skull-2026` (`873056e` au contrôle). La branche est propre ;
  elle diffère de `main` par 234 fichiers et plus de 41 000 lignes. Une fusion
  exige donc une revue et un plan de rollback dédiés, pas une opération de
  reprise ordinaire.
- Le worktree `C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`,
  branche `codex/production-skull-2026`, conserve la source de vérité dérivée
  du commit de production. Il ne doit pas être supprimé ni réinitialisé.
- `SKULL-08.7` est VALIDÉ sur la candidate distante : configuration TOML et
  permissions vérifiées, candidate sur 5000, healthchecks `live`/`ready` 200 et
  rollback disponible. `SKULL-08.4` et `SKULL-08.6` restent PARTIELLES ;
  `SKULL-08.5` est ANNULÉE car la cible Home Assistant observée ne correspond
  pas à l'action fumée attendue.
- `SKULL-11.5` est PARTIEL : le Skull est sur `192.168.40.20`,
  `skull.home.arpa` résout, les ACL minimales et les refus attendus sont
  prouvés ; la continuité complète des clients legacy reste à démontrer.
- La prochaine tâche autorisée est `SKULL-08.6`, dans le worktree phase 8.
  Elle doit fermer ou qualifier explicitement les dépendances DNS restantes et
  leurs modes de panne avant le début de la phase 9. La phase 13 a été créée
  pour le modèle événement → action ; elle ne donne aucune autorisation de
  modifier la sonnette ou la fumée.

## Situation observée

- Dépôt principal local : `C:\Skull-V2`.
- Dépôt GitHub : `IM-Lab-france/Skull-V2`.
- Raspberry de production : hôte `skull`, IPv4 legacy `192.168.1.116`.
- Système : Debian 12 ARM64 sur Raspberry Pi.
- Déploiement : `/opt/skull`, utilisateur de service `skull`.
- Interfaces : port 5000 principal, port 5050 playlist.
- Services `servo-sync.service` et `playlist-web.service` actifs et activés.
- I²C, GPIO et PulseAudio présents.
- Le compte `skull` possède actuellement `sudo` sans mot de passe.
- Une clé SSH locale dédiée permet l’administration depuis ce poste.

## État logiciel important

- Le dépôt local principal était propre et aligné sur `origin/main` au début du
  diagnostic.
- La production Raspberry est basée sur le commit `57455ce` et possède neuf
  fichiers applicatifs modifiés localement.
- Les modifications de production ne doivent pas être écrasées par `pull`,
  `reset`, `clean` ou réinstallation avant export et sauvegarde.
- Les données, réglages et logs de production ne sont pas protégés par Git.
- La production contient environ 22 sessions éligibles au mode aléatoire.
- Les logs historiques sont volumineux et nécessitent une rotation.
- Flask fonctionne encore avec le mode debug/reloader, ce qui crée plusieurs
  processus applicatifs et doit être corrigé après ajout de tests.
- Les routes d’administration ne sont pas authentifiées et écoutent sur le
  réseau.

## Matériel et fonctionnement

- PCA9685 sur bus I²C, quatre servos : mâchoire, yeux gauche/droit et cou.
- Les mouvements mécaniques n’ont pas été testés pendant cette reprise.
- Les offsets actifs observés sont stockés dans la configuration runtime ; ils
  doivent être sauvegardés avant toute intervention.
- Le gaze utilise UDP sur `127.0.0.1:5005` et reste local au Raspberry.
- Bluetooth et audio utilisent BlueZ et PulseAudio.

## Bluetooth réalisé pendant la reprise

- Les deux anciennes Bose SoundLink Mini ont été supprimées de BlueZ à la
  demande de l’utilisateur.
- `SINB238` a été identifié comme périphérique BLE sans profil audio ; il ne
  peut pas servir de sortie sonore.
- Le JBL Quantum 360 a été détecté, appairé, approuvé et connecté pendant
  l’essai historique.
- La Bose SoundLink Mini II est désormais la sortie audio de validation
  actuelle du Skull.
- Un sink A2DP PulseAudio a été observé pour la Bose après correction de la
  chaîne de connexion et de sélection de sortie.
- Trois cycles extinction/rallumage de la Bose ont été validés ; un worker de
  reconnexion autonome est maintenant déployé sur la candidate. Après ajout
  réversible de l’activation systemd, la candidate revient seule après reboot
  et `servo-sync.service` reste désactivé.

## Correctif de reconnexion Bluetooth

- `/status` ne lance plus de reconnexion synchrone ; il lit l’état et le
  résultat observable du worker.
- Le worker est unique, annulable, relance la politique bornée toutes les dix
  secondes et sélectionne le sink seulement après connexion BlueZ et preuve
  A2DP/PulseAudio.
- Le délai demandé par le contrôleur est maintenant propagé à la commande
  `bluetoothctl`, y compris sur le superviseur Linux `timeout`.
- La candidate `/opt/skull-candidate` répond aux healthchecks, la Bose était
  connectée et `audio_ready=true` après redémarrage contrôlé du service ; le
  service legacy est resté inactif.
- `SKULL-07.8` est validée : la reconnexion Bluetooth est exécutée par un
  worker autonome hors du chemin HTTP, `/status` publie un état cache et
  `connection_state` distingue reconnexion, dégradation, connexion et audio
  prêt. Les tests de concurrence/annulation et la suite complète (`266
  passed`) sont verts ; la candidate est active au boot et le service legacy
  désactivé.
- `SKULL-07.9` est validée : la supervision ESP32 utilise un superviseur
  unique hors des routes HTTP, avec cache, backoff, circuit breaker,
  sérialisation et annulation. `GET /esp32/status` ne sonde plus le firmware ;
  `POST /esp32/status/check` est réservé au contrôle manuel. La candidate est
  déployée et saine ; la configuration ESP32 reste désactivée, donc le polling
  réel n’est pas lancé sans activation explicite. La suite compte `269 passed`.

## Nettoyage Bluetooth du 3 septembre 2026

- Le bond `JBL Quantum 360` a été supprimé du Skull.
- Le périphérique BLE connu `SINB238`, non appairé, a également été supprimé.
- Les deux anciennes sauvegardes `bluetooth_device.env.bak-*` ont été retirées
  de la configuration active du Skull.
- Vérification finale : la liste des périphériques connus et la liste des
  périphériques appairés ne contiennent plus que `Bose Mini II SoundLink`.
- Trois nouveaux cycles extinction/rallumage ont été validés après correction
  de l’adresse active ; la Bose revient automatiquement avec `audio_ready=true`.
- Un reboot complet avec la candidate activée a confirmé le retour autonome de
  `skull-candidate.service` sur le port 5000, avec healthchecks HTTP 200 ;
  `servo-sync.service` est resté désactivé. La Bose est restée la seule cible
  appairée et connectée. Le sink A2DP est apparu après l’initialisation
  PulseAudio ; l’émission faible volume a un retour technique nul et
  l’utilisateur a confirmé avoir entendu trois bips. `SKULL-07.7` est validée.
- Les mentions historiques dans les preuves et fixtures de test sont
  conservées pour la traçabilité et ne sont pas des références runtime.

## Interactions entre équipements

- L’ESP32 boutons est prévu en `192.168.1.212` et appelle le Skull en HTTP sur
  le port 5000.
- Un appui envoie `POST /api/enqueue` avec le nom de session.
- L’ESP32 interroge `GET /api/sessions` chaque seconde et adapte deux relais à
  `playlist.current`.
- Le firmware possède cinq boutons, mais le serveur principal expose seulement
  trois affectations : incohérence à résoudre.
- La sonnette est prévue en `192.168.1.211` et déclenche `POST /play` pour la
  session `Accueil`, avec retries et anti-spam.
- Le démarrage réussi d’`Accueil` provoque un POST vers un webhook domotique,
  qui pilote ensuite la fumée.
- Le secret du webhook est actuellement dans le code et doit être remplacé.

## Décisions prises

- Modernisation incrémentale, aucune réécriture big bang.
- Compatibilité des routes legacy maintenue pendant la transition.
- Tests de caractérisation avant refactoring.
- Mode matériel simulé obligatoire avant tests automatisés.
- Un seul processus doit posséder le matériel.
- Pas de modification mécanique ou d’offset sans validation physique.
- Sauvegarde et rollback obligatoires avant déploiement.
- Migration IoT après stabilisation du Skull principal.

## Documentation créée

- `README.md` corrigé pour l’interface playlist réelle.
- `OPERATIONS.md` : exploitation, architecture, flux et contraintes IoT.
- `OBJECTIF.md` : finalité, périmètre et critères de réussite.
- `TODO.md` : phases et validations du chantier.
- `MEMOIRE.md` : état présent et décisions de continuité.
- `LUNA.md` : protocole d’exécution, autorisations, preuves et prompt unitaire
  pour GPT-5.6 Luna.
- `tasks/00-REPRISE.md` à `tasks/12-VALIDATION-MATERIELLE.md` : fiches
  atomiques détaillant prérequis, étapes, critères d’acceptation et rollback.
- `evidence/README.md` : format des preuves par identifiant de tâche.

## État des modifications locales

Les fichiers de pilotage sont locaux dans `C:\Skull-V2`. Ils ne sont pas
encore poussés sur GitHub ni copiés sur le Raspberry. Le Raspberry a toutefois
été modifié pour l’accès SSH et la configuration Bluetooth demandés pendant la
session.

- `SKULL-01.3` est validée : archive distante créée le 2 septembre 2026 dans
  `/var/backups/skull/20260902T192200Z/`, checksum vérifié, 113 entrées
  contrôlées, services restés actifs. La copie hors Raspberry reste à faire.
- `SKULL-01.4` est validée : archive copiée dans `C:\Skull-V2\backups\SKULL-01.3`,
  checksum distant/local identique, extraction temporaire réussie. La copie
  temporaire sensible reste dans le dossier Temp exact indiqué dans la preuve.
- `SKULL-01.5` est préparée : `/dev/mmcblk0` est identifié sur le Skull comme
  carte SD de 31 914 983 424 octets et la carte locale `E:` correspond au
  disque physique Windows `3` de même taille. La méthode hors ligne et la
  restauration sont documentées dans `evidence/SKULL-01.5/RESULT.md`. Aucun
  `dd`, arrêt ou écriture bloc n’a été exécuté ; confirmation explicite encore
  requise avant d’écraser `E:`.
- `SKULL-01.5` est validée pour la sauvegarde : Rufus 4.14 a créé
  `D:\Skull-Backups\skull-20260902T200000Z.vhdx` depuis le disque source `8`
  monté en `L:`. L’image fait 8 963 227 648 octets et son SHA-256 est
  `3FEFF0E7EA02D6933338E4E792BBA7082B5B00B71A3B63A552870244216923B8`.
  `E:` n’a pas été modifiée. La restauration n’est pas encore testée.
- `SKULL-02.1` est validée : le worktree
  `C:\Users\cedri\Documents\Codex\Skull-V2-production-2026` et la branche
  `codex/production-skull-2026` sont basés sur le commit de production
  `57455ce3870af15485035ec9482761e34e3b592f`. Aucun push ni changement distant
  n’a été effectué ; le dépôt principal et ses modifications sont préservés.
- `SKULL-02.2` est validée : le patch expurgé de `SKULL-01.2` a été appliqué
  dans le worktree isolé. Huit fichiers sont modifiés ; Python et les deux
  fichiers JavaScript passent les contrôles syntaxiques. Le diff ajoute le
  volume de boucle, un endpoint `/loop/volume`, le webhook `Accueil` configuré
  par environnement et des changements UI. Aucun secret, runtime ou push n’a
  été ajouté ; inventaire dans `evidence/SKULL-02.2/`.
- `SKULL-02.3` est validée : les imports ont été comparés aux freezes de
  production, `requirements.in`, `requirements-playlist.in`, les deux locks et
  `DEPENDENCIES.md` ont été créés. Les locks ont été régénérés puis installés
  dans un venv éphémère Python 3.11 `linux/arm64` sous Docker Desktop ;
  `compileall` et les imports de contrôle passent (`IMPORTS_OK`). Aucun accès
  I2C, GPIO ou Bluetooth, aucun secret et aucun changement Raspberry n’ont été
  effectués. La compatibilité matérielle reste à valider sur le Skull.
- `SKULL-02.4` est validée : les clés et schémas observables des configurations
  runtime ont été documentés dans `config/` avec des valeurs neutres. Les
  fichiers actifs restent ignorés par Git, les exemples sont suivis et trois
  tests contrôlent JSON, schémas et absence de secrets/webhooks. La lecture
  distante de la configuration réelle reste à faire quand SSH vers
  `192.168.1.116` sera disponible.
- `SKULL-02.5` est validée : `main` et `origin/main` sont alignés au commit
  `69cb37f`, tandis que le worktree isolé reste basé sur la production
  `57455ce`. Les validations Python, JavaScript, tests de configuration,
  `git diff --check` et la comparaison SHA-256 des neuf fichiers applicatifs
  passent. Les différences sont classées ; aucune normalisation de fins de
  ligne, aucun commit, push ou accès matériel n’a été effectué.
- `SKULL-03.1` est validée : `pytest` est déclaré dans
  `requirements-dev.in`, la collecte est configurée dans `pytest.ini`, et les
  répertoires de tests sont présents. Deux sentinelles passent sans importer
  le matériel réel ; le test de mode production échoue volontairement quand
  `SKULL_ENV=production` est activé. Aucun appel Raspberry n’a été effectué.
- `SKULL-03.2` est validée : quatre formats de timeline sont couverts par 12
  tests avec fixtures synthétiques. Les durées, frames, timestamps et angles
  de la version actuelle sont figés, y compris les comportements étranges de
  mâchoire, doublons, canaux absents, valeurs hors limites et durée nulle.
  `timeline.py` n’a pas été modifié et aucun matériel n’a été utilisé.
- `SKULL-03.3` est validée : la détection des sessions est testée avec des
  placeholders synthétiques. Les MP3/JSON requis, caches WAV, fichiers
  multiples, noms Unicode/espaces/casse et traversée de chemin sont
  documentés. Le code accepte plusieurs fichiers et `sync_player.py` utilise
  le premier résultat de `Path.glob`; aucune correction ni donnée de
  production n’a été ajoutée.
- `SKULL-03.4` est validée : les contrats HTTP legacy principaux sont testés
  avec Flask et adaptateurs factices. 25 tests passent sur les routes de statut,
  sessions, lecture, playlist, catégories et passerelle ESP32. Les snapshots
  vérifient statuts, types et clés sans IP, MAC, secret ou appel distant ; la
  carte des interactions est dans `tests/contracts/HTTP-MAP.md`.
- `SKULL-03.5` est validée : la playlist et l’état de lecture sont caractérisés
  avec des adaptateurs factices. Les scénarios de file, transitions, skip,
  stop, suppression, aléatoire, concurrence et erreurs audio/Bluetooth passent
  localement. Les comportements asynchrones et retries sont documentés sans
  correction.
- `SKULL-03.6` est validée : le webhook fumée et l’adaptateur ESP32 sont
  caractérisés par 6 scénarios dédiés dans un total de 40 tests. Le webhook
  local n’est appelé qu’après démarrage et uniquement pour `Accueil` ; timeout,
  refus et HTTP 500 ne stoppent pas la lecture. Les erreurs réseau et JSON de
  l’ESP32 sont rapportées sans appel réel ni secret.
- `SKULL-04.1` est validée : `adapters.py` définit six protocoles minimaux,
  documentés et importables sous Windows sans bibliothèque Raspberry. Les faux
  adaptateurs de `tests/fixtures/fake_adapters.py` vérifient la conformité et
  journalisent les appels dans 3 tests dédiés. Aucune route HTTP, logique
  métier, I²C, GPIO, audio réel, Bluetooth réel ou réseau réel n’a été ajouté.
- `SKULL-04.2` est validée : `simulated_hardware.py` impose explicitement
  `SKULL_HARDWARE_MODE=simulated`, reproduit les clamps, offsets, canaux et
  impulsions du pilote réel, et capture chaque commande avec un timestamp
  logique déterministe. Le faux contrôleur PCA9685 ne touche aucun périphérique;
  47 tests passent localement. Le pilote réel et les routes HTTP restent
  inchangés; l’audio simulé est réservé à `SKULL-04.3`.
- `SKULL-04.3` est validée : `simulation_clock.py` fournit une horloge
  injectable dont `sleep` n’attend pas, et `simulated_audio.py` fournit un
  lecteur audio déterministe compatible avec `AudioAdapter`. Les transitions,
  fin de piste unique et dérive timeline/audio sont testées, y compris une
  session simulée de 300 secondes en moins d’une seconde. 52 tests passent;
  aucun device audio ni route HTTP n’a été utilisé.
- `SKULL-04.4` est validée : `simulated_external.py` fournit des adaptateurs
  Bluetooth, ESP32 et fumée entièrement en mémoire. Les états Bluetooth
  découvert/appairé/trusted/connecté/A2DP/sink sont séparés, les opérations et
  payloads ESP32 sont journalisés, et la fumée injecte succès, timeout ou HTTP
  simulé. 59 tests passent sans réseau réel, subprocess, socket ou adresse de
  production; la sélection centralisée des adaptateurs reste réservée à
  `SKULL-04.5`.
- `SKULL-04.5` est validée : `runtime_factory.py` sélectionne un bundle commun
  de six adaptateurs, exige un fournisseur explicite d’adaptateurs réels en
  production et refuse tout fallback simulé. Le mode validé est visible via
  `/health/ready`; le service et le lanceur de production refusent
  `SKULL_HARDWARE_MODE=simulated`. 66 tests passent localement, sans démarrage
  matériel réel ni déploiement.
- `SKULL-05.1` est validée : le relevé live du 3 septembre 2026 confirme les
  deux services actifs et quatre processus Flask au total, avec reloader
  (`servo-sync.service` : PID 727/796 ; `playlist-web.service` : PID 703/762).
  Les deux processus du service principal détiennent `/dev/i2c-1` et ouvrent
  UDP `127.0.0.1:5005`; deux clients Python PulseAudio sont observés. La cause
  est identifiée dans `web_app.py:3158` et `playlist_web.py:335` (`debug=True`),
  combinée aux constructions matérielles au niveau module
  (`web_app.py:74-75`, `sync_player.py:39`, `gaze_receiver.py:65-66`,
  `loop_player.py:81-84`). Aucun redémarrage ni changement distant n’a été
  effectué. Preuve : `evidence/SKULL-05.1/RESULT.md`.
- `SKULL-05.2` est validée localement dans le worktree de production :
  `web_app.py` initialise le runtime une seule fois après validation du mode,
  sans construction matérielle à l’import ; `main()` impose
  `debug=False`/`use_reloader=False`, un verrou de fichier borné protège
  l’initialisation production, et `SyncPlayer.cleanup()`/`cleanup_runtime()`
  sont idempotents. Les tests dédiés et la suite complète passent (`70
  passed`). Aucun déploiement ou redémarrage Raspberry n’a été effectué ; la
  preuve est dans `evidence/SKULL-05.2/RESULT.md`.
- `SKULL-05.3` est validée localement : Gunicorn `22.0.0` est verrouillé dans
  les deux ensembles de dépendances, `gunicorn.conf.py` impose un worker, un
  thread et aucun préchargement, et `launch_wsgi.sh` fournit la commande
  candidate sur `127.0.0.1:5002`. Le smoke test Linux en mode simulé répond à
  `/health/live` et montre un master avec un seul worker ; en mode simulé,
  `/health/ready` reste correctement à 503 tant que le runtime matériel n’est
  pas initialisé. Les hooks d’arrêt appellent le cleanup idempotent. 74 tests
  passent. Aucun déploiement ou redémarrage Raspberry n’a été effectué ; preuve dans
  `evidence/SKULL-05.3/RESULT.md`.
- `SKULL-05.4` est validée localement : `/health/live` répond 200 sans lancer
  le runtime, tandis que `/health/ready` répond 503 à froid ou si la
  configuration/composant est invalide, puis 200 après initialisation complète.
  Les réponses sont limitées à `status`, `version`, `mode` et `checks`, sans
  secret, chemin privé ni effet de bord. 78 tests passent. Aucun déploiement ou
  redémarrage Raspberry n’a été effectué ; preuve dans
  `evidence/SKULL-05.4/RESULT.md`.
- `SKULL-05.5` est validée localement : les appels HTTP et commandes
  applicatives sont bornés par timeout et couverts par un garde-fou AST ; les
  scénarios serveur muet, DNS indisponible et commande suspendue sont simulés.
  Le logger est rotatif (10 MiB, 5 sauvegardes), les statistiques sont retenues
  sur 100 sessions et une panne du répertoire de logs bascule vers stderr.
  `ExecStartPre` ne connecte plus le Bluetooth, et les erreurs webhook/ESP32/
  playlist sont contrôlées sans URL ou secret. 86 tests passent. Aucun
  déploiement ou redémarrage Raspberry n’a été effectué ; preuve dans
  `evidence/SKULL-05.5/RESULT.md`.
- `SKULL-05.6` est validée localement : l’unité candidate d’exemple vise
  `/opt/skull-candidate`, `127.0.0.1:5002` et le mode simulé, sans section
  `[Install]` ni activation automatique. Les 21 cas legacy sont comparés aux
  snapshots gelés sur méthode, statut, content-type, clés et types ; les
  champs volatils sont explicitement listés. Le smoke Docker Linux a répondu
  `GET /health/live` en 200 avec un master et un worker, puis s’est arrêté.
  89 tests passent. Aucun venv, service, port ou fichier du Raspberry n’a été
  créé ou modifié ; preuve dans `evidence/SKULL-05.6/RESULT.md`.
- `SKULL-05.7` est validée : la candidate a été transférée sous
  `/opt/skull-candidate`, le flux `/logs/stream` est borné à une fenêtre SSE de
  0,5 seconde avec reconnexion native `EventSource`, puis le runtime candidate
  a été démarré en mode réel sur le port historique avec un master et un worker
  Gunicorn. Les healthchecks, routes legacy et passerelles de lecture ont
  répondu ; les requêtes invalides de lecture ont été rejetées sans déclenchement.
  Le rollback de la première tentative a été exécuté et la candidate corrigée
  est maintenant active ; `servo-sync.service` est inactive, l’unité historique
  n’a pas été modifiée, et `playlist-web.service` reste actif. Preuve dans
  `evidence/SKULL-05.7/RESULT.md`. Les essais physiques de servo, audio, bouton,
  sonnette et fumée restent réservés à la phase de validation matérielle.
- `SKULL-06.1` est validée localement : le package pur `domain/` fournit les
  types immuables de session, timeline, playlist et état de lecture, ainsi que
  les erreurs métier distinctes. Les validations existantes utilisent ces
  erreurs sans changer les réponses HTTP legacy ; 94 tests passent. Aucun
  déploiement, accès distant ou accès matériel n’a été effectué. Preuve dans
  `evidence/SKULL-06.1/RESULT.md`.
- `SKULL-06.2` est validée localement : `domain/session_catalog.py` centralise
  la découverte des répertoires, l’ordre stable, la sélection des fichiers et
  les diagnostics des sessions absentes ou invalides. Les dossiers incomplets
  restent visibles, les doublons ne sont pas supprimés et les opérations de
  lecture reçoivent des erreurs déterministes. Les tests legacy restent verts
  (`100 passed`). Aucun déploiement, accès distant ou accès matériel n’a été
  effectué. Preuve dans `evidence/SKULL-06.2/RESULT.md`.
- `SKULL-06.3` est validée localement : `domain/timeline.py` porte désormais
  le parsing, la validation, la normalisation et l’interpolation des quatre
  formats de timeline. Les événements simultanés, la fréquence 60 Hz, les
  mappings, offsets et arrondis de référence sont conservés ; les erreurs sont
  indexées sans divulgation de contenu. Neuf fixtures sont équivalentes au
  commit de référence et 109 tests passent. Aucun déploiement, accès distant
  ou accès matériel n’a été effectué. Preuve dans
  `evidence/SKULL-06.3/RESULT.md`.
- `SKULL-06.4` est validée localement : `domain/playlist.py` porte la file
  thread-safe, l’état courant, la sélection aléatoire injectable et une
  persistance JSON atomique optionnelle. Les identifiants restent uniques, les
  écritures échouées conservent le fichier précédent et les routes legacy
  restent inchangées ; 116 tests passent. La persistance n’est pas activée dans
  le runtime candidat. Aucun déploiement, accès distant ou accès matériel n’a
  été effectué. Preuve dans `evidence/SKULL-06.4/RESULT.md`.
- `SKULL-06.5` est validée localement : `domain/state_machine.py` centralise
  les transitions de lecture et leurs effets déclarés, sous verrou unique.
  `SyncPlayer` conserve les statuts legacy, interrompt ses attentes sur stop,
  joint son worker sans délai borné et arrête l’audio avant la remise en
  sécurité en cas d’erreur. Les transitions interdites, la concurrence, le
  stop idempotent, l’erreur sûre et l’absence de worker orphelin sont testés ;
  190 tests passent. Aucun déploiement, accès distant ou accès matériel n’a
  été effectué. Preuve dans `evidence/SKULL-06.5/RESULT.md`.
- `SKULL-06.6` est validée localement : `adapters_runtime.py` enveloppe les
  frontières PCA9685, audio, Bluetooth, ESP32, fumée et gaze sans import
  matériel au chargement ; les erreurs techniques sont traduites en erreurs
  métier stables. `services/playback.py` reçoit ses dépendances par
  constructeur, et les tests couvrent les pannes indépendantes, le parsing
  `bluetoothctl`, le JSON HTTP et l’absence de fallback implicite ; 202 tests
  passent. Le recâblage des routes legacy est réservé à `SKULL-06.7` ; aucun
  déploiement, accès distant ou accès matériel n’a été effectué. Preuve dans
  `evidence/SKULL-06.6/RESULT.md`.
- `SKULL-06.7` est validée localement : toutes les routes historiques sont
  enregistrées par le blueprint `api/legacy.py`, sans changement de chemin,
  méthode ou schéma JSON. Les contrôles de lecture passent par
  `LegacyPlaybackService`, et la matrice contractuelle legacy reste verte ;
  208 tests passent. Aucun bouton, sonnette, client ou matériel n’a été
  modifié ou sollicité. Preuve dans `evidence/SKULL-06.7/RESULT.md`.
- `SKULL-06.8` est validée localement : `api/v1.py` expose quatre routes de
  lecture sous `/api/v1`, avec enveloppe `ok/data` ou `ok/error`, validation
  bornée des noms de session et du paramètre `limit`, erreurs génériques et
  filtrage des champs sensibles. `tests/contracts/API-V1.md` documente les
  routes et la correspondance legacy/v1 ; les clients, boutons, sonnette et
  équipements restent inchangés. La suite complète compte 212 tests verts,
  sans accès distant, matériel ou réseau réel. Preuve dans
  `evidence/SKULL-06.8/RESULT.md`.
- `SKULL-07.1` est validée localement : `domain/bluetooth.py` définit un état
  explicite avec validation MAC stricte, propriétés BlueZ et UUID séparés,
  déduction A2DP par UUID uniquement, et distinction entre information
  inconnue et erreur temporaire. Les fixtures JBL Quantum 360, SoundLink Mini
  et BLE non audio passent ; l’adaptateur runtime ne déclare aucun
  `pulse_sink` sans preuve PulseAudio. Aucun scan, appairage, connexion,
  changement de sink ou accès matériel n’a été effectué. Preuve dans
  `evidence/SKULL-07.1/RESULT.md`.
- `SKULL-07.2` est validée localement : `services/bluetooth_commands.py`
  centralise l’exécution interactive sans shell, avec liste d’arguments,
  timeout, normalisation/rédaction des sorties et verrou partagé. La façade
  legacy et `BluetoothctlAdapter` valident les MAC strictement ; scans et
  appairages multi-commandes sont sérialisés. Les tests couvrent injection,
  timeout, sortie sensible et concurrence ; aucun accès Bluetooth réel n’a
  été effectué. Le travail parallèle de la phase 8 n’a pas été modifié. Preuve
  dans `evidence/SKULL-07.2/RESULT.md`.
- `SKULL-07.3` est validée localement : l’IHM utilise une surface dédiée pour
  scan, appairage, confiance, connexion, sélection de sortie et test audio.
  Les états sont affichés séparément, les transitions pair/trust/connect ne
  sont pas enchaînées, les opérations sont idempotentes et chaque réponse
  rafraîchit l’état sans sortie technique brute. La sélection PulseAudio et le
  son réel restent réservés aux tâches suivantes ; aucun accès distant ou
  matériel n’a été effectué. Le travail parallèle de la phase 8 a été préservé.
  Preuve dans `evidence/SKULL-07.3/RESULT.md`.
- `SKULL-07.4` est validée localement : `PulseAudioOutputAdapter` sélectionne
  le profil A2DP puis un sink Bluetooth identifié par son nom stable, attend
  son apparition de manière bornée et vérifie qu’il est le sink par défaut et
  non suspendu. Le profil Audio Sink est une preuve distincte de `connected` ;
  aucun volume/mute n’est modifié. Le fallback local est désactivé par défaut
  et son emploi est signalé. Les tests passent (`239 passed`) sans commande
  `pactl` réelle, accès distant ou lecture audio ; le travail parallèle de la
  phase 8 a été préservé. Preuve dans `evidence/SKULL-07.4/RESULT.md`.
- `SKULL-07.5` est validée localement : `BluetoothReconnectController` lit
  seulement l’adresse configurée, refuse les appareils non trusted, limite les
  tentatives, applique un backoff progressif et interrompt l’attente à l’arrêt.
  Aucun scan ni appairage automatique n’est lancé ; `connected` reste séparé
  de `audio_ready`. La suite compte `245 passed`, sans accès distant ou
  matériel réel ; le travail parallèle de la phase 8 a été préservé. Preuve
  dans `evidence/SKULL-07.5/RESULT.md`.
- `SKULL-07.6` est validée localement : les scénarios simulés couvrent scan
  vide, JBL A2DP, BLE non audio, refus d’appairage, connexion sans sink, sink
  retardé, disparition pendant lecture, timeout, reconnexion et arrêt pendant
  attente. Les délais utilisent `SimulatedClock` sans attente réelle ; la
  suite compte `255 passed`, sans accès distant, matériel ou Bluetooth réel.
  Le travail parallèle de la phase 8 a été préservé. Preuve dans
  `evidence/SKULL-07.6/RESULT.md`.

## Reprise lors d’une prochaine session

1. Lire `OBJECTIF.md`.
2. Lire `LUNA.md` et ne confier qu’un identifiant `SKULL-XX.Y` à la fois.
3. Lire la section « Prochaine action » de `TODO.md`.
4. Lire `OPERATIONS.md` avant toute connexion au Raspberry.
5. Vérifier `git status` dans les trois worktrees sans rien réinitialiser ;
   identifier explicitement celui qui contient la tâche confiée.
6. Pour `SKULL-08.6`, se placer dans
   `C:\Users\cedri\Documents\Codex\Skull-V2-phase8-2026`, lire entièrement
   `tasks/08-CONFIGURATION.md`, puis les preuves `SKULL-08.6` et `SKULL-08.7`.
7. Exécuter la suite de tests uniquement dans le worktree phase 8 ; ne pas
   interpréter les zéro test du dépôt de pilotage comme une validation.
8. Vérifier les services et `/status` sans lancer de session ; confirmer que la
   candidate est le propriétaire attendu du port 5000 avant toute décision.
9. Commencer par l'unique identifiant indiqué dans `TODO.md`. Demander
   confirmation avant toute écriture distante, changement réseau, sauvegarde
   avec arrêt ou intervention matérielle.
