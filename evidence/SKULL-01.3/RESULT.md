# Résultat SKULL-01.3

- Date : 2 septembre 2026
- Statut : VALIDÉ
- Cible : `skull@192.168.1.116`
- Répertoire distant : `/var/backups/skull/20260902T192200Z/`
- Archive : `/var/backups/skull/20260902T192200Z/skull-runtime.tar.gz`
- Taille archive : `1608763251` octets
- SHA-256 : `b6935663b0e3d2ab9ed72e8a143646899e41f8a518261d9490301666203094ad`
- Fichier checksum : `/var/backups/skull/20260902T192200Z/SHA256SUMS.txt`
- Fichiers locaux modifiés : `evidence/SKULL-01.3/RESULT.md` uniquement

## Contenu sauvegardé

- `/opt/skull/data` ;
- `/opt/skull/config` ;
- `/etc/systemd/system/servo-sync.service` ;
- `/etc/systemd/system/playlist-web.service` ;
- `manifest.txt` non sensible.

Les venv, caches et logs historiques n’ont pas été inclus. Aucun contenu de
configuration, secret, clé ou fichier `.env` n’a été affiché ou copié dans la
preuve locale.

## Validation effectuée sur le Raspberry

- préflight immédiat réussi avant écriture ;
- espace disponible supérieur à deux fois la taille `data + config` ;
- répertoire créé en `750 root:root` ;
- archive finale en `600 root:root` ;
- checksum calculé puis vérifié avec `sha256sum -c` ;
- archive relue avec `tar -tzf` ;
- `113` entrées présentes ;
- dossiers `data/` et `config/`, deux unités systemd et `manifest.txt` vérifiés ;
- services `servo-sync.service` et `playlist-web.service` restés `active` ;
- aucun arrêt, redémarrage, scan Bluetooth, mouvement, lecture audio ou appel
  de fumée.

## Rollback

L’opération est additive. Aucun rollback n’est nécessaire. L’archive doit être
conservée jusqu’à validation de la copie hors Raspberry et d’une restauration
temporaire dans `SKULL-01.4`.

## Prochaine tâche autorisée

`SKULL-01.4` — copier l’archive et son checksum hors du Raspberry, vérifier les
empreintes puis tester une extraction temporaire locale. Cette tâche ne doit
pas supprimer l’archive distante.
