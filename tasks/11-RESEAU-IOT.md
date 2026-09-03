# Phase 11 — migrer du réseau legacy vers le réseau IoT

## Flux fonctionnels à préserver

| Source | Destination | Port/protocole | Usage |
|---|---|---:|---|
| boutons ESP32 | Skull | TCP 5000, HTTP legacy | commandes physiques |
| sonnette | Skull | TCP 5000, HTTP legacy | déclenchement de session |
| interface/playlist | Skull | TCP 5000, HTTP | pilotage et état |
| Skull | ESP32 boutons | TCP 80, HTTP | statut, relais, configuration |
| Skull | domotique | TCP 8123, HTTP | fumée/webhook actuel |
| tous les équipements | DNS/NTP | ports des services retenus | résolution et heure |

Cette table est une base issue de l’audit. Elle doit être revérifiée en direct
avant toute règle. mDNS ne traverse généralement pas les VLAN : ne pas en faire
une dépendance implicite.

## SKULL-11.1 — réauditer la topologie

### Étapes

1. Relever VLAN, sous-réseaux, passerelles, DHCP, DNS et pare-feu actuels.
2. Confirmer IP/MAC de Skull, boutons, sonnette et hôte domotique.
3. Capturer les connexions réelles pendant bouton, sonnette, lecture et fumée.
4. Comparer aux flux de `OPERATIONS.md` et expliquer chaque écart.
5. Repérer les dépendances broadcast, mDNS ou IP codée en dur.

### Acceptation

- inventaire horodaté et attribué ;
- aucune mutation réseau ;
- flux inconnus traités avant planification.

## SKULL-11.2 — réserver adressage et DNS

### Étapes

1. Choisir noms stables pour Skull et microcontrôleurs.
2. Réserver les baux DHCP ou adresses selon la norme du réseau.
3. Préparer enregistrements DNS directs et, si gérés, inverses.
4. Fixer TTL court pendant migration puis valeur normale après stabilisation.
5. Vérifier résolution depuis legacy, IoT et poste d’administration.
6. Ne pas modifier le Raspberry à cette tâche.

### Acceptation

- aucune collision DHCP/ARP ;
- noms résolus depuis les seules zones prévues ;
- tableau ancien/nouveau complet.

## SKULL-11.3 — écrire les ACL minimales

### Règles

1. Autoriser uniquement source, destination, protocole et port nécessaires.
2. Boutons et sonnette ne reçoivent aucun accès d’administration au Skull.
3. Skull n’accède à la domotique que sur le port requis.
4. Administration du Skull autorisée uniquement depuis le réseau de gestion.
5. Refuser le transit IoT vers legacy après migration, sauf coexistence listée.
6. Ajouter DNS/NTP explicitement ; ne pas autoriser « any » comme dépannage.

### Preuves attendues

Pour chaque règle : test positif depuis la source autorisée et test négatif
depuis au moins une source interdite. Vérifier également l’état sauvegardé du
pare-feu, pas seulement la règle en mémoire.

## SKULL-11.4 — préparer la coexistence

### Étapes

1. Permettre au Skull de répondre temporairement aux clients legacy et IoT.
2. Rendre adresses/destinations configurables, sans duplication de logique.
3. Ajouter journalisation temporaire des routes legacy par identité/source.
4. Définir durée, propriétaire et condition de retrait de chaque exception.
5. Préparer rollback IP/DNS/ACL avant la première bascule.

### Acceptation

- coexistence bornée dans le temps et dans les flux ;
- aucun accès large entre VLAN.

## SKULL-11.5 — migrer le Skull en premier

### Confirmation requise

Changement d’adresse/VLAN/DHCP/DNS ou règle réseau.

### Séquence

1. Vérifier accès console ou voie de récupération locale.
2. Sauvegarder configuration réseau et règles actuelles.
3. Appliquer réservations et ACL préparées.
4. Basculer le Skull vers IoT.
5. Vérifier adresse, route, DNS, NTP, SSH depuis gestion et port 5000 depuis les
   seules sources autorisées.
6. Tester que les clients legacy continuent pendant coexistence.
7. En cas d’échec, restaurer le réseau précédent par la voie locale prévue.

### Acceptation

- Skull administrable depuis gestion ;
- services externes requis accessibles ;
- refus inter-VLAN attendus confirmés.

## SKULL-11.6 — migrer les boutons

### Étapes

1. Sauvegarder firmware et configuration de l’ESP32.
2. Résoudre l’écart entre cinq boutons firmware et trois affectations serveur.
3. Remplacer l’IP du Skull par le nom DNS si le firmware le supporte.
4. Migrer réseau et identité technique.
5. Tester chaque bouton une fois, avec effets matériels neutralisés ou confirmés.
6. Tester Skull indisponible, délai d’attente et reprise.

### Acceptation

- cinq entrées documentées, même si certaines restent non affectées ;
- aucun blocage durable lorsque le Skull est absent.

## SKULL-11.7 — migrer la sonnette

### Étapes

1. Sauvegarder configuration et relever le payload exact.
2. Migrer destination DNS et identité technique.
3. Tester un appel sans session matérielle, puis un déclenchement confirmé.
4. Vérifier anti-rebond, timeout et comportement en cas d’échec.
5. Contrôler qu’aucune route d’administration n’est accessible depuis la
   sonnette.

### Acceptation

- événement unique par appui ;
- refus d’administration prouvé.

## SKULL-11.8 — migrer fumée et domotique

### Étapes

1. Confirmer le sens réel du flux et le port en capture.
2. Coordonner DNS, ACL et rotation du secret de phase 08.
3. Tester le webhook avec un appel sans dispositif dangereux.
4. Tester domotique indisponible et vérifier que la session se termine proprement.
5. Tester `Accueil` et non-`Accueil` selon le contrat caractérisé.

### Acceptation

- seul le scénario autorisé déclenche le webhook ;
- timeout borné ;
- secret ancien retiré après validation.

## SKULL-11.9 — retirer legacy

### Confirmation requise

Suppression des règles et adresses de coexistence.

### Étapes

1. Observer une période convenue sans appel legacy.
2. Exporter compteurs et journaux prouvant l’absence de client restant.
3. Retirer une exception à la fois.
4. Rejouer tous les tests positifs et négatifs.
5. Archiver la configuration pare-feu finale et la procédure de rollback.

### Acceptation

- aucun équipement Skull sur legacy ;
- aucune règle temporaire restante ;
- matrice de flux finale `VALIDÉE`.
