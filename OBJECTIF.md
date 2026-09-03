# Objectif — modernisation du Skull principal

## Finalité

Moderniser le logiciel du Raspberry Skull sans modifier sa mécanique de
fonctionnement et sans casser les équipements existants.

La cible doit conserver :

- les quatre servos et leur câblage PCA9685 actuel ;
- les canaux `jaw`, `eye_left`, `eye_right`, `neck_pan` ;
- les limites, offsets et positions neutres validés mécaniquement ;
- les sessions MP3 + JSON et leurs formats de timeline ;
- la playlist, les catégories, la boucle et le mode aléatoire ;
- les appels existants des boutons et de la sonnette ;
- le déclenchement de la fumée associé à la session `Accueil` ;
- les routes legacy nécessaires pendant la transition.

## Résultat attendu

Le Skull doit devenir :

- reproductible depuis une source Git de référence ;
- testable sans matériel grâce à des adaptateurs simulés ;
- exploitable avec un seul processus de contrôle matériel ;
- capable de diagnostiquer séparément Bluetooth, audio, servos et réseau ;
- sauvegardé et restaurable ;
- déployable par release avec rollback immédiat ;
- sécurisé avant son passage sur le réseau IoT ;
- documenté pour une reprise sans connaissance implicite.

## Contraintes non négociables

1. Pas de réécriture complète en une seule bascule.
2. Aucun mouvement pendant les tests logiciels.
3. Aucun changement de limite ou d’offset sans validation physique.
4. Compatibilité maintenue avec `/play`, `/api/enqueue`, `/api/sessions` et
   `/status` pendant la transition.
5. Les secrets restent hors du dépôt et de la documentation.
6. Une sauvegarde vérifiée précède toute mise à jour du Raspberry.
7. Chaque déploiement possède une validation et un retour arrière.
8. Le Raspberry de production n’est pas utilisé comme poste de développement.

## Périmètre du premier chantier

Le premier chantier concerne le Skull principal :

- code Python ;
- services systemd ;
- interface principale et playlist ;
- PCA9685, timelines et lecture audio ;
- Bluetooth/PulseAudio ;
- contrats HTTP avec boutons, sonnette et domotique ;
- données, configuration, logs et déploiement.

Les firmwares ESP32, la migration réseau IoT et le câblage physique ne seront
modifiés qu’après stabilisation du Skull et validation de leurs contrats.

## Critères de réussite

- la nouvelle version reproduit les réponses API legacy ;
- les sessions existantes sont toutes inventoriées et validées ;
- les commandes servo simulées correspondent à la version actuelle ;
- le démarrage ne provoque aucun mouvement inattendu ;
- Bluetooth se reconnecte après extinction et redémarrage ;
- boutons, sonnette et fumée fonctionnent sans modification pendant la première
  bascule ;
- les données et réglages survivent à une restauration ;
- un rollback vers la release précédente est démontré ;
- seuls les flux réseau nécessaires sont autorisés avant la migration IoT.

## Décision d’architecture

Le nouveau cœur sera indépendant de Flask, GPIO, Bluetooth et des adresses IP.
Ces dépendances seront placées derrière des adaptateurs. Les routes legacy
continueront d’appeler ce cœur, tandis qu’une API versionnée sera ajoutée pour
les évolutions futures.

