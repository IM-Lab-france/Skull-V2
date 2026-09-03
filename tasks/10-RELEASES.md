# Phase 10 — déployer par releases atomiques

## Arborescence cible

```text
/opt/skull/releases/<release-id>/   code et venv immuables
/opt/skull/current -> releases/...  lien de la release active
/etc/skull/                         configuration et références de secrets
/var/lib/skull/                     sessions et état persistant
/var/log/skull/                     journaux
```

Aucune ancienne release n’est supprimée dans cette phase.

## SKULL-10.1 — définir l’identifiant et le manifeste

### Étapes

1. Former `release-id` avec version, commit complet et date UTC.
2. Produire un manifeste contenant commit, fichiers, SHA-256, versions Python et
   dépendances verrouillées.
3. Enregistrer les migrations de données/configuration requises.
4. Signaler un arbre Git sale ; ne pas fabriquer de release sans provenance.
5. Exclure venv local, logs, données, sauvegardes et secrets.

### Acceptation

- archive reconstruisible depuis le commit et le lockfile ;
- hash vérifié avant et après transfert ;
- manifeste sans secret.

## SKULL-10.2 — construire l’artefact hors production

### Étapes

1. Partir d’un clone ou worktree propre au commit visé.
2. Lancer lint, tests unitaires, caractérisation et intégration simulée.
3. Construire l’archive avec ordre et horodatages reproductibles si possible.
4. Extraire l’archive dans un dossier temporaire neuf.
5. Recréer le venv depuis les dépendances verrouillées.
6. Démarrer en simulation et vérifier live/ready/routes legacy.
7. Générer le rapport `evidence/SKULL-10.2/RESULT.md`.

### Acceptation

- aucune dépendance au répertoire source ;
- test depuis l’archive extraite, pas depuis le worktree ;
- hashes conformes au manifeste.

## SKULL-10.3 — créer l’installateur idempotent

### Étapes

1. Accepter explicitement archive, manifeste et répertoire cible.
2. Vérifier que la cible résolue reste sous `/opt/skull/releases`.
3. Refuser une release existante différente ; accepter sans changement une
   release identique.
4. Extraire dans un dossier temporaire sous le même système de fichiers.
5. Vérifier hashes puis renommer atomiquement.
6. Créer le venv dans la release ou l’associer de manière immuable.
7. Ne jamais toucher au lien `current` pendant l’installation.

### Acceptation

- deux exécutions donnent le même état ;
- archive corrompue refusée avant bascule ;
- aucune commande de suppression récursive large.

## SKULL-10.4 — rendre systemd indépendant de la version

### Étapes

1. Faire pointer `ExecStart` vers `/opt/skull/current`.
2. Fixer utilisateur, groupe, répertoire de travail et fichiers de configuration.
3. Restreindre redémarrages en boucle avec délais et limites.
4. Déclarer explicitement accès I²C, audio et réseau requis.
5. Valider l’unité avec `systemd-analyze verify` avant installation.
6. Conserver une copie horodatée de l’unité précédente.

### Acceptation

- unité identique entre releases ;
- aucun chemin vers un ancien clone ou venv mutable.

## SKULL-10.5 — préflight de bascule

### Contrôles sans mouvement

1. vérifier manifeste et hashes ;
2. charger et valider la configuration ;
3. vérifier droits d’accès aux données/logs ;
4. vérifier dépendances Python ;
5. vérifier disponibilité du port cible ;
6. vérifier imports des adaptateurs sans les activer ;
7. démarrer la release sur port parallèle en simulation ;
8. comparer les contrats HTTP.

### Acceptation

- résultat unique `PASS` ou `FAIL` avec détail ;
- un `FAIL` empêche la bascule ;
- aucun healthcheck ne déplace le matériel.

## SKULL-10.6 — basculer atomiquement

### Confirmation requise

Modification du lien `current` et redémarrage du service.

### Séquence

1. Enregistrer la cible actuelle du lien.
2. Créer un nouveau lien temporaire vers la candidate.
3. Remplacer `current` atomiquement.
4. Redémarrer le service et attendre avec délai borné.
5. Vérifier live, ready, version, routes legacy et journaux.
6. N’autoriser les tests matériels qu’en phase 12.
7. Écrire release précédente, nouvelle et résultat dans la preuve.

### Acceptation

- service actif sur l’unique release annoncée ;
- aucune copie partielle visible via `current`.

## SKULL-10.7 — tester le rollback

### Étapes

1. Préparer une candidate qui échoue au ready sans action matérielle.
2. Lancer la bascule pendant une fenêtre confirmée.
3. Détecter l’échec dans le délai défini.
4. Refaire pointer `current` vers la release précédente.
5. Redémarrer et vérifier version/live/ready/routes legacy.
6. Vérifier que données et configuration n’ont pas été rétrogradées ou perdues.

### Acceptation

- rollback automatique ou commande unique documentée ;
- service précédent restauré en moins de cinq minutes ;
- preuve d’échec volontaire et de récupération.

## Migrations de données

Une migration destructive ou irréversible est interdite. Toute évolution de
format doit lire l’ancien format, écrire un nouveau fichier distinct, vérifier,
puis basculer par renommage. Le rollback applicatif doit rester capable de lire
les données ou disposer d’une copie restaurable.
