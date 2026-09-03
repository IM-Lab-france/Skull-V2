# Phase 02 — reconstruction de la source de vérité

## SKULL-02.1 — préparer un worktree isolé

### Prérequis

- SKULL-01.2 validée ;
- patch de production et commit de base disponibles ;
- workspace principal préservé.

### Autorisation

Écriture Git locale. Aucun push, aucune modification distante.

### Étapes

1. Vérifier que le commit de production existe localement avec
   `git cat-file -e <commit>^{commit}`.
2. Si absent, effectuer un `git fetch` non destructif depuis `origin`.
3. Créer un worktree dans un chemin dédié hors `C:\Skull-V2`.
4. Créer la branche `codex/production-skull-2026` depuis le commit exact.
5. Vérifier que le worktree est propre avant application du patch.

### Acceptation

- branche basée sur le SHA exact de production ;
- workspace principal inchangé ;
- aucune branche distante créée ;
- chemin du worktree enregistré dans la preuve.

## SKULL-02.2 — appliquer et analyser le patch de production

### Étapes

1. Exécuter `git apply --check production.patch`.
2. Si l’échec vient uniquement des fins de ligne, comparer avec
   `--ignore-space-at-eol` sans appliquer aveuglément.
3. Appliquer le patch dans le worktree isolé.
4. Comparer `git diff --stat`, `git diff --numstat` et le manifeste SHA-256.
5. Classer chaque fichier : fonctionnel, UI, installation, données générées ou
   différence de fin de ligne.
6. Ne pas intégrer venv, logs, `.env`, config runtime ou audio.
7. Documenter chaque différence fonctionnelle dans
   `evidence/SKULL-02.2/DIFF-INVENTORY.md`.

### Point d’arrêt

Si le patch contient une URL secrète, une clé ou un identifiant sensible,
arrêter, rédiger une version redacted pour l’analyse et demander une décision.

### Acceptation

- les neuf fichiers applicatifs sont expliqués ;
- aucun artefact runtime intégré ;
- le diff fonctionnel est séparé du bruit de fins de ligne ;
- syntaxe Python validée.

## SKULL-02.3 — établir les dépendances reproductibles

### Étapes

1. Comparer `pip freeze` aux imports réels de chaque application.
2. Distinguer dépendances directes et transitives.
3. Créer `requirements.in` pour les dépendances directes principales.
4. Créer `requirements-playlist.in` pour l’interface playlist.
5. Générer des locks reproductibles pour Python 3.11 ARM64.
6. Documenter les paquets système nécessaires : FFmpeg, PortAudio, I²C,
   Bluetooth et PulseAudio.
7. Tester la création d’un venv neuf sur une machine Linux compatible ou un
   conteneur sans accéder au matériel.

### Acceptation

- aucune dépendance installée implicitement par le lanceur ;
- versions compatibles Python 3.11 ;
- imports purs validés dans un profil simulé ;
- procédure de mise à jour du lock documentée.

## SKULL-02.4 — créer les exemples de configuration

### Étapes

1. Inventorier les clés de tous les JSON et `.env` runtime sans copier leurs
   valeurs sensibles.
2. Créer des fichiers `.example` avec valeurs neutres.
3. Ajouter commentaires, types, unités et contraintes.
4. Vérifier que `.gitignore` exclut les fichiers actifs mais pas les exemples.
5. Ajouter un test détectant les secrets connus ou URLs de webhook dans le diff.

### Acceptation

- un nouvel utilisateur sait quelles valeurs fournir ;
- aucun secret dans Git ;
- les configurations actives restent ignorées ;
- les exemples sont validables automatiquement.

## SKULL-02.5 — valider la branche de référence

### Validation

```powershell
python -m compileall -q .
git diff --check
git status --short
```

Ajouter les tests disponibles à ce stade. Comparer ensuite les SHA-256 des
fichiers source à ceux de la production, en excluant uniquement les différences
documentées.

### Acceptation

- branche autonome et compréhensible ;
- aucun secret ou runtime ;
- toutes les différences résiduelles justifiées ;
- aucun push sans revue utilisateur.

