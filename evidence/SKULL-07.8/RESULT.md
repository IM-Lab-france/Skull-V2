# Résultat SKULL-07.8

- Date : 3 septembre 2026, Europe/Paris
- Statut : `VALIDÉ`
- Portée : découplage de la reconnexion Bluetooth et de l’IHM dans la
  candidate `C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`, puis
  déploiement contrôlé sur `/opt/skull-candidate`.

## Correctif réalisé

- Ajout d’un worker daemon unique et annulable pour exécuter la politique de
  reconnexion hors du chemin HTTP.
- Démarrage du worker lors de l’initialisation de la candidate en mode réel.
- `/status` ne déclenche plus `_ensure_bt_connection` ; il publie uniquement
  l’état BlueZ, l’état du sink et le dernier résultat connu du worker.
- Le délai de connexion fourni par le contrôleur est propagé à la commande
  directe `bluetoothctl` et à son superviseur Linux `timeout`.
- La sélection PulseAudio reste postérieure aux preuves indépendantes de
  connexion BlueZ, profil A2DP et sink exact non suspendu par défaut.

## Validation locale et distante

- Tests unitaires du contrôleur et du worker : `8 passed` sous Windows.
- Compilation Python de `web_app.py` et `services/bluetooth_reconnect.py` : OK.
- `git diff --check` : OK, avec seulement les avertissements de conversion de
  fins de ligne déjà présents dans le worktree.
- Harnais distant dans l’environnement `/opt/skull/.venv` : worker, absence de
  reconnexion dans `/status` et propagation du délai validés.
- Harnais distant avec un worker marqué occupé et les appels BlueZ/PulseAudio
  rendus bloquants : `/status` a répondu en `0,030 s` sans appeler ces
  dépendances.
- Suite complète du worktree candidat : `266 passed`, avec un seul
  avertissement externe connu de `pydub/audioop`.
- Le statut Bluetooth expose maintenant un état explicite et stable :
  `reconnecting`, `degraded`, `disconnected`, `connected` ou `audio_ready`.
- L’IHM affiche distinctement la reconnexion en cours, l’état dégradé, la
  connexion établie et l’audio prêt.
- Archive applicative transférée sans `config`, `data`, `logs`, `evidence`,
  `tests`, `.git` ni secrets ; empreinte locale :
  `6ddf6e74a69d0db136fd092d5862f25cc2652602d25dd53c776724c8f52ba44e`.
- Sauvegarde root du code candidat créée avant l’extraction :
  `/var/backups/skull/skull-candidate-bt-worker-timeout2-20260903/code.tar.gz`.
- Après déploiement : `skull-candidate.service` actif, healthchecks live et
  ready HTTP 200, `servo-sync.service` inactif.
- Après redémarrage contrôlé de la candidate : Bose `paired=true`,
  `trusted=true`, `connected=true`, `audio_sink_capable=true`,
  `audio_ready=true`; aucun processus `bluetoothctl` ou `timeout` orphelin.
- Après activation réversible de la candidate dans systemd et reboot complet :
  candidate `enabled/active`, service legacy `disabled/inactive`, healthchecks
  live/ready HTTP 200, et Bose toujours seule cible appairée.
- Après déploiement du correctif `SKULL-07.8` et redémarrage contrôlé du
  service : candidate active, service legacy inactif, healthchecks live/ready
  HTTP 200 ; après la fenêtre de reprise, état `audio_ready=true`.
- Un dernier cycle de déconnexion contrôlée a ensuite été lancé pour tester la
  reprise hors IHM. La Bose est restée `paired=true` et `trusted=true`, mais
  n’a pas repris avant la fin de cette session ; la candidate reste active et
  le worker poursuit ses essais bornés. Aucun scan ni appairage n’a été lancé.

## Acceptation

- `/health/*` et `/status` restent disponibles pendant une reconnexion lente ;
  le worker ne bloque pas le chemin HTTP.
- Le runner commun garantit une seule commande Bluetooth active à la fois ;
  les doubles démarrages du worker sont idempotents.
- Les sondages périodiques n’exécutent ni scan, ni `pair`, ni `trust` ; seule
  l’adresse de configuration est utilisée pour la reconnexion.
- L’état lu, la reconnexion en cours, l’échec dégradé et l’audio prêt sont
  distingués par l’API et l’IHM.
- Les tests d’annulation, de concurrence, de disparition, de reprise et de
  timeout passent sans matériel réel.

La bascule systemd de la candidate reste réversible via la sauvegarde root
créée pendant `SKULL-07.7`. La phase 8 et le code du service legacy n’ont pas
été modifiés.

## Nettoyage des périphériques Bluetooth

- Le bond JBL et le périphérique BLE connu non audio ont été supprimés du
  Raspberry.
- Les anciens fichiers de sauvegarde de configuration Bluetooth ont été
  retirés de `/opt/skull/config`.
- Vérification distante : la liste des périphériques connus et la liste des
  périphériques appairés ne contiennent plus que `Bose Mini II SoundLink`.
- La configuration active et les unités systemd ne contiennent aucune ancienne
  référence JBL, Quantum ou SINB.
- Les occurrences historiques dans les preuves et fixtures de test locales
  sont conservées hors runtime pour préserver la traçabilité.

## Rollback

En cas d’échec, arrêter la candidate, extraire l’archive root conservée dans
`/var/backups/skull/skull-candidate-bt-worker-timeout2-20260903/`, puis
redémarrer `skull-candidate.service`. Aucune configuration, donnée, journal,
appairage ou fichier de la phase 8 n’a été ciblé.
