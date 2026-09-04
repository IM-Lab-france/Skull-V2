# Phase 08 — centraliser configuration et secrets

## Cible

- code immuable : `/opt/skull/current` ;
- configuration : `/etc/skull/config.toml` ;
- secrets : fichier distinct lisible uniquement par le service, ou gestionnaire
  de secrets approuvé ;
- données : `/var/lib/skull` ;
- logs : `/var/log/skull`.

TOML est la cible proposée car Python 3.11 peut le lire avec `tomllib`. Aucun
secret réel ne doit entrer dans Git, la documentation, les tests ou les preuves.

## SKULL-08.1 — inventorier la configuration actuelle

### Étapes

1. Rechercher variables d’environnement, JSON, constantes et IP codées en dur.
2. Pour chaque clé, noter source, type, valeur par défaut, sensibilité,
   consommateur et possibilité de rechargement.
3. Identifier les valeurs qui décrivent le matériel : canaux, neutres, limites,
   offsets et fréquence PWM.
4. Identifier les secrets sans afficher leur valeur.
5. Créer `docs/configuration-inventory.md` avec valeurs redigées.

### Acceptation

- chaque clé a un propriétaire et une destination cible ;
- aucune valeur secrète dans le diff Git.

## SKULL-08.2 — créer le schéma typé

### Sections minimales

`runtime`, `http`, `hardware`, `audio`, `bluetooth`, `esp32`, `smoke`,
`storage`, `logging` et `security`.

### Étapes

1. Définir types, plages et champs obligatoires.
2. Refuser valeur inconnue ou hors plage avec chemin précis de la clé.
3. Valider les relations, par exemple angle neutre inclus dans les limites.
4. Conserver les valeurs sensibles sous forme de références, pas de contenu.
5. Rediger intégralement les secrets lors de l’affichage de configuration.
6. Tester configuration minimale, complète, clé inconnue, type invalide et
   contrainte croisée invalide.

### Acceptation

- échec au démarrage avant toute initialisation matérielle ;
- message exploitable et sans secret ;
- configuration immuable après chargement.

## SKULL-08.3 — définir la précédence

### Ordre proposé

1. arguments de commande réservés aux opérations de maintenance ;
2. variables d’environnement explicitement autorisées ;
3. fichier `/etc/skull/config.toml` ;
4. valeurs par défaut sûres du schéma.

### Étapes

1. Documenter chaque clé surchargeable.
2. Interdire les valeurs matérielles critiques en argument HTTP.
3. Afficher la provenance de chaque valeur non sensible en diagnostic.
4. Tester toutes les collisions de sources.

### Acceptation

- une seule règle de précédence ;
- aucune configuration cachée dépendante du répertoire courant.

## SKULL-08.4 — importer la configuration legacy

### Étapes

1. Écrire un convertisseur séparé du démarrage normal.
2. Lire les anciens JSON et `.env` en lecture seule.
3. Produire TOML candidat et rapport de clés inconnues/redigées.
4. Ne jamais écraser un fichier cible existant.
5. Ne jamais supprimer les sources legacy.
6. Vérifier idempotence : deux conversions donnent le même résultat.
7. Comparer la configuration résolue legacy et nouvelle.

### Acceptation

- conversion locale sur copies de fixtures ;
- correspondance complète ou écarts explicitement bloquants ;
- rollback par sélection de l’ancien chargeur.

## SKULL-08.5 — sortir et remplacer le secret fumée

### Confirmation requise

Rotation du secret dans le Skull ou la domotique.

### Étapes

1. Repérer tous les producteurs et consommateurs du webhook.
2. Préparer une double acceptation temporaire si le système distant le permet.
3. Générer le nouveau secret par mécanisme approuvé, hors chat et Git.
4. Déployer d’abord le consommateur capable d’accepter le nouveau secret.
5. Basculer le producteur, tester, puis retirer l’ancien secret.
6. Rechercher l’ancien identifiant dans Git, logs et sauvegardes textuelles sans
   jamais l’imprimer.

La sonnette existante et son automatisation Home Assistant ne doivent pas être
reconfigurées dans cette tâche. Si l’ancien endpoint observé correspond à la
sonnette, il reste inchangé ; la configuration générique événement → action,
dont un bouton pouvant déclencher la fumée, est reportée à la phase 13.

### Acceptation

- ancien secret refusé, nouveau accepté ;
- aucune valeur dans l’historique Git créé par la modernisation ;
- procédure de récupération documentée.

## SKULL-08.6 — remplacer les IP par des noms internes

### Étapes

1. Établir la liste des dépendances et leur propriétaire DNS.
2. Créer les enregistrements seulement pendant la phase réseau approuvée.
3. Ajouter nom et IP de secours temporaire dans la configuration, sans fallback
   silencieux.
4. Tester résolution, timeout, mauvaise adresse et absence de DNS.
5. Conserver les routes legacy pendant la coexistence IoT.

### Acceptation

- aucun changement d’ACL implicite ;
- chaque nom résout depuis le réseau source prévu ;
- échec DNS visible et borné.

## SKULL-08.7 — déployer la nouvelle configuration

### Confirmation requise

Écriture sous `/etc/skull` et redémarrage du service.

### Séquence

1. Sauvegarder fichiers et permissions actuels.
2. Installer le candidat avec propriétaire et mode minimaux.
3. Exécuter un validateur sans initialiser le matériel.
4. Démarrer la candidate sur port parallèle.
5. Comparer configuration résolue et contrats legacy.
6. Basculer le service ; surveiller live, ready et logs.
7. En cas d’échec, restaurer fichiers et unité précédents.

### Acceptation

- démarrage legacy puis TOML testé ;
- permissions vérifiées par `stat` ;
- rollback démontré sans perte de données.
