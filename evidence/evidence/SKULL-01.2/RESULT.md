# Résultat SKULL-01.2

- Date : 2 septembre 2026
- Statut : VALIDÉ
- Portée : export local des métadonnées de production, unités systemd,
  dépendances et empreintes source ; aucune écriture distante
- Cible : `skull@192.168.1.116`, `/opt/skull`
- Fichiers locaux créés : `evidence/SKULL-01.2/`

## Résultat obtenu

Les éléments suivants ont été récupérés en lecture seule et consignés
localement :

- commit de production :
  `57455ce3870af15485035ec9482761e34e3b592f` ;
- statut Git filtré des noms sensibles ;
- liste et statistiques du diff ;
- définition effective de `servo-sync.service` ;
- définition effective de `playlist-web.service` ;
- `pip freeze` du venv principal ;
- `pip freeze` du venv playlist ;
- SHA-256 des fichiers suivis, hors données, logs, venv et configuration
  sensible.

## Fichiers de preuve

- `production-head.txt`
- `production-status.txt`
- `servo-sync.service.txt`
- `playlist-web.service.txt`
- `requirements-main.freeze.txt`
- `requirements-playlist.freeze.txt`
- `source-sha256.txt`
- `production.patch`
- `SHA256SUMS.txt`

## Traitement du webhook

Le patch est un diff à contexte nul (`-U0`) produit depuis le commit de
production. Les lignes ajoutées qui contenaient une URL webhook ont été
remplacées par :

```python
os.environ["SKULL_SMOKE_WEBHOOK_URL"]
```

La variable `SKULL_SMOKE_WEBHOOK_URL` doit déjà être fournie au processus par un
fichier protégé ou une variable d’environnement, sans valeur dans Git. Une
variable absente provoque un échec explicite au chargement ; elle ne déclenche
aucun appel vers une URL de remplacement. Le patch ne contient aucune ancienne
valeur secrète, y compris dans les lignes de contexte.

## Observations de production

- neuf fichiers applicatifs sont modifiés hors du commit de référence ;
- les artefacts `.venv`, `.venv_playlist`, `logs` et `requirements.txt` ne sont
  pas suivis ;
- `servo-sync.service` lance actuellement `/opt/skull/.venv/bin/python
  /opt/skull/web_app.py` ;
- `playlist-web.service` lance `/opt/skull/launch_playlist_web.sh` ;
- les deux services utilisent `User=skull`, `Group=skull` et
  `Restart=on-failure` ;
- le venv principal contient notamment Flask, les bibliothèques PCA9685,
  PulseAudio/audio et GPIO ;
- le venv playlist contient Flask, requests et leurs dépendances.

## Validation

- clé SSH présente localement ;
- préflight local exécuté avec `git status --short --branch` et `git diff
  --stat` ;
- accès SSH non interactif réussi ;
- `git rev-parse HEAD` réussi ;
- `git diff --name-only`, `git diff --stat` et `git diff --check` exécutés ;
- `git apply --check --unidiff-zero --ignore-whitespace --whitespace=nowarn`
  réussi dans un worktree basé exactement sur le commit de production ;
- application effective du patch réussie dans ce worktree temporaire ;
- empreintes SHA-256 locales calculées dans `SHA256SUMS.txt` ;
- patch contenant `21094` lignes LF et `10667` lignes CRLF ;
- les fichiers sources modifiés résultants conservent leurs fins de ligne CRLF ;
- lecture stricte `os.environ["SKULL_SMOKE_WEBHOOK_URL"]` présente après application ;
- scan secret du patch et du `web_app.py` résultant : aucun résultat ;
- lecture des deux unités systemd réussie ;
- lecture des deux inventaires `pip freeze` réussie ;
- recherche de motifs secrets dans la preuve : aucun résultat ;
- aucun arrêt, redémarrage, scan, appairage, sudo ou écriture distante.

## Écarts et risques

- `git diff --check` signale des espaces de fin liés aux fins de ligne dans le
  diff de production ; ils sont conservés strictement dans le patch et ne sont
  pas normalisés ;
- la validation d’application a été faite sous Windows : le changement de mode
  Unix du seul `launch_playlist_web.sh` n’est pas matérialisé par le filesystem
  Windows ; il devra être revalidé sur Linux avant déploiement ;
- les dépendances sont observées mais pas encore transformées en lockfile
  reproductible ;
- aucun secret ne doit être recherché en affichant sa valeur.

## Rollback

Aucun rollback distant nécessaire : la tâche n’a effectué que des lectures.
Les fichiers locaux de preuve sont additifs. Ne pas supprimer les preuves pour
faire disparaître le statut `PARTIEL`.

## Prochaine action autorisée

`SKULL-01.3` — créer l’archive distante de données et configuration. Cette
tâche nécessitera une confirmation explicite avant toute écriture sur le
Raspberry.
