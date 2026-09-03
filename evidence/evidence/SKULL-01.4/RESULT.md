# Résultat SKULL-01.4

- Date : 2 septembre 2026
- Statut : VALIDÉ
- Source distante : `skull@192.168.1.116`
- Archive distante conservée : `/var/backups/skull/20260902T192200Z/skull-runtime.tar.gz`
- Destination locale : `C:\Skull-V2\backups\SKULL-01.3\`
- Archive locale : `C:\Skull-V2\backups\SKULL-01.3\skull-runtime.tar.gz`
- Checksum local : `C:\Skull-V2\backups\SKULL-01.3\SHA256SUMS.txt`
- Restauration temporaire : `C:\Users\cedri\AppData\Local\Temp\Skull-SKULL-01.4-20260902T194721Z`

## Résultats

- transfert binaire terminé avec code `0` ;
- taille locale : `1608763251` octets ;
- SHA-256 distant et local identique :
  `b6935663b0e3d2ab9ed72e8a143646899e41f8a518261d9490301666203094ad` ;
- archive locale lisible avec `tar.exe -tzf` ;
- `113` entrées détectées ;
- extraction locale réussie avec code `0` ;
- `opt/skull/data`, `opt/skull/config`, les deux unités systemd et
  `manifest.txt` restaurés ;
- dossier local `backups/` confirmé ignoré par Git ;
- archive distante toujours présente en `600 root:root` ;
- checksum distant toujours présent en `600 root:root` ;
- services distants toujours `active` ;
- aucune suppression de l’archive distante.

## Validation exécutée

```powershell
git check-ignore -v C:\Skull-V2\backups\SKULL-01.3
Get-FileHash -Algorithm SHA256 C:\Skull-V2\backups\SKULL-01.3\skull-runtime.tar.gz
tar.exe -tzf C:\Skull-V2\backups\SKULL-01.3\skull-runtime.tar.gz
tar.exe -xzf C:\Skull-V2\backups\SKULL-01.3\skull-runtime.tar.gz -C <répertoire-temporaire>
```

Le contenu des fichiers de configuration n’a pas été affiché. L’extraction
temporaire contient une copie sensible et doit rester protégée jusqu’à décision
de conservation ou de suppression.

## Rollback

Le transfert et l’extraction sont des opérations locales additives. L’archive
distante n’a pas été supprimée. Le répertoire temporaire exact est connu et
peut être supprimé séparément après confirmation de son chemin ; aucune
suppression n’a été effectuée automatiquement.

## Prochaine tâche autorisée

`SKULL-01.5` — préparer l’évaluation d’un clone de carte SD. Cette tâche reste
un plan uniquement et ne doit exécuter aucune image brute sans confirmation.
