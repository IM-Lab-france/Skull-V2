# SKULL-01.5 — préparation de la sauvegarde de carte SD

## Statut

**VALIDÉ — image créée et checksum vérifié.**

La source a été lue par Rufus 4.14 depuis le disque physique `8`, initialement
monté en `L:`. L’image créée est :

```text
D:\Skull-Backups\skull-20260902T200000Z.vhdx
taille : 8963227648 octets
signature VHDX : 76 68 64 78 66 69 6C 65 (vhdxfile)
```

La carte `E:` n’a pas été utilisée comme destination et n’a pas été formatée.
SHA-256 vérifié localement :

```text
3FEFF0E7EA02D6933338E4E792BBA7082B5B00B71A3B63A552870244216923B8
```

La valeur est conservée dans `SHA256SUMS.txt`.

## Contrôles effectués

### Source sur le Skull

Inventaire lecture seule exécuté sur `skull@192.168.1.116` :

```text
/dev/mmcblk0  disk  31914983424 bytes  name=SC32G  type=SD
├─/dev/mmcblk0p1  vfat  536870912 bytes      /boot/firmware
└─/dev/mmcblk0p2  ext4  31369723904 bytes    /
```

La racine utilise environ 7,1 Go et dispose d’environ 20,1 Go libres. La
source exacte à imager est donc `/dev/mmcblk0`, et non une partition seule.

### Destinations locales observées

| Support | Observation | Décision |
|---|---|---|
| `E:` / disque Windows `3` | USB amovible, 31 914 983 424 octets, partition FAT32 presque vide | destination retenue, à écraser après confirmation |
| `H:` | USB amovible, « No Media », capacité nulle | inutilisable |
| `C:` | NTFS, disque fixe, environ 71,5 GiB libres | non retenu comme support matériel |
| `D:` | NTFS, disque fixe, environ 801,7 GiB libres | non retenu comme support matériel |

Les numéros de série et valeurs sensibles ne sont pas consignés. La destination
validée pour la prochaine opération est le disque physique Windows `3`, monté
en `E:`. Le clonage vers une partition ou vers `C:`/`D:` reste interdit.

## Méthode retenue

Image hors ligne, depuis une machine Linux distincte :

1. Arrêter proprement les services, puis arrêter le Raspberry.
2. Retirer la carte SD et l’insérer dans le lecteur de la machine d’imagerie.
3. Vérifier trois fois le modèle, la taille et le chemin du périphérique source.
4. Démonter ses partitions sans modifier la carte.
5. Écrire une image brute vers un fichier situé sur un support externe dédié.
6. Exécuter `sync`, puis calculer et vérifier le SHA-256 du fichier image.
7. Éjecter proprement le support et conserver l’image en lecture seule.

Une image complète nécessite au minimum 31 914 983 424 octets. La destination
recommandée dispose d’au moins 40 Go libres pour couvrir l’image, son checksum
et une marge de travail.

## Commandes de référence — à exécuter uniquement après confirmation

Les chemins ci-dessous sont des exemples à remplacer par les chemins réellement
validés. Ils ne constituent pas une autorisation d’exécution :

```bash
lsblk -o NAME,TYPE,SIZE,MODEL,SERIAL,MOUNTPOINTS
sudo umount /dev/mmcblk0p1 /dev/mmcblk0p2
sudo dd if=/dev/mmcblk0 of=/mnt/backup/skull-YYYYMMDDTHHMMSSZ.img \
  bs=4M status=progress conv=fsync
sha256sum /mnt/backup/skull-YYYYMMDDTHHMMSSZ.img \
  | tee /mnt/backup/skull-YYYYMMDDTHHMMSSZ.img.sha256
sync
```

Estimation indicative, à recalculer selon le débit mesuré : environ 25 minutes
à 20 MiB/s, 13 minutes à 40 MiB/s ou 6,5 minutes à 80 MiB/s.

## Procédure de restauration

La restauration écrase intégralement la carte cible. Elle nécessitera une
confirmation séparée et une identification stricte de la carte cible :

```bash
sha256sum -c skull-YYYYMMDDTHHMMSSZ.img.sha256
lsblk -o NAME,TYPE,SIZE,MODEL,SERIAL,MOUNTPOINTS
sudo umount /dev/mmcblk0p1 /dev/mmcblk0p2
sudo dd if=/mnt/backup/skull-YYYYMMDDTHHMMSSZ.img of=/dev/mmcblk0 \
  bs=4M status=progress conv=fsync
sync
```

Après remise en place et démarrage, vérifier sans lancer de session :
`systemctl is-active servo-sync.service playlist-web.service`, l’endpoint
`/status`, le montage de `/`, puis les services et les flux matériels pendant
une validation contrôlée. Ne jamais restaurer vers une partition (`p1`/`p2`).

## Point d’arrêt

La confirmation est acquise, l’image est créée sur `D:` et son SHA-256 est
conservé. La restauration devra être testée sur une carte cible dédiée, jamais
sur la source sans nouvelle confirmation.
