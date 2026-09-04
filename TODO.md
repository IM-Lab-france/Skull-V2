# TODO — modernisation du Skull principal

## Légende

- `[x]` terminé et observé ;
- `[ ]` à faire ;
- `[~]` partiellement réalisé, annulé ou en attente d'une condition explicitée ;
- `VALIDATION` signifie qu’une preuve est obligatoire avant de continuer ;
- `CONFIRMATION` signifie qu’une action peut toucher la production ou le
  matériel.

## 0. Reprise et compréhension — terminé

Détails et preuves attendues : [tasks/00-REPRISE.md](tasks/00-REPRISE.md).

- [x] Localiser le Raspberry Skull sur le réseau legacy : `192.168.1.116`.
- [x] Établir un accès SSH par clé pour le compte `skull`.
- [x] Vérifier l’accès administrateur via `sudo`.
- [x] Inventorier OS, stockage, mémoire, services et ports.
- [x] Vérifier `servo-sync.service` et `playlist-web.service`.
- [x] Vérifier la présence d’I²C, GPIO et PulseAudio.
- [x] Inventorier les sessions et la configuration active.
- [x] Cartographier Skull, boutons, sonnette et fumée.
- [x] Rédiger `OPERATIONS.md`.
- [x] Rédiger `OBJECTIF.md`, `TODO.md` et `MEMOIRE.md`.
- [x] Appairer et configurer la Bose SoundLink Mini II comme sortie audio
  actuelle.

## 1. Geler et sauvegarder la production — priorité immédiate

Exécution atomique : [tasks/01-SAUVEGARDE.md](tasks/01-SAUVEGARDE.md).

- [ ] `CONFIRMATION` Arrêter une fenêtre de maintenance.
- [x] Archiver `/opt/skull/data` et `/opt/skull/config` — `SKULL-01.3` validée.
- [ ] Sauvegarder les unités systemd réellement installées.
- [ ] Exporter le diff Git complet de `/opt/skull`.
- [ ] Exporter la liste exacte des dépendances des deux venv.
- [ ] Relever les versions système, Python, BlueZ et PulseAudio.
- [ ] Créer un manifeste des sessions avec tailles et checksums.
- [x] Copier les sauvegardes hors du Raspberry — `SKULL-01.4` validée.
- [x] Vérifier les checksums après copie — `SKULL-01.4` validée.
- [x] Restaurer l’archive dans un répertoire temporaire — `SKULL-01.4` validée.
- [x] Évaluer puis réaliser une image de sauvegarde de la carte SD —
  `SKULL-01.5` validée : image VHDX Rufus créée sur `D:`, taille et SHA-256
  consignés dans `evidence/SKULL-01.5/` ; restauration non testée.
- [x] `VALIDATION` Produire une preuve de restauration exploitable —
  `SKULL-01.4` validée.

## 2. Reconstruire la source de vérité

Exécution atomique :
[tasks/02-SOURCE-DE-VERITE.md](tasks/02-SOURCE-DE-VERITE.md).

- [x] Créer la branche `codex/production-skull-2026` et son worktree isolé —
  `SKULL-02.1` validée.
- [x] Importer les fichiers modifiés présents sur le Raspberry dans le
  worktree isolé — `SKULL-02.2` validée ; inventaire dans
  `evidence/SKULL-02.2/DIFF-INVENTORY.md`.
- [x] Comparer production, `main` local et `origin/main` — `SKULL-02.5`
  validée ; `main` et `origin/main` sont alignés et les empreintes de la
  branche isolée sont conservées dans `evidence/SKULL-02.5/`.
- [x] Documenter l’origine de chaque différence — inventaire dans
  `evidence/SKULL-02.2/DIFF-INVENTORY.md` et classification SHA-256 dans
  `evidence/SKULL-02.5/SHA256-COMPARISON.tsv`.
- [ ] Normaliser les fins de ligne sans changement fonctionnel — reporté : les
  avertissements sont documentés, aucune normalisation automatique n’a été
  appliquée.
- [x] Ajouter les fichiers de configuration exemples sans secrets —
  `SKULL-02.4` validée.
- [x] Versionner et valider les dépendances Python de référence — `SKULL-02.3`
  validée : fichiers directs, locks régénérés, dépendances système documentées
  et installation/imports vérifiés dans un conteneur Python 3.11 ARM64.
- [x] Créer les exemples de configuration et le contrôle anti-secret —
  `SKULL-02.4` validée : schémas JSON, environnement Bluetooth neutre,
  exclusions Git et tests automatiques ajoutés.
