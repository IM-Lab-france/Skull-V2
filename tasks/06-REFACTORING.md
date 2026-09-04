# Phase 06 — découper l’application sans casser le comportement

## Règle générale

Une tâche ci-dessous correspond à un commit isolé. Après chaque tâche, exécuter
les tests de caractérisation complets. Aucun changement de contrat HTTP ou de
valeur servo n’est accepté dans cette phase.

## Architecture cible minimale

```text
skull/
  app.py                 # factory Flask et assemblage
  domain/                # logique sans Flask ni matériel
  services/              # orchestration des cas d’usage
  adapters/              # PCA9685, audio, Bluetooth, HTTP externes
  api/legacy.py          # contrats historiques inchangés
  api/v1.py              # nouveaux contrats versionnés
  config.py              # lecture et validation
```

Les noms peuvent s’adapter au dépôt, mais les dépendances restent orientées de
l’API et des adaptateurs vers le domaine, jamais l’inverse.

## SKULL-06.1 — extraire les types et erreurs du domaine

### Étapes

1. Recenser statuts, dictionnaires et exceptions actuellement implicites.
2. Créer des types pour session, événement de timeline, élément de playlist et
   état de lecture.
3. Créer des erreurs métier distinctes : introuvable, invalide, conflit,
   dépendance indisponible et opération interdite.
4. Ne pas importer Flask, requests, subprocess ou bibliothèque Raspberry dans
   le domaine.
5. Adapter le code existant sans modifier les réponses HTTP.

### Acceptation

- domaine importable sur Windows ;
- exceptions traduites par la façade legacy comme avant ;
- tests de caractérisation inchangés et verts.

## SKULL-06.2 — extraire le catalogue de sessions

### Étapes

1. Isoler découverte des dossiers, détection MP3/JSON et validation des noms.
2. Définir l’ordre stable de parcours.
3. Gérer fichier absent, doublon, JSON invalide et dossier partiellement écrit.
4. Ne jamais supprimer ou corriger automatiquement une session invalide.
5. Tester le catalogue avec un répertoire temporaire.

### Acceptation

- résultat indépendant de Flask ;
- erreurs déterministes ;
- mêmes sessions visibles qu’avant sur le jeu de référence.

## SKULL-06.3 — extraire timeline et interpolation

### Étapes

1. Séparer parsing, validation, normalisation et interpolation.
2. Conserver toutes les variantes de format caractérisées en phase 03.
3. Valider timestamps croissants, canaux connus et valeurs numériques finies.
4. Conserver fréquence, arrondis, clamp et offsets observés.
5. Produire des erreurs avec index d’événement sans exposer le contenu complet.
6. Tester limites, événements simultanés et timeline vide.

### Acceptation

- traces interpolées identiques aux fixtures de référence ;
- aucune attente réelle ni accès matériel dans ce module.

## SKULL-06.4 — extraire playlist et état de lecture

### Étapes

1. Isoler ajout, déplacement, suppression, skip, catégorie et randomisation.
2. Formaliser les invariants : index courant valide, absence de doublon non
   désiré, traitement spécial de `Accueil` préservé.
3. Injecter la source d’aléatoire dans les tests.
4. Rendre les écritures de playlist atomiques par fichier temporaire puis
   remplacement.
5. En cas d’erreur d’écriture, conserver le fichier précédent.

### Acceptation

- fixtures legacy inchangées ;
- tests déterministes du mode aléatoire ;
- corruption simulée sans perte du fichier valide.

## SKULL-06.5 — introduire la machine à états

### États minimaux

`IDLE`, `STARTING`, `PLAYING`, `PAUSED`, `STOPPING`, `ERROR`.

### Étapes

1. Lister les transitions autorisées et l’erreur retournée pour les autres.
2. Associer chaque transition à ses effets : audio, timeline, fumée et état
   publié.
3. Protéger les transitions concurrentes avec un mécanisme unique.
4. Faire de `stop` une opération idempotente.
5. Garantir qu’une erreur remet les sorties dans un état sûr défini.
6. Tester chaque arc et chaque transition interdite.

### Acceptation

- tableau complet des transitions dans le code ou la documentation ;
- aucun thread orphelin après stop ou erreur ;
- mêmes statuts visibles par les routes legacy.

## SKULL-06.6 — extraire les adaptateurs

### Étapes

1. Envelopper PCA9685, audio, Bluetooth, ESP32, fumée et gaze derrière les
   protocoles de phase 04.
2. Déplacer parsing de commandes et HTTP dans l’adaptateur concerné.
3. Convertir les erreurs techniques en erreurs métier stables.
4. Injecter les adaptateurs dans les services ; interdire les singletons cachés.
5. Ajouter tests unitaires avec faux adaptateurs et tests d’intégration séparés.

### Acceptation

- le cœur ne dépend d’aucune IP, commande shell ou bibliothèque Raspberry ;
- chaque adaptateur peut échouer indépendamment dans les tests.

## SKULL-06.7 — conserver la façade legacy

### Étapes

1. Regrouper les routes historiques dans un blueprint dédié.
2. Conserver chemins, méthodes, paramètres, statuts et schémas JSON.
3. Traduire les appels vers les nouveaux services.
4. Ajouter un avertissement de dépréciation uniquement si cela ne casse pas les
   clients ; sinon le journaliser côté serveur.
5. Rejouer les snapshots de phase 03.

### Acceptation

- zéro modification côté boutons, sonnette ou interface existante ;
- comparaison contractuelle sans différence non approuvée.

## SKULL-06.8 — ajouter `/api/v1`

### Étapes

1. Définir une convention JSON unique pour succès et erreur.
2. Versionner explicitement les routes nouvelles.
3. Valider toutes les entrées avant appel métier.
4. Ne pas exposer traceback, commande, secret ou chemin système.
5. Générer une table de correspondance legacy vers v1.
6. Ne migrer aucun client pendant cette tâche.

### Acceptation

- documentation et tests de contrat pour chaque route v1 ;
- coexistence legacy/v1 ;
- aucun effet sur le comportement matériel.
