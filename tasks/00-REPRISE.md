# Phase 00 — reprise et compréhension

## SKULL-00.1 — vérifier le dossier de continuité

### Objectif

Garantir qu’un nouvel agent dispose des faits nécessaires avant tout travail.

### Autorisation

Lecture locale uniquement.

### Étapes

1. Lire `OBJECTIF.md`, `TODO.md`, `MEMOIRE.md` et `OPERATIONS.md`.
2. Vérifier que les quatre fichiers existent et ne sont pas vides.
3. Vérifier que `README.md` contient un lien vers chacun.
4. Vérifier que `MODERNISATION_SKULL.md` n’existe plus.
5. Exécuter `git diff --check`.

### Validation

```powershell
Test-Path OBJECTIF.md,TODO.md,MEMOIRE.md,OPERATIONS.md
rg -n 'OBJECTIF.md|TODO.md|MEMOIRE.md|OPERATIONS.md' README.md
Test-Path MODERNISATION_SKULL.md
git diff --check
```

### Acceptation

- les quatre premiers tests retournent `True` ;
- `MODERNISATION_SKULL.md` retourne `False` ;
- les liens sont présents ;
- aucune erreur de whitespace Git.

## SKULL-00.2 — vérifier l’accès distant en lecture seule

### Objectif

Confirmer que la cible est bien le Raspberry Skull sans modifier son état.

### Autorisation

SSH en lecture seule. Aucun `sudo` modifiant, aucune commande Bluetooth.

### Étapes

1. Vérifier la présence de la clé locale sans afficher son contenu.
2. Se connecter avec `BatchMode=yes`.
3. Lire hostname, OS, architecture, uptime et états des deux services.
4. Lire `/status` en supprimant l’adresse Bluetooth du résultat publié.

### Acceptation

- hostname `skull` ;
- Debian 12 ARM64 ou évolution explicitement documentée ;
- les deux services sont `active` ;
- `/status` répond en JSON ;
- aucun secret n’est copié dans la preuve.

### Point d’arrêt

Si l’OS, l’hôte ou les services diffèrent de `MEMOIRE.md`, mettre la tâche en
`BLOQUÉ` et demander une décision avant la suite.