- [ ] Sortir définitivement venv, logs, cache et données du suivi Git.
- [ ] Définir où seront sauvegardés les contenus audio hors Git.
- [ ] `VALIDATION` Recréer les environnements depuis un clone neuf.

## 3. Construire les tests de caractérisation

Exécution atomique :
[tasks/03-CARACTERISATION.md](tasks/03-CARACTERISATION.md).

- [x] Ajouter pytest et une structure de tests — `SKULL-03.1` validée :
  dépendance de développement séparée, collecte déterministe, répertoires
  `unit`, `contract`, `fixtures` et sentinelle anti-mode production.
- [x] Tester chaque format de timeline accepté — `SKULL-03.2` validée : quatre
  racines, cas limites, erreurs attendues et comportements mécaniques à risque
  figés dans les fixtures et tests locaux.
- [x] Tester la détection des sessions — `SKULL-03.3` validée : présence des
  MP3/JSON, caches WAV, multi-fichiers, noms Unicode et traversée de chemin
  caractérisés sans données de production.
- [ ] Tester l’interpolation à 60 Hz.
- [ ] Tester les limites et offsets sans matériel.
- [x] Tester la détection MP3/JSON des sessions — couvert par `SKULL-03.3` ;
  les placeholders restent synthétiques et hors Git de production.
- [x] Figer les réponses JSON des routes legacy — `SKULL-03.4` validée :
  statuts, content-types, clés et types testés localement avec adaptateurs
  simulés ; carte des routes dans `tests/contracts/HTTP-MAP.md`.
- [x] Tester playlist, état de lecture et erreurs de démarrage — `SKULL-03.5`
  validée : transitions, concurrence, skip/stop, suppression, aléatoire et
  erreurs audio/Bluetooth caractérisés ; tableau dans `evidence/SKULL-03.5/`.
- [ ] Tester play, pause, resume, stop et fin de piste.
- [ ] Tester ajout, déplacement, suppression et skip de playlist.
- [ ] Tester catégories, mode aléatoire et exclusion de `Accueil`.
- [ ] Figer les réponses JSON des routes legacy.
- [x] Tester le webhook fumée uniquement pour `Accueil` — `SKULL-03.6`
  validée : POST local, casse, timeout et statuts d’erreur caractérisés.
- [x] Tester les indisponibilités Bluetooth, ESP32 et domotique — couvert par
  `SKULL-03.5` et `SKULL-03.6` avec adaptateurs factices.
- [ ] `VALIDATION` Exécuter les tests sur Windows et Linux.

## 4. Ajouter le mode matériel simulé

Exécution atomique : [tasks/04-SIMULATION.md](tasks/04-SIMULATION.md).

- [x] Définir l’interface commune des adaptateurs matériels — `SKULL-04.1` validée.
- [x] Créer un faux PCA9685 qui journalise les commandes — `SKULL-04.2` validée.
- [x] Créer un faux lecteur audio avec horloge contrôlée — `SKULL-04.3` validée.
- [x] Créer de faux adaptateurs BlueZ/PulseAudio, ESP32 et fumée — `SKULL-04.4` validée.
- [x] Créer la factory centrale et le bundle commun d’adaptateurs — `SKULL-04.5` validée.
- [x] Refuser le mode simulé dans le service/lanceur de production.
- [x] Exposer le mode validé via `/health/ready`.
- [x] Interdire tout accès I²C/GPIO dans le profil de test.
- [x] Comparer les commandes simulées aux traces de référence.
- [ ] `VALIDATION` Démontrer qu’aucun test ne peut déplacer un servo.

## 5. Stabiliser le runtime sans changement fonctionnel

Exécution atomique : [tasks/05-RUNTIME.md](tasks/05-RUNTIME.md).

`SKULL-05.1` est validée : collecte live `systemctl`, processus, sockets, I²C
et audio terminée sur le Raspberry ; preuve dans
`evidence/SKULL-05.1/RESULT.md`. Le reloader Flask crée actuellement deux
processus par application et deux propriétaires de `/dev/i2c-1`. Les étapes
locales `SKULL-05.2` à `SKULL-05.6` sont maintenant validées ; `SKULL-05.7`
a été tentée puis annulée par rollback.

- [x] Désactiver Flask `debug=True` et son reloader — `SKULL-05.2` validée
  localement ; production non déployée.
- [x] Garantir un seul processus possédant le matériel — initialisation unique,
  verrou borné et cleanup idempotent validés localement par tests.
- [x] Choisir un serveur WSGI à un worker — Gunicorn, configuration à un worker
  et smoke test Linux simulé validés par `SKULL-05.3`.
