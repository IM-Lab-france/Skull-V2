# Phase 13 — actions configurables déclenchées par événement

## Contexte et borne

Cette phase remplace le couplage implicite entre une session et le webhook
historique. Elle ne modifie pas la sonnette, Home Assistant, le réseau ou un
équipement réel sans confirmation explicite. Le secret et ses valeurs restent
hors Git, hors preuves et hors conversation.

## SKULL-13.1 — modèle d'actions

### Objectif

Définir un modèle typé `événement → conditions → actions` pour séparer les
événements applicatifs (par exemple le démarrage d'une session) des effets
externes.

### Étapes

1. Lire la configuration phase 8 et les contrats legacy avant toute modification.
2. Définir les types d'événement, les conditions autorisées et les actions
   déclaratives sans valeur secrète.
3. Valider les clés inconnues, références de secrets absentes, boucles et
   actions incompatibles avant toute initialisation matérielle.
4. Journaliser l'identifiant de règle, la décision et le résultat en rédigeant
   toute donnée sensible.
5. Ajouter les tests unitaires des erreurs et des cas nominalement inertes.

### Acceptation

- une configuration invalide échoue avant un appel externe ;
- les routes legacy et la lecture restent compatibles ;
- aucune URL authentifiée ni secret n'apparaît dans le diff ou les preuves.

## SKULL-13.2 — liaisons configurées

### Étapes

1. Ajouter une fixture explicitant une action inerte et une action HTTP simulée.
2. Relier une session ou un événement à une règle par identifiant, jamais par
   une URL codée dans le code applicatif.
3. Interdire toute reconfiguration de la sonnette dans cette tâche.
4. Exiger une autorisation explicite et une référence de secret approuvée avant
   de préparer une cible réelle.

### Acceptation

- aucune action n'est exécutée par défaut ;
- l'origine et la règle appliquée sont observables sans secret ;
- le rollback désactive la règle sans modifier les données de session.

## SKULL-13.3 — caractérisation simulée

### Étapes

1. Tester succès, refus, timeout, indisponibilité et reprise avec adaptateurs
   simulés et une horloge contrôlée.
2. Tester que seule la règle explicitement activée est évaluée.
3. Tester l'absence de récursion et une limite de tentatives.
4. Vérifier que l'échec de l'action externe respecte le mode dégradé documenté.

### Acceptation

- aucun test ne contacte le réseau, Bluetooth, I2C, GPIO ou le dispositif fumée ;
- les délais sont bornés et les résultats sont rédigés ;
- la suite complète du worktree concerné est verte.

## Validation réelle ultérieure

Une recette avec effet réel appartient à la phase 12, après approbation humaine
spécifique, zone sécurisée et validation de l'identité/ACL de la cible.
