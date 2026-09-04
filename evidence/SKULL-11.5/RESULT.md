# Résultat SKULL-11.5

- Date : 3 septembre 2026
- Statut : PARTIEL
- Cible : Raspberry `skull`, migré de `192.168.1.116` vers le VLAN 40
- Routeur : Flint `192.168.50.1`
- Sauvegarde Flint : `/root/backup-network-20260903T174001Z`
- Sauvegarde réseau Skull : `/var/backups/skull/network-20260903T174013Z/`

## Configuration appliquée

- SSID IoT 2,4 GHz activé sur l’interface virtuelle `ra3` :
  `GL-MT6000-8d5-IoT` ; le SSID Users conserve `ra2`.
- Réservation DHCP par la MAC du Skull vers `192.168.40.20`.
- DNS `skull.home.arpa` vers `192.168.40.20` dans dnsmasq et AdGuard Home.
- Autorisation Skull → Home Assistant `192.168.40.10:8123/TCP`.
- Autorisation gestion → Skull sur `22`, `5000` et `5050/TCP`.
- Autorisation DNS/NTP IoT vers le Flint selon les règles dédiées.
- Le profil NetworkManager legacy `preconfigured` est conservé ; le profil
  actif est `skull-iot`.

## Validation exécutée

- hostname `skull`, Debian 12 ARM64 ;
- Wi-Fi actif sur `GL-MT6000-8d5-IoT` ;
- adresse `192.168.40.20/24`, passerelle et DNS `192.168.40.1` ;
- `skull.home.arpa` résout vers `192.168.40.20` depuis le Skull ;
- Home Assistant répond `HTTP 200` sur `192.168.40.10:8123` ;
- `skull-candidate.service` et `playlist-web.service` sont actifs ;
- healthchecks Skull `/health/live`, `/health/ready` et `/status` répondent `200` ;
- depuis PVE0 en VLAN 50, les ports Skull `22`, `5000` et `5050` répondent ;
- depuis le Skull, les accès vers Flint SSH, Proxmox management, serveurs et
  Internet direct sont refusés ;
- aucun DNAT WAN vers `192.168.40.20` et aucun forwarding IoT → WAN présents.

## Écarts et suites

- La règle Edge Proxy `192.168.90.10 → Skull:5000` n’est pas activée : les
  routes d’administration Skull ne sont pas encore authentifiées et séparées.
- Le redémarrage AdGuard a relancé le moteur firewall et affiché des erreurs
  de scripts auxiliaires historiques ; les règles Skull attendues sont
  toutefois présentes dans la configuration persistante et dans iptables.
- `ha.home.arpa` n’a pas été modifié ; la cible validée pour Skull reste
  l’adresse directe `192.168.40.10:8123`.

## Rollback

- Flint : restaurer les fichiers sauvegardés dans
  `/root/backup-network-20260903T174001Z`, puis recharger dnsmasq, Wi-Fi et
  firewall.
- Skull : réactiver le profil NetworkManager `preconfigured` pour revenir au
  SSID et à l’adressage legacy ; le profil `skull-iot` reste supprimable après
  validation explicite du rollback.

Aucun secret, mot de passe ou contenu de clé Wi-Fi n’est présent dans cette
preuve.