- [x] Ajouter `/health/live` et `/health/ready` — contrats 200/503, mode public
  et absence d’effets de bord validés par `SKULL-05.4`.
- [x] Ajouter une rotation et une rétention des logs — `SKULL-05.5` validée
  localement : 10 MiB + 5 rotations et 100 stats par défaut, permissions
  `0750`/`0640`, secours si le stockage est indisponible.
- [x] Borner tous les appels réseau par timeout — `SKULL-05.5` validée
  localement par inventaire AST et scénarios d’indisponibilité.
- [x] Rendre le démarrage Bluetooth non bloquant — `SKULL-05.5` validée
  localement : suppression de la connexion dans `ExecStartPre`.
- [x] Afficher les erreurs sans révéler de secret — `SKULL-05.5` validée
  localement : webhook, erreurs ESP32 et playlist contrôlés.
- [x] Déployer et vérifier la candidate sur le Raspberry — `SKULL-05.7`
  validée : candidate Gunicorn active sur 5000, healthchecks et routes legacy
  vérifiés, flux `/logs/stream` borné et rollback testé. Preuve :
  `evidence/SKULL-05.7/RESULT.md`.
- [x] Préparer une unité systemd parallèle pour validation — `SKULL-05.6`
  validée localement : chemin distinct, mode simulé, port loopback et aucune
  activation automatique.
- [x] Comparer les réponses ancienne/nouvelle version — `SKULL-05.6` validée
  localement contre les snapshots de contrats legacy ; champs volatils listés.
- [ ] `VALIDATION` Boutons et sonnette fonctionnent sans modification.

## 6. Découper l’application

Exécution atomique : [tasks/06-REFACTORING.md](tasks/06-REFACTORING.md).

- [x] Extraire les types et erreurs du domaine — `SKULL-06.1` validée :
  package pur importable sous Windows, erreurs compatibles avec la façade
  legacy et 94 tests de caractérisation verts.
- [x] Extraire le catalogue et la validation des sessions — `SKULL-06.2`
  validée : découverte indépendante de Flask, ordre stable, inspection des
  fichiers et 100 tests de caractérisation verts.
- [x] Extraire le parseur et l’interpolation des timelines — `SKULL-06.3`
  validée : quatre formats conservés, erreurs indexées, traces identiques à la
  référence et 109 tests de caractérisation verts.
- [x] Extraire l’état de lecture et la playlist — `SKULL-06.4` validée : file
  thread-safe, randomisation injectable, invariants d’identifiants et
  persistance atomique optionnelle ; 116 tests de caractérisation verts.
- [x] Créer une machine à états explicite — `SKULL-06.5` validée localement :
  table complète des transitions, verrou unique, arrêt idempotent, sortie
  sûre sur erreur et worker interruptible ; 190 tests verts.
- [x] Extraire les adaptateurs PCA9685, audio, Bluetooth, ESP32, fumée et gaze —
  `SKULL-06.6` validée localement : wrappers injectables, erreurs métier
  stables, parsing Bluetooth/JSON HTTP isolé et service de lecture injecté ;
  202 tests verts.
- [x] Conserver les routes legacy comme façade de compatibilité — `SKULL-06.7`
  validée localement : blueprint dédié, service de lecture utilisé par les
  contrôles legacy et matrice HTTP inchangée ; 208 tests verts.
- [x] Ajouter une API `/api/v1` versionnée — `SKULL-06.8` validée localement :
  quatre routes de lecture, enveloppe JSON commune, validation des entrées,
  erreurs génériques et table de correspondance legacy/v1 ; aucun client ni
  équipement n’a été migré.
- [x] `VALIDATION` Tous les tests de caractérisation restent verts — 212 tests
  passent, avec un avertissement externe connu de `pydub`/`audioop`.

## 7. Fiabiliser Bluetooth et audio

Exécution atomique :
[tasks/07-BLUETOOTH-AUDIO.md](tasks/07-BLUETOOTH-AUDIO.md).

- [x] Distinguer clairement scan, appairage, confiance, connexion et A2DP —
  `SKULL-07.1` validée localement : modèle d’état explicite, UUID A2DP
  séparés des propriétés BlueZ et `pulse_sink` non déduit de `connected`.
- [x] Sécuriser l’exécution des commandes Bluetooth — `SKULL-07.2` validée
  localement : exécuteur commun sans shell, timeout, sortie normalisée,
  erreurs rédigées, validation MAC et verrou contre les scans/appairages
  concurrents.
