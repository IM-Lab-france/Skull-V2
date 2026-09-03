# Phase 04 — mode matériel simulé

## Prérequis et autorisation

- phase 03 validée ;
- modifications et validations locales uniquement ;
- aucun import ou accès I²C, GPIO, audio ou Bluetooth réel pendant les tests ;
- tout test doit choisir explicitement le mode simulé.

## SKULL-04.1 — définir les protocoles d’adaptateurs

### Objectif

Rendre le cœur testable sans importer de bibliothèque Raspberry.

### Étapes

1. Définir des `Protocol` Python pour matériel servo, audio, Bluetooth, ESP32,
   fumée et gaze.
2. Limiter chaque protocole aux opérations réellement utilisées.
3. Décrire types d’entrée, résultat et exceptions attendues.
4. Ne déplacer aucune logique métier dans les adaptateurs.
5. Ajouter des tests de conformité pour les faux adaptateurs.

### Acceptation

- imports des protocoles possibles sur Windows sans dépendance Raspberry ;
- interfaces petites et documentées ;
- aucune modification de route HTTP dans cette tâche.

## SKULL-04.2 — simuler le PCA9685

### Étapes

1. Créer `SimulatedHardware` avec la même interface que le pilote réel.
2. Enregistrer chaque commande : canal, nom, angle demandé, angle clampé,
   impulsion calculée et timestamp logique.
3. Implémenter `neutral`, `cleanup` et offsets sans I²C.
4. Interdire toute importation de `board`/`busio` dans le module simulé.
5. Comparer les traces aux valeurs de référence.
6. Exiger `SKULL_HARDWARE_MODE=simulated` explicitement ; ne jamais basculer
   automatiquement en simulation si le matériel réel échoue.

### Acceptation

- tests Windows verts ;
- limites identiques à la référence ;
- mode production échoue clairement si I²C absent ;
- mode simulé ne crée aucun périphérique système.

## SKULL-04.3 — simuler l’audio et l’horloge

### Étapes

1. Introduire une horloge injectable (`monotonic`, `sleep`).
2. Créer un lecteur audio simulé avec durée configurable.
3. Supporter play, pause, resume, stop et fin de piste.
4. Permettre l’avancement déterministe sans attente réelle.
5. Vérifier synchronisation timeline/audio et dérive calculée.

### Acceptation

- une session de cinq minutes se teste en moins d’une seconde ;
- aucun device audio ouvert ;
- transitions reproductibles.

## SKULL-04.4 — simuler Bluetooth, ESP32 et fumée

### Bluetooth

Créer des états distincts : découvert, appairé, trusted, connecté, profil A2DP,
sink disponible. Permettre l’injection d’erreurs et délais.

### ESP32

Créer un faux serveur ou adaptateur avec statut, relais, auto-relay,
button-config et restart simulé. Enregistrer chaque appel.

### Fumée

Créer un adaptateur mémorisant les déclenchements et pouvant retourner succès,
timeout ou erreur HTTP.

### Acceptation

- scénarios d’échec testables sans réseau ;
- appels et payloads inspectables ;
- aucune adresse réelle dans les tests.

## SKULL-04.5 — sélectionner les adaptateurs au démarrage

### Étapes

1. Créer une factory centrale selon configuration validée.
2. Production : adaptateurs réels obligatoires.
3. Tests : adaptateurs simulés explicites.
4. Afficher le mode actif au démarrage sans secret.
5. Refuser `simulated` dans l’unité systemd de production.
6. Ajouter un test de démarrage pour chaque mode.

### Acceptation

- aucun fallback silencieux ;
- mode visible dans `/health/ready` ;
- production et simulation utilisent le même cœur métier.
