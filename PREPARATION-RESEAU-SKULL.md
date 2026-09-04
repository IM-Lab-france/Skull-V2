# Preparation réseau du Skull

Statut : préparation locale uniquement — aucune écriture réseau exécutée.

## Cible retenue

| Élément | Valeur cible |
|---|---|
| Wi-Fi | SSID IoT 2,4 GHz du Flint, documenté actuellement comme `GL.iNet IoT` |
| VLAN | 40 — IOT |
| Adresse | `192.168.40.20/24` |
| Attribution | réservation DHCP par adresse MAC du Raspberry |
| Passerelle | `192.168.40.1` |
| DNS | `192.168.40.1` |
| Nom DNS | `skull.home.arpa` |
| Home Assistant | `192.168.40.10:8123` |

L’adresse `.20` est une proposition hors du pool DHCP documenté `.100-.199`.
Elle doit être vérifiée comme libre avant réservation. Ne pas configurer une
IP statique dans Debian avant cette vérification.

Le SSID IoT était documenté comme désactivé. Il devra être activé et attaché au
VLAN 40. Le Skull ne doit pas rejoindre le SSID utilisateurs ou invités.

## Flux à préparer

| Source | Destination | Autorisation |
|---|---|---|
| Skull `192.168.40.20` | Home Assistant `192.168.40.10:8123/TCP` | autoriser |
| Skull | DNS/NTP | autoriser les services retenus |
| Edge Proxy `192.168.90.10` | Skull `192.168.40.20:5000/TCP` | autoriser pour l’interface principale |
| Edge Proxy `192.168.90.10` | Skull `192.168.40.20:5050/TCP` | autoriser seulement si la playlist est publiée séparément |
| VLAN 50 MANAGEMENT | Skull | SSH/administration ciblés uniquement |
| Internet | Skull directement | refuser |

La publication Internet doit rester :

```text
Internet → Freebox/Flint → Edge Proxy VLAN 90 → Skull VLAN 40
```

Aucun port WAN ne doit être redirigé directement vers `192.168.40.20`.

## Préconditions avant application

1. Relever l’adresse MAC réelle du Raspberry Skull.
2. Vérifier que `192.168.40.20` est libre et absente des réservations DHCP.
3. Vérifier que le SSID IoT est bien associé au VLAN 40.
4. Vérifier que Home Assistant accepte réellement `TCP/8123`.
5. Sauvegarder la configuration Flint, DHCP/DNS et les règles pare-feu.
6. Préparer le rollback vers le SSID et l’adresse legacy `192.168.1.116`.
7. Ajouter une authentification et séparer les routes publiques des routes
   d’administration du Skull avant toute exposition Internet.

## Validation attendue

- Le Raspberry obtient `192.168.40.20` sur le SSID IoT.
- `skull.home.arpa` résout vers `192.168.40.20`.
- Depuis le Skull, `192.168.40.10:8123` est joignable.
- Depuis le VLAN 50, SSH et les healthchecks du Skull fonctionnent.
- Depuis l’Edge Proxy, seuls les ports publiés du Skull répondent.
- Depuis Internet, seul le nom public HTTPS via l’Edge Proxy répond.
- Un accès direct Internet aux ports `5000`, `5050` et `22` est refusé.
- Un client IoT non autorisé ne peut pas administrer le Skull ni accéder aux
  autres VLAN internes.

Cette préparation ne vaut pas preuve d’application ni de connectivité réelle.
