# Index des fiches d’exécution

Chaque fiche détaille une phase de `TODO.md`. Luna traite un seul identifiant de
tâche par exécution.

| Phase | Fichier | Objet |
|---:|---|---|
| 00 | `00-REPRISE.md` | preuves de la reprise déjà effectuée |
| 01 | `01-SAUVEGARDE.md` | gel et sauvegarde de production |
| 02 | `02-SOURCE-DE-VERITE.md` | reconstruction du code de référence |
| 03 | `03-CARACTERISATION.md` | contrats et tests du comportement actuel |
| 04 | `04-SIMULATION.md` | matériel et services simulés |
| 05 | `05-RUNTIME.md` | processus, WSGI, santé et logs |
| 06 | `06-REFACTORING.md` | découpage interne compatible |
| 07 | `07-BLUETOOTH-AUDIO.md` | fiabilisation BlueZ/PulseAudio |
| 08 | `08-CONFIGURATION.md` | configuration, secrets et migration |
| 09 | `09-SECURITE.md` | séparation et protection des API |
| 10 | `10-RELEASES.md` | déploiement atomique et rollback |
| 11 | `11-RESEAU-IOT.md` | migration réseau progressive |
| 12 | `12-VALIDATION-MATERIELLE.md` | recette physique finale |
| 13 | `13-ACTIONS-EVENEMENTS.md` | modèle événement → action sans secret |

## Dépendances

```text
00 → 01 → 02 → 03 → 04 → 05 → 06
                           ├────→ 07
                           ├────→ 08 → 09
                           ├────→ 10 → 11 → 12
                           └────→ 13 → 12
```

Les phases 07 et 08 peuvent être préparées en parallèle après la phase 05, mais
leurs déploiements attendent la validation de la phase 06.

L'état de référence et le worktree requis sont indiqués par l'« Audit de
continuité » de `MEMOIRE.md`. La phase 8 n'est pas intégrée au `main` du dépôt
de pilotage : son intégration est une tâche distincte qui exige revue, tests
dans le worktree source et rollback.

## Points d’entrée du code actuel

Cette carte décrit le `main` local au 2 septembre 2026. La phase 02 doit la
réconcilier avec le code réellement installé sur le Raspberry avant refactoring.

| Besoin | Point de départ actuel |
|---|---|
| application et routes principales | `web_app.py` |
| interface playlist séparée | `playlist_web.py` |
| lecture synchronisée | `sync_player.py` |
| parsing et interpolation | `timeline.py` |
| PCA9685 et servos | `rpi_hardware.py` |
| boucle audio d’ambiance | `loop_player.py` |
| réception gaze | `gaze_receiver.py` |
| journalisation | `logger.py` |
| démarrage principal | `launch_servo_sync.sh` |
| démarrage playlist | `launch_playlist_web.sh` |
| installation et unités | `install_skull.sh` |
| IHM principale | `templates/index.html`, `static/app.js`, `static/style.css` |
| IHM playlist | `templates/playlist_only.html`, `static/playlist.js` |

Les classes et fonctions sont des repères d’inspection, pas des interfaces
stables. Luna doit rechercher leur définition et leurs appelants avant chaque
déplacement. Elle ne doit jamais modifier simultanément une fonction et son
contrat legacy sans test de caractérisation préalable.

## Ordre dans une phase

Les identifiants sont exécutés dans l’ordre numérique. Une tâche ultérieure ne
commence pas si une dépendance est `PARTIELLE` ou `BLOQUÉE`, sauf décision écrite
dans `MEMOIRE.md`. Une préparation locale peut précéder une confirmation, mais
aucune action distante ou matérielle ne doit être incluse implicitement.