- [x] Séparer les opérations Bluetooth de l’IHM — `SKULL-07.3` validée
  localement : routes explicites scan/pair/trust/connect/select-output/test-audio,
  états indépendants, rafraîchissement après succès ou échec et erreurs
  rédigées sans sortie brute. Preuve dans
  `evidence/SKULL-07.3/RESULT.md`.
- [x] Refuser les périphériques BLE sans profil `Audio Sink` — sélection
  PulseAudio bloquée si le UUID Audio Sink n’est pas prouvé ; validé localement
  dans `SKULL-07.4`.
- [x] Sélectionner explicitement le sink PulseAudio — profil A2DP, nom stable,
  sink par défaut et état non suspendu vérifiés localement dans `SKULL-07.4`.
- [x] Ajouter une sortie audio locale de secours configurable — désactivée par
  défaut et signalée explicitement lorsqu’elle est utilisée ; `SKULL-07.4`.
- [x] Préparer une reconnexion contrôlée — adresse configurée uniquement,
  `trusted` obligatoire, tentatives bornées, backoff progressif et annulation
  interruptible ; `SKULL-07.5` validée localement.
- [x] Couvrir les scénarios logiciels Bluetooth/audio — scan vide, A2DP, BLE
  non audio, refus, sink retardé ou absent, disparition, timeout, reconnexion
  et arrêt pendant attente ; `SKULL-07.6` validée localement.
- [x] Découpler la reconnexion Bluetooth de l’IHM — `SKULL-07.8` validée :
  worker autonome, état non bloquant publié à l’IHM, concurrence et
  annulation couvertes, 266 tests passés, candidate active au boot et service
  legacy désactivé.
- [x] Découpler et temporiser la supervision ESP32 — `SKULL-07.9` validée :
  état cache pour `/esp32/status`, contrôle manuel séparé, superviseur unique,
  backoff, circuit breaker, sérialisation, annulation et 269 tests passés.
  Le polling réel reste désactivé tant que la configuration ESP32 n’est pas
  activée explicitement.
- [x] Tester extinction/rallumage de la Bose SoundLink Mini II — trois cycles
  validés.
- [x] Tester reconnexion après redémarrage du Raspberry — la candidate est
  activée au boot, `servo-sync.service` désactivé, et les healthchecks ainsi
  que la reconnexion Bose ont été vérifiés après reboot.
- [x] Tester une lecture à faible volume — émission de 3 secondes entendue par
  l’utilisateur, trois bips confirmés.
- [x] `VALIDATION` Démontrer une reconnexion autonome reproductible — candidate
  active après reboot, Bose reconnectée et audio A2DP disponible.

## 8. Centraliser configuration et secrets

Exécution atomique :
[tasks/08-CONFIGURATION.md](tasks/08-CONFIGURATION.md).

État de référence : les travaux de cette phase sont dans le worktree
`C:\Users\cedri\Documents\Codex\Skull-V2-phase8-2026`, branche
`codex/phase8-skull-2026`. Ils ne sont pas encore intégrés à `main`.

- [x] Créer une configuration typée et validée au démarrage — schéma, précédence
  et tests disponibles dans le worktree phase 8.
- [~] Importer automatiquement les anciens JSON et `.env` — convertisseur et
  fixtures validés localement ; la migration de toutes les données réelles reste
  à comparer avant clôture de `SKULL-08.4`.
- [~] Sortir le webhook fumée du code source — la cible a été analysée ; la
  liaison événement → action est désormais reportée à la phase 13.
- [~] Remplacer le secret du webhook actuel — `SKULL-08.5` annulée le
  4 septembre 2026 : aucune rotation ni modification de la sonnette, car le
  webhook observé ne pilote pas la fumée attendue.
- [~] Remplacer progressivement les IP codées en dur par du DNS interne —
  `skull.home.arpa` est validé ; les autres dépendances et le comportement de
  panne DNS restent à clôturer dans `SKULL-08.6`.
- [~] Séparer code, configuration, données et logs — TOML et permissions sont
  déployés sur la candidate ; `/opt/skull/current` et la séparation par release
  restent en phase 10.
- [x] `VALIDATION` Démarrer avec ancienne puis nouvelle configuration —
  `SKULL-08.7` validée sur la candidate port 5000 ; healthchecks 200 et
  rollback disponible.

## 9. Sécuriser les API

Exécution atomique : [tasks/09-SECURITE.md](tasks/09-SECURITE.md).

