# Résultat SKULL-01.1

- Date : 2 septembre 2026, collecte `20260902T190313Z`
- Statut : VALIDÉ
- Portée : préflight de sauvegarde en lecture seule du Raspberry Skull
- Cible : `skull@192.168.1.116`, répertoire `/opt/skull`
- Fichiers modifiés : `evidence/SKULL-01.1/RESULT.md` uniquement

## Résultats observés

- hostname : `skull`
- système : Debian GNU/Linux 12 (bookworm), architecture `aarch64`
- `servo-sync.service` : `active`, `enabled`
- `playlist-web.service` : `active`, `enabled`
- `/opt/skull` : `/dev/mmcblk0p2`, ext4, chemin résolu `/opt/skull`
- `/var/backups` : `/dev/mmcblk0p2`, ext4
- taille globale `/opt/skull` : `2.5G`
- espace disponible sur le filesystem : `22685732 KiB` selon `df -Pk`
- tailles mesurées : `data 1.8G`, `config 3.8M`, `logs 617M`, `.venv 121M`,
  `.venv_playlist 31M`
- taille exacte `data + config` pour comparaison : `1832369302` octets
- espace libre exact pour comparaison : `23230189568` octets
- condition espace libre > 2 × archive : satisfaite (`23230189568` >
  `3664738604`)
- commit de production :
  `57455ce3870af15485035ec9482761e34e3b592f`
- statut Git de production : branche `main` alignée sur `origin/main`, avec
  neuf fichiers applicatifs modifiés localement et des artefacts runtime non
  suivis (`.venv`, `.venv_playlist`, `logs`, `requirements.txt`)
- diff Git de production : 9 fichiers, `10735` insertions et `10291`
  suppressions selon `git diff --stat`
- permissions observées : `/opt/skull` `755 skull:skull`, `/var/backups`
  `755 root:root`

Les noms de fichiers potentiellement sensibles ont été filtrés de la sortie de
statut. Aucun contenu de configuration, secret, clé, `.env` ou adresse
Bluetooth n’a été copié dans cette preuve.

## Commandes de validation

Préflight local :

```powershell
Set-Location C:\Skull-V2
git status --short --branch
git diff --stat
Test-Path $env:USERPROFILE\.ssh\skull_116_ed25519
```

Préflight distant en lecture seule :

```bash
hostname
. /etc/os-release; uname -m
systemctl is-active servo-sync.service playlist-web.service
systemctl is-enabled servo-sync.service playlist-web.service
findmnt -T /opt/skull
findmnt -T /var/backups
df -Pk / /opt/skull /var/backups
du -sh /opt/skull /opt/skull/data /opt/skull/config /opt/skull/logs \
  /opt/skull/.venv /opt/skull/.venv_playlist
du -sb /opt/skull/data /opt/skull/config
df -PB1 /opt/skull
cd /opt/skull; git rev-parse HEAD; git status --short --branch; git diff --stat
readlink -f /opt/skull
stat -c "%a %U %G %n" /opt/skull /var/backups
```

## Écarts ou risques restants

- la production possède bien neuf fichiers applicatifs modifiés hors du commit
  de référence ; ils devront être exportés dans `SKULL-01.2` avant toute
  synchronisation ;
- les données occupent environ 1.83 Go : une archive compressée et sa copie
  locale doivent être dimensionnées avant `SKULL-01.3` ;
- les permissions de `/var/backups` sont larges au niveau du répertoire parent ;
  la prochaine tâche devra créer un sous-répertoire de sauvegarde en `0750` et
  vérifier ses permissions ;
- aucune archive n’a été créée, aucun service n’a été arrêté et aucune écriture
  distante n’a été effectuée dans cette tâche.

## Rollback

Aucun rollback distant nécessaire : la tâche n’a effectué que des lectures. La
preuve locale est additive et peut être conservée même si le préflight est
rejoué avec un nouvel horodatage.

## Prochaine tâche autorisée

`SKULL-01.2` — exporter le code, le diff, les unités systemd et les dépendances
de production dans une preuve locale, sans arrêt de service. Elle n’est pas
exécutée dans le cadre de cette tâche.
