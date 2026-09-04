# Phase 01 — gel et sauvegarde de production

Cette phase précède toute modification applicative distante.

## SKULL-01.1 — préflight de sauvegarde

### Autorisation

Lecture distante seulement.

### Étapes

1. Vérifier l’hôte, les services, l’espace libre et la taille de `/opt/skull`.
2. Lister les volumes montés et confirmer que `/opt/skull` est sur `/`.
3. Mesurer séparément `data`, `config`, `logs`, `.venv` et `.venv_playlist`.
4. Vérifier que `/var/backups` reste dans le filesystem attendu.
5. Relever le commit, le statut Git et les fichiers non suivis sans afficher
   `.env` ni `bluetooth_device.env`.
6. Choisir un horodatage UTC unique : `YYYYMMDDTHHMMSSZ`.

### Commandes de référence

```bash
hostname
df -h / /opt/skull /var/backups
du -sh /opt/skull/data /opt/skull/config /opt/skull/logs \
  /opt/skull/.venv /opt/skull/.venv_playlist
cd /opt/skull
git status --short --branch
git rev-parse HEAD
git diff --stat
```

### Acceptation

- espace libre supérieur à deux fois la taille des données à archiver ;
- aucun chemin cible ambigu ;
- commit et statut enregistrés dans `evidence/SKULL-01.1/RESULT.md` ;
- secrets exclus du compte rendu.

## SKULL-01.2 — exporter le code de production

### Autorisation

Lecture distante et écriture locale dans `evidence/SKULL-01.2/`. Aucun arrêt de
service.

### Étapes

1. Créer localement `evidence/SKULL-01.2/`.
2. Exporter `git rev-parse HEAD`, `git status --porcelain=v1` et
   `git diff --binary` depuis `/opt/skull`.
3. Exporter la liste des fichiers applicatifs avec tailles et SHA-256.
4. Exclure `.env`, config runtime, données, logs, venv et clés.
5. Exporter `systemctl cat` pour les deux services dans des fichiers séparés.
6. Exporter `pip freeze` des deux venv.
7. Calculer les checksums des exports locaux.

### Artefacts attendus

```text
evidence/SKULL-01.2/
  RESULT.md
  production-head.txt
  production-status.txt
  production.patch
  source-sha256.txt
  servo-sync.service.txt
  playlist-web.service.txt
  requirements-main.freeze.txt
  requirements-playlist.freeze.txt
  SHA256SUMS.txt
```

### Acceptation

- `production.patch` est applicable dans un worktree temporaire basé sur le
  commit relevé ;
- aucun secret détecté par recherche des noms de variables sensibles ;
- les deux listes de dépendances ne sont pas vides ;
- le Raspberry n’a pas été modifié.

## SKULL-01.3 — créer l’archive de données

### Autorisation

**CONFIRMATION obligatoire** avant création distante. Cette tâche écrit dans
`/var/backups/skull/<horodatage>/` mais ne modifie pas `/opt/skull`.

### Cible exacte

```text
/var/backups/skull/<horodatage>/skull-runtime.tar.gz
```

### Contenu

- `/opt/skull/data` ;
- `/opt/skull/config` ;
- unités systemd Skull ;
- manifeste de versions ;
- aucun venv, cache ou log historique.

### Étapes

1. Refaire SKULL-01.1 immédiatement avant l’écriture.
2. Créer le répertoire d’horodatage avec permissions `0750`.
3. Créer l’archive avec chemins relatifs depuis `/`.
4. Écrire un SHA-256 à côté de l’archive.
5. Exécuter `tar -tzf` et vérifier la présence de `data/` et `config/`.
6. Ne jamais afficher le contenu des fichiers de configuration.

### Acceptation

- archive non vide ;
- checksum vérifié sur le Raspberry ;
- liste de contenu lisible ;
- permissions empêchant l’accès aux autres utilisateurs ;
- services restés actifs pendant la création.

### Rollback

L’archive est additive. En cas d’échec, conserver le fichier incomplet et le
signaler ; ne pas le supprimer automatiquement.

## SKULL-01.4 — copier et vérifier hors Raspberry

### Autorisation

Lecture distante et écriture locale dans un dossier de sauvegarde hors Git.

### Étapes

1. Ajouter le dossier local de sauvegarde à `.gitignore` avant la copie.
2. Copier l’archive et son checksum via SCP.
3. Recalculer SHA-256 localement.
4. Comparer strictement les deux valeurs.
5. Tester l’ouverture de l’archive sans extraction dans le workspace.
6. Extraire dans un dossier temporaire dédié, jamais à la racine du dépôt.
7. Vérifier les dossiers et supprimer uniquement le dossier temporaire après
   validation explicite de son chemin.

### Acceptation

- checksum local égal au checksum distant ;
- archive ouvrable ;
- `data` et `config` restaurables dans un emplacement temporaire ;
- aucun fichier de sauvegarde suivi par Git.

## SKULL-01.5 — préparer la sauvegarde de carte SD

### Autorisation

Plan uniquement tant que le support cible et la méthode ne sont pas choisis.

### Étapes

1. Identifier le type/taille de la carte avec `lsblk`.
2. Identifier un stockage externe assez grand.
3. Choisir entre arrêt physique + image hors ligne, ou outil compatible avec
   snapshot cohérent.
4. Documenter la durée, l’espace requis et la procédure de restauration.
5. Obtenir confirmation avant toute image brute.

### Acceptation

- source et destination exactes identifiées ;
- aucune commande `dd` n’est exécutée sans confirmation ;
- procédure de restauration définie et relue.

