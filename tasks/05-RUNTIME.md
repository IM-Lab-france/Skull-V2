# Phase 05 — stabiliser le runtime

## But et règle de sécurité

Cette phase change la manière de lancer l’application, pas son comportement
fonctionnel. Elle ne commence qu’après les tests de caractérisation et le mode
simulé. Toute installation ou bascule sur le Raspberry exige une confirmation.

## SKULL-05.1 — mesurer le runtime actuel

### Préconditions

- sauvegarde de phase 01 vérifiée ;
- accès SSH en lecture seule ;
- aucun redémarrage de service pendant la collecte.

### Étapes

1. Relever `systemctl cat`, `systemctl show` et `systemctl status` pour
   `servo-sync.service` et `playlist-web.service`.
2. Relever l’arbre de processus avec PID, PPID, commande, utilisateur et nombre
   de threads.
3. Identifier le propriétaire des ports avec `ss -lntup`.
4. Rechercher `debug=True`, `use_reloader`, `app.run` et les initialisations
   matérielles exécutées à l’import.
5. Redémarrer uniquement en fenêtre de maintenance confirmée, puis compter les
   processus et les ouvertures I²C/audio.
6. Enregistrer les résultats dans `evidence/SKULL-05.1/RESULT.md`.

### Acceptation

- le nombre réel de processus propriétaires du matériel est connu ;
- la cause d’un éventuel double démarrage est identifiée par fichier et ligne ;
- aucune hypothèse n’est présentée comme un fait observé.

## SKULL-05.2 — rendre le démarrage déterministe

### Fichiers ciblés

- point d’entrée Flask ;
- factory d’application si elle existe ;
- tests de démarrage.

### Étapes

1. Déplacer tout lancement derrière un point d’entrée explicite.
2. Mettre `debug=False` par défaut.
3. Interdire le reloader dans le profil matériel réel.
4. Initialiser les adaptateurs une seule fois, après validation de la
   configuration.
5. Installer un verrou de processus borné au service si deux processus peuvent
   encore ouvrir le PCA9685.
6. Garantir que `cleanup()` est idempotent et appelé lors d’un arrêt normal.
7. Tester deux tentatives d’initialisation simultanées en mode simulé.

### Acceptation

- un seul propriétaire des servos et de l’audio ;
- import du module sans lancer serveur, thread, audio ou I²C ;
- arrêt propre sans double neutralisation ni exception masquée.

## SKULL-05.3 — ajouter un serveur WSGI à un worker

### Décision imposée

Utiliser un seul worker en production tant que l’état matériel reste dans le
processus. Ne pas activer le préchargement ni plusieurs workers.

### Étapes

1. Ajouter le serveur WSGI aux dépendances verrouillées.
2. Créer une commande locale en mode simulé, par exemple avec un worker et un
   timeout documenté.
3. Vérifier que les signaux TERM et INT arrêtent les threads et libèrent les
   adaptateurs.
4. Vérifier que les requêtes longues n’entraînent pas un deuxième worker.
5. Documenter le choix des threads ; rester à un thread si l’état partagé n’est
   pas protégé.
6. Ajouter un test qui échoue si la configuration de production demande plus
   d’un worker.

### Acceptation

- commande de lancement reproductible ;
- un seul worker démontré par l’arbre de processus ;
- fermeture propre vérifiée en simulation.

## SKULL-05.4 — créer les healthchecks sans effet de bord

### Contrats

- `GET /health/live` retourne 200 si le processus HTTP répond ;
- `GET /health/ready` retourne 200 uniquement si configuration et adaptateurs
  obligatoires sont initialisés ; sinon 503 ;
- aucun healthcheck ne lance de session, ne bouge de servo, ne joue de son, ne
  scanne le Bluetooth et n’appelle un service externe.

### Réponse minimale

La réponse JSON contient `status`, `version`, `mode`, et un objet `checks`. Elle
ne contient ni secret, ni chemin privé, ni sortie brute de commande.

### Acceptation

- tests 200/503 couvrant chaque dépendance ;
- réponse en moins d’une seconde avec dépendances externes indisponibles ;
- `mode=simulated` ou `mode=real` visible sans ambiguïté.

## SKULL-05.5 — borner réseau, Bluetooth et logs

### Étapes

1. Inventorier tous les appels HTTP, commandes système et sockets.
2. Définir pour chacun un timeout de connexion et un timeout total.
3. Déporter l’initialisation Bluetooth hors du chemin critique de démarrage.
4. Transformer timeout et indisponibilité en erreurs métier contrôlées.
5. Ajouter une rotation des logs par taille ou via `logrotate`.
6. Fixer rétention, propriétaire et permissions.
7. Redacter URL de webhook, jetons et variables sensibles dans les exceptions.
8. Tester serveur muet, DNS invalide, commande suspendue et disque de logs
   indisponible.

### Acceptation

- aucun appel externe sans timeout ;
- l’application démarre même si l’enceinte est éteinte ;
- croissance maximale des logs documentée ;
- aucun secret dans les preuves de test.

## SKULL-05.6 — préparer une instance parallèle

### Confirmation requise

Création d’un venv, d’une unité systemd ou ouverture d’un port sur le Raspberry.

### Étapes

1. Installer la candidate dans un chemin distinct de `/opt/skull`.
2. Créer une unité `skull-candidate.service` sans activation automatique.
3. Utiliser un port temporaire, proposé `5002`, non exposé hors du réseau de
   test.
4. Démarrer d’abord en mode simulé si possible.
5. Capturer pour chaque route legacy : méthode, statut, `Content-Type`, schéma
   JSON et effets observables.
6. Comparer candidate et production en ignorant uniquement les champs volatils
   explicitement listés.
7. Arrêter et désactiver la candidate à la fin du test.

### Acceptation

- aucune concurrence d’accès au PCA9685 ou à l’audio ;
- matrice de comparaison complète ;
- unité candidate arrêtée après validation.

## SKULL-05.7 — basculer le runtime

### Confirmation requise

Arrêt de la production et démarrage de la candidate sur le port historique.

### Séquence

1. Vérifier sauvegarde, version candidate et commande de rollback.
2. Arrêter proprement l’ancien service.
3. Vérifier qu’aucun processus ne possède encore port, I²C ou audio.
4. Démarrer le nouveau service.
5. Vérifier live, ready, routes legacy, boutons et sonnette sans déclencher de
   mouvement non autorisé.
6. En cas d’échec, arrêter la candidate et restaurer immédiatement l’unité
   précédente.
7. Conserver logs et horodatage des deux tentatives.

### Acceptation

- un seul processus matériel après bascule ;
- compatibilité legacy démontrée ;
- rollback exécutable en moins de cinq minutes et testé.
