# Phase 03 — tests de caractérisation

## Prérequis et autorisation

- `SKULL-02.5` validée ;
- modifications et tests locaux uniquement ;
- aucun appel au Raspberry, aucun scan Bluetooth et aucun accès matériel ;
- les comportements observés sont figés avant toute tentative de correction.

## SKULL-03.1 — installer le socle de tests

### Autorisation

Modifications locales uniquement.

### Étapes

1. Ajouter `pytest` aux dépendances de développement, pas à la production.
2. Créer `tests/unit`, `tests/contract`, `tests/fixtures`.
3. Ajouter une configuration pytest avec chemins déterministes.
4. Garantir qu’aucune collecte de test n’importe `board`, `busio` ou le PCA9685
   réel à ce stade.
5. Ajouter un test sentinelle qui échoue si une variable de mode production est
   activée pendant les tests.

### Acceptation

- `python -m pytest --collect-only` fonctionne sur Windows ;
- aucun accès matériel à la collecte ;
- test sentinelle présent.

## SKULL-03.2 — caractériser les timelines

### Cas obligatoires

- racine `timeline` avec moteurs ;
- racine `keyframes` ;
- racine `frames` ;
- canaux top-level ;
- timestamps en bordure ;
- deux keyframes au même instant ;
- canal absent ;
- fichier vide, JSON invalide et format inconnu ;
- pourcentage de mâchoire 0, 50 et 100 ;
- valeurs hors limites et durée nulle.

### Étapes

1. Créer de petites fixtures synthétiques sans audio protégé.
2. Capturer les sorties de la version de référence.
3. Tester durée, nombre de frames, timestamps et angles.
4. Marquer explicitement les comportements étranges comme caractéristiques ;
   ne pas les « corriger » dans cette phase.
5. Ajouter un rapport pour les cas susceptibles de danger mécanique.

### Acceptation

- tous les formats existants couverts ;
- sorties de référence figées ;
- erreurs attendues testées ;
- aucun changement du parseur dans cette tâche.

## SKULL-03.3 — caractériser les sessions

### Cas obligatoires

- dossier avec exactement un MP3 et un JSON ;
- fichiers WAV cache présents ;
- MP3 manquant ;
- JSON manquant ;
- plusieurs MP3 ou JSON ;
- noms avec espaces, accents et casse différente ;
- tentative de traversée de chemin ;
- dossier vide.

### Acceptation

- comportement actuel documenté ;
- traversée de chemin refusée ;
- ordre de sélection multi-fichier connu ;
- aucune donnée de production copiée dans Git.

## SKULL-03.4 — figer les contrats HTTP legacy

### Entrées à capturer

- `GET /status` ;
- `GET /api/sessions` ;
- `POST /api/enqueue` valide/invalide ;
- `POST /play` valide/invalide ;
- pause, resume, stop ;
- playlist GET/POST/delete/move/skip ;
- catégories ;
- endpoints ESP32 avec adaptateur simulé.

### Étapes

1. Capturer les codes HTTP, content-types et schémas JSON.
2. Normaliser uniquement les champs temporels/non déterministes.
3. Créer des snapshots lisibles dans `tests/contracts`.
4. Ajouter un test qui compare clés, types et statuts, pas l’ordre JSON.
5. Documenter quels endpoints sont publics, matériels ou administratifs.

### Acceptation

- contrats utilisés par boutons et sonnette couverts en priorité ;
- aucune requête de test ne touche le Raspberry ;
- snapshots sans IP privée inutile, MAC ou secret.

## SKULL-03.5 — caractériser playlist et état de lecture

### Scénarios

1. file vide ;
2. ajout au repos : démarrage immédiat ou file selon comportement actuel ;
3. ajout pendant lecture ;
4. fin normale et lecture suivante ;
5. skip ;
6. stop ;
7. suppression de la session courante ;
8. mode aléatoire avec `Accueil` exclue ;
9. concurrence de deux requêtes enqueue ;
10. erreur audio ou Bluetooth avant démarrage.

### Acceptation

- transitions décrites par tableau état/événement/résultat ;
- absence de race évidente dans le test concurrent ;
- comportements indésirables consignés sans correction dans cette phase.

## SKULL-03.6 — caractériser fumée et dépendances externes

### Étapes

1. Remplacer le webhook par un serveur HTTP local factice.
2. Vérifier qu’il n’est appelé que pour `Accueil`, casse normalisée.
3. Vérifier méthode POST, timeout et traitement des statuts d’erreur.
4. Vérifier que l’échec fumée n’annule pas silencieusement la lecture.
5. Simuler timeout, refus de connexion et réponse 500.
6. Simuler ESP32 indisponible et réponse JSON invalide.

### Acceptation

- aucune URL réelle dans les fixtures ;
- nombre d’appels et ordre d’événements déterministes ;
- décisions d’échec documentées.
