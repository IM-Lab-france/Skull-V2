# Guide d’exécution pour GPT-5.6 Luna

## Mission

Ce fichier indique comment exécuter de façon fiable la modernisation du Skull
principal. Luna ne doit traiter qu’une fiche de tâche à la fois.

## Ordre de lecture obligatoire

Avant chaque tâche :

1. lire `OBJECTIF.md` ;
2. lire `MEMOIRE.md` ;
3. lire `OPERATIONS.md` ;
4. lire `TODO.md` ;
5. lire `tasks/README.md` ;
6. lire entièrement la fiche de phase concernée ;
7. inspecter les fichiers cités par cette fiche avant toute modification.

Si ces documents se contredisent, arrêter la tâche et signaler précisément les
deux passages incompatibles. Ne pas choisir silencieusement une interprétation.

## Unité de travail

Une exécution Luna doit porter sur **un seul identifiant de tâche**, par exemple
`SKULL-02.3`. Ne jamais demander « fais toute la phase » pour une phase qui
contient plusieurs modifications indépendantes.

Prompt minimal recommandé :

```text
Travaille dans C:\Skull-V2. Lis LUNA.md et les fichiers de pilotage obligatoires.
Exécute uniquement la tâche SKULL-XX.Y de tasks/XX-....md.
Respecte ses autorisations, critères d’acceptation et points d’arrêt.
Préserve les changements existants. Mets à jour la preuve et la TODO seulement
si tous les critères sont validés.
```

Pour une revue sans modification, ajouter :

```text
Mode diagnostic uniquement : aucune écriture locale ou distante.
```

## Réglage Luna conseillé

- `high` pour une tâche locale bornée avec tests clairs ;
- `xhigh` pour architecture, sécurité, migration de données ou analyse de diff ;
- `max` seulement pour un blocage difficile après échec documenté ;
- une nouvelle tâche/phase démarre dans une nouvelle conversation si le contexte
  précédent contient beaucoup de logs ou de sorties outils.

## Autorisations par défaut

Luna peut, sans nouvelle confirmation :

- lire les dépôts et fichiers de documentation ;
- exécuter `git status`, `git diff`, `git log` et les tests locaux ;
- modifier les fichiers locaux explicitement visés par la tâche ;
- créer des tests et preuves locales ;
- lancer des validations sans matériel en mode simulé.

Luna doit obtenir une confirmation explicite avant :

- toute écriture sur `192.168.1.116` ;
- tout arrêt ou redémarrage de service distant ;
- tout scan ou mouvement de servo ;
- toute lecture audio ou commande de fumée/relais ;
- toute modification réseau, Bluetooth ou systemd ;
- toute suppression, restauration, publication ou poussée Git ;
- toute commande nécessitant `sudo` qui modifie l’état.

Une autorisation donnée pour une tâche ne s’étend pas aux tâches suivantes.

## Interdictions

- Ne jamais utiliser `git reset --hard`, `git clean`, `git checkout --` ou une
  suppression récursive sur les dépôts ou le Raspberry.
- Ne jamais copier un secret, mot de passe, webhook complet, clé privée ou
  fichier `.env` dans le chat, Git, les preuves ou les logs.
- Ne jamais remplacer silencieusement une configuration de production.
- Ne jamais faire de fallback automatique du matériel réel vers le simulateur.
- Ne jamais considérer un test simulé comme une validation matérielle.
- Ne jamais modifier les limites/offsets des servos sans fiche matérielle et
  confirmation explicite.
- Ne jamais appliquer un patch de production dont le diff n’a pas été relu.

## Préflight obligatoire

Au début de chaque tâche locale :

```powershell
Set-Location C:\Skull-V2
git status --short --branch
git diff --stat
```

Avant une lecture distante autorisée :

```powershell
$skullKey = Join-Path $env:USERPROFILE '.ssh\skull_116_ed25519'
ssh -i $skullKey -o BatchMode=yes -o ConnectTimeout=8 `
  skull@192.168.1.116 'hostname; systemctl is-active servo-sync.service playlist-web.service'
```

Si le statut Git contient des changements non documentés par `MEMOIRE.md`,
arrêter et les présenter. Ne pas les écraser.

## Méthode d’implémentation

Pour chaque tâche :

1. reformuler l’objectif en une phrase ;
2. inventorier les fichiers réellement concernés ;
3. noter les hypothèses vérifiables ;
4. exécuter les contrôles de préflight ;
5. écrire ou compléter les tests qui doivent échouer avant le correctif ;
6. effectuer le changement minimal ;
7. exécuter les validations listées dans la fiche ;
8. inspecter `git diff --check` et le diff complet ;
9. enregistrer les preuves dans `evidence/<task-id>/RESULT.md` ;
10. mettre à jour `TODO.md` et `MEMOIRE.md` uniquement si la tâche est validée.

## Format des preuves

Chaque dossier `evidence/<task-id>/` contient au minimum un `RESULT.md` :

```markdown
# Résultat SKULL-XX.Y

- Date :
- Statut : VALIDÉ | PARTIEL | BLOQUÉ
- Portée :
- Fichiers modifiés :
- Commandes de validation :
- Résultats :
- Écarts ou risques restants :
- Rollback :
```

Ne pas stocker de gros logs bruts dans Git. Résumer les résultats et conserver
les sorties sensibles hors dépôt.

## Critère de clôture

Une case de `TODO.md` peut passer à `[x]` uniquement si :

- tous les critères d’acceptation de la fiche sont satisfaits ;
- les tests demandés passent ;
- `git diff --check` ne retourne pas d’erreur ;
- aucun secret n’apparaît dans le diff ;
- le rollback est décrit ;
- la preuve `evidence/<task-id>/RESULT.md` existe.

Sinon, conserver `[ ]` et inscrire `PARTIEL` ou `BLOQUÉ` dans la preuve.

## Compte rendu final attendu

Le compte rendu Luna doit tenir en cinq parties :

1. résultat obtenu ;
2. fichiers modifiés ;
3. tests et preuves ;
4. limites ou risques ;
5. prochaine tâche autorisée, sans l’exécuter.