- [ ] Séparer routes publiques et routes d’administration.
- [ ] Protéger suppression, restart, Bluetooth, pitch et upload.
- [ ] Restreindre les routes legacy aux sources autorisées.
- [ ] Ajouter une identité technique pour boutons et sonnette.
- [ ] Limiter CORS.
- [ ] Définir le comportement si la domotique est inaccessible.
- [ ] `VALIDATION` Prouver que les ports et routes non autorisés sont refusés.

## 10. Déployer par releases

Exécution atomique : [tasks/10-RELEASES.md](tasks/10-RELEASES.md).

- [ ] Créer `/opt/skull/releases/<version>`.
- [ ] Séparer `/var/lib/skull`, `/etc/skull` et `/var/log/skull`.
- [ ] Créer le lien atomique `/opt/skull/current`.
- [ ] Ajouter préflight et healthchecks de déploiement.
- [ ] Automatiser la bascule vers la release précédente.
- [ ] Tester un échec volontaire et son rollback.
- [ ] `VALIDATION` Démontrer un rollback complet.

## 11. Préparer la migration IoT

Exécution atomique : [tasks/11-RESEAU-IOT.md](tasks/11-RESEAU-IOT.md).

- [x] Réserver l'adresse Skull et son nom DNS — `192.168.40.20` et
  `skull.home.arpa`, preuve `SKULL-11.5`.
- [x] Définir et appliquer les ACL minimales Skull — gestion vers 22/5000/5050,
  Skull vers Home Assistant 8123, DNS/NTP dédiés ; preuve `SKULL-11.5`.
- [x] Autoriser une coexistence temporaire legacy/IoT — profil legacy conservé
  et rollback documenté ; preuve `SKULL-11.5`.
- [~] Migrer le Skull avant les émetteurs — `SKULL-11.5` est PARTIEL : Skull
  est sur le VLAN 40 et administrable, mais la continuité des clients legacy
  n'est pas encore prouvée de bout en bout.
- [ ] Migrer ensuite l’ESP32 boutons.
- [ ] Migrer la sonnette.
- [ ] Migrer le webhook fumée/domotique.
- [ ] Harmoniser les 5 boutons firmware avec les 3 affectations serveur.
- [ ] Retirer les règles legacy seulement après validation.
- [ ] `VALIDATION` Tester chaque flux et chaque refus attendu.

## 13. Nouvelles fonctionnalités — événements et actions

Exécution atomique : [tasks/13-ACTIONS-EVENEMENTS.md](tasks/13-ACTIONS-EVENEMENTS.md).

- [ ] `SKULL-13.1` Définir un modèle configurable événement → conditions →
  actions, validé et journalisé sans secret.
- [ ] `SKULL-13.2` Configurer les liaisons d'événements, sans reconfigurer la
  sonnette existante.
- [ ] `SKULL-13.3` Tester en simulation succès, erreurs, délais, reprises et
  absence de boucle infinie avant tout effet matériel.
- [ ] `VALIDATION` Démontrer une action configurée depuis un événement réel
  après approbation et recette matérielle.

## 12. Validation matérielle finale

Exécution atomique :
[tasks/12-VALIDATION-MATERIELLE.md](tasks/12-VALIDATION-MATERIELLE.md).

- [ ] `CONFIRMATION` Préparer une zone dégagée et un arrêt électrique.
- [ ] Tester le healthcheck sans mouvement.
- [ ] Tester l’audio seul à faible volume.
- [ ] Tester chaque servo autour du neutre.
- [ ] Tester une timeline courte connue.
- [ ] Tester un bouton physique.
- [ ] Tester la sonnette.
- [ ] Tester `Accueil` et la fumée en conditions sécurisées.
- [ ] Tester coupure réseau et reprise.
- [ ] Tester redémarrage Raspberry.
- [ ] Tester rollback de release.
- [ ] `VALIDATION` Signer le procès-verbal de remise en service.

## Prochaine action

Avant toute nouvelle implémentation, traiter `SKULL-08.6` dans le worktree
`C:\Users\cedri\Documents\Codex\Skull-V2-phase8-2026` : compléter la preuve
DNS (dépendances restantes, sources autorisées, pannes bornées), puis décider
explicitement de clôturer ou de conserver la phase PARTIELLE. Ne pas commencer
la phase 9 avant cette décision, ni fusionner le worktree phase 8 dans `main`
sans revue dédiée : il contient 234 fichiers et plus de 41 000 lignes de diff.

La candidate actuellement en service est associée aux branches de travail et
non au `main` local. Toute intervention distante exige le préflight de
`LUNA.md`, une confirmation pour une écriture, et une vérification que
`skull-candidate.service` reste le seul propriétaire du port 5000. Pour Luna,
ne confier qu'un identifiant à la fois.
