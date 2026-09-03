# Phase 09 — sécuriser les API sans casser les clients legacy

## Principe

La sécurité est introduite par coexistence mesurée. Une route legacy n’est pas
fermée tant que ses appelants, adresses et scénarios de reprise ne sont pas
prouvés. Aucune règle large inter-VLAN ne doit compenser un inventaire incomplet.

## SKULL-09.1 — produire le modèle de menace et l’inventaire des routes

### Étapes

1. Lister chaque route : méthode, paramètres, effet, client connu et fréquence.
2. Classer l’effet : lecture publique, contrôle normal, administration, matériel
   sensible ou destructif.
3. Identifier les frontières : navigateur, boutons, sonnette, domotique, Skull
   et administrateur.
4. Relever les adresses sources réellement vues dans les logs, en les conservant
   dans une preuve privée si nécessaire.
5. Documenter rejeu, injection, CSRF, appel anonyme, upload hostile, DoS local et
   divulgation de secret.
6. Créer `docs/api-security-matrix.md`.

### Acceptation

- aucune route sans classification ;
- chaque client legacy a un propriétaire et une méthode de migration ;
- inconnues marquées `BLOQUÉ`, pas remplacées par une supposition.

## SKULL-09.2 — séparer les façades

### Groupes

- public : statut non sensible et lecture strictement nécessaire ;
- contrôle : play, pause, stop et commandes autorisées ;
- administration : upload, suppression, restart, Bluetooth, calibration/pitch ;
- legacy : contrats historiques maintenus temporairement.

### Étapes

1. Créer un blueprint par groupe.
2. Appliquer limites de taille et validation avant lecture complète du corps.
3. Interdire les méthodes HTTP non prévues.
4. Retourner 404 ou 405 de manière cohérente sans révéler la structure interne.
5. Vérifier les snapshots legacy après déplacement.

### Acceptation

- mêmes contrats legacy ;
- politiques applicables par groupe, sans décorateur oublié.

## SKULL-09.3 — protéger l’administration

### Cible minimale

Utiliser une identité technique stockée hors Git. Comparer les jetons en temps
constant. Ne jamais placer un secret dans l’URL, les logs ou un message d’erreur.

### Étapes

1. Ajouter un middleware d’authentification pour le groupe administration.
2. Charger la référence du secret depuis la configuration sécurisée.
3. Rejeter absence, format invalide et jeton incorrect avant l’action.
4. Si l’IHM emploie une session navigateur, ajouter protection CSRF et cookie
   `HttpOnly`, `SameSite` et `Secure` lorsque HTTPS est effectif.
5. Ajouter limitation de débit pour les opérations coûteuses.
6. Journaliser résultat, route et identité non secrète, jamais le jeton.

### Acceptation

- tableau de tests 401/403/200 pour chaque route sensible ;
- aucun effet matériel ou fichier lors d’un refus ;
- rotation possible sans modifier le code.

## SKULL-09.4 — identifier boutons et sonnette

### Étapes

1. Vérifier d’abord les capacités exactes de chaque firmware.
2. Préférer un jeton distinct par appareil et une route de contrôle dédiée.
3. Si le firmware ne sait pas porter un secret, utiliser temporairement ACL
   réseau source/destination très précise et planifier son remplacement.
4. Ajouter timestamp/nonce uniquement si l’horloge et le firmware le permettent.
5. Ne jamais partager le jeton administrateur avec un microcontrôleur.
6. Tester identité valide, mauvais appareil, rejeu et requête anonyme.

### Acceptation

- compromission d’un bouton ne donne pas accès à l’administration ;
- limitation temporaire clairement documentée.

## SKULL-09.5 — limiter CORS, uploads et entrées

### Étapes

1. Recenser les origines réellement nécessaires.
2. Refuser `*` sur les routes avec identité ou effet.
3. Limiter taille, extension, type détecté et nom des uploads.
4. Générer le nom de stockage côté serveur et empêcher toute traversée de chemin.
5. Écrire dans un fichier temporaire, valider, puis déplacer atomiquement.
6. Borner nombres, chaînes, listes, durées et angles avant le domaine.
7. Tester payload trop grand, double extension, chemin relatif et JSON profond.

### Acceptation

- aucune écriture hors du répertoire prévu ;
- aucune entrée invalide n’atteint un adaptateur matériel.

## SKULL-09.6 — définir les modes dégradés

### Étapes

1. Pour domotique, fumée, Bluetooth et ESP32, choisir : bloquant, optionnel ou
   dégradé.
2. Fixer timeouts, nombre de tentatives et comportement utilisateur.
3. Interdire qu’un échec fumée bloque l’arrêt de la session.
4. Rendre l’état dégradé visible dans `/health/ready` et l’IHM sans secret.
5. Tester chaque dépendance absente séparément et simultanément.

### Acceptation

- pas de boucle infinie ;
- état final sûr ;
- erreur externe n’accorde jamais davantage de droits.

## SKULL-09.7 — déployer la transition de sécurité

### Confirmation requise

Toute activation d’authentification, d’ACL ou de règle pare-feu.

### Séquence

1. Observer les clients legacy sur une période convenue.
2. Déployer journalisation et nouvelles routes sans fermer les anciennes.
3. Migrer un client à la fois et prouver succès/refus attendu.
4. Activer les restrictions sur la candidate.
5. Exécuter la matrice complète depuis chaque réseau concerné.
6. Basculer, surveiller les refus et garder un rollback local testé.
7. Fermer les routes legacy seulement après validation explicite.

### Acceptation

- appels autorisés fonctionnels ;
- appels interdits refusés ;
- boutons et sonnette compatibles pendant la transition.

## Rollback

Restaurer unité, configuration et règles précédentes à partir des fichiers
sauvegardés. Ne pas désactiver globalement le pare-feu et ne pas ouvrir un sous-
réseau entier pour résoudre un client inconnu.
