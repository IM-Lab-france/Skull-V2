# Résultat SKULL-07.7

- Date : 3 septembre 2026, Europe/Paris
- Statut : `PARTIEL`
- Portée : premier cycle de validation physique du JBL sur le Raspberry
  `skull` via l’unité candidate active.
- Autorisation : confirmation explicite reçue pour Bluetooth, audio à faible
  volume et redémarrages contrôlés.

## Observations

- L’adresse Bluetooth configurée correspond au nom `JBL Quantum 360`.
- Après redémarrage contrôlé de BlueZ et démarrage temporaire de PulseAudio,
  l’appairage, la confiance et la connexion restent stables pendant huit
  secondes ; le bond BlueZ est désormais persistant.
- La carte Bluetooth PulseAudio apparaît, mais aucun sink n’est créé et la
  liaison retombe lors de la bascule A2DP.
- PulseAudio expose le profil réel `a2dp_sink` (underscore), disponible pour
  le JBL. Le correctif local remplace désormais `a2dp-sink` (tiret) par
  `a2dp_sink` dans l’adaptateur et ses contrats de test.
- Même avec le profil réel sélectionné directement, BlueZ signale
  `a2dp-sink profile connect failed` / `Protocol not available`, puis les
  endpoints A2DP sont désenregistrés ; aucun sink ne peut être défini par
  défaut.
- La candidate déployée reste au jalon `SKULL-05.7` et ne contient pas la
  route de phase 7 `/bluetooth/select-output` (réponse HTTP 404). Les tests
  matériels ne peuvent donc pas valider le code local de phase 7 sans une
  future bascule de release.
- La fiche technique officielle JBL confirme les profils HFP 1.5 et A2DP
  1.3 : le casque est compatible A2DP.
- Le redémarrage contrôlé de `skull-candidate.service` a réussi ; l’IHM est
  revenue en HTTP 200 et `servo-sync.service` est resté inactif.
- `bluetooth.service` a été redémarré de manière contrôlée ; l’instance
  utilisateur PulseAudio et ses modules de découverte ont été relancés sans
  modification de fichier persistant.
- Aucun son n’a été joué et aucun cycle extinction/rallumage complet n’a été
  validé.

## Commandes de validation

- Diagnostic BlueZ/PulseAudio masqué avant action.
- Reconnexion contrôlée de l’adresse configurée, sans scan.
- Appairage, confiance et connexion explicites après passage du JBL en mode
  appairage.
- Redémarrage contrôlé de BlueZ, démarrage temporaire de PulseAudio et
  rechargement réversible de sa découverte Bluetooth.
- Inspection des profils exposés par PulseAudio et sélection manuelle du
  profil A2DP réel, sans volume, mute ni lecture sonore.
- Redémarrage contrôlé de `skull-candidate.service`.
- Vérification de l’état HTTP, BlueZ, A2DP et sink.

## Écarts ou risques restants

- Déployer le correctif local `a2dp_sink` dans une release distincte avant de
  le valider matériellement sur le Raspberry.
- Diagnostiquer le refus A2DP persistant de BlueZ/PulseAudio malgré la carte
  présente et le profil disponible ; aucun fallback HFP ne doit être appliqué
  silencieusement.
- Vérifier ensuite le sink par défaut avant toute lecture à faible volume.
- Exécuter les trois cycles extinction/rallumage et le redémarrage Raspberry.

## Rollback

- Aucun fichier de production ni configuration logicielle n’a été modifié par
  cette validation.
- Redémarrer `bluetooth.service` et l’instance utilisateur PulseAudio restaure
  leurs modules issus de la configuration existante ; ne pas supprimer le bond
  JBL comme méthode de rollback.
- Le service candidate peut être remis dans son état précédent.

## Tentative de déploiement du correctif A2DP

- Une archive applicative contrôlée a été préparée sans `config`, `data`,
  `logs`, `.venv`, tests, preuves ni fichiers secrets ; son empreinte locale et
  distante correspondait.
- Une sauvegarde distante du code précédent a été créée avant la bascule.
- `skull-candidate.service` a été arrêté puis relancé avec le code candidat.
  Le démarrage du processus a été observé, mais l’HTTP sur le port 5000 a
  cessé de répondre : `/status` et la route de sélection A2DP ont expiré.
- La vérification A2DP/sink n’a donc pas été validée et aucun son n’a été joué.
- Le rollback du code précédent a été exécuté. Résultat final :
  `skull-candidate.service` actif, HTTP 200, route moderne absente (404),
  `servo-sync.service` inactif.
- La candidate distante est donc restée sur son état précédent ; la tâche
  reste `PARTIEL`. Les données, la configuration Bluetooth et la phase 8 n’ont
  pas été ciblées.

## Diagnostic complémentaire et correction

- Le premier timeout ne provenait pas de l’initialisation audio : les journaux
  distants contiennent `LOOP_STREAM_STARTED`. Le contrôle de déploiement sondait
  toutefois `/status`, qui peut lancer une reconnexion Bluetooth synchrone dans
  l’unique worker Gunicorn. Le contrôle a été corrigé pour utiliser
  `/health/live` puis `/health/ready`.
- Deux erreurs de pilotage ont également été corrigées sans toucher au code
  applicatif : extraction `tar` sans restauration des métadonnées de
  répertoires et génération JSON avec quotes shell littérales.
- Après ces corrections, les deux healthchecks ont répondu correctement et la
  route `/bluetooth/select-output` a été atteinte. Elle a répondu 409 car
  BlueZ indique actuellement le périphérique appairé et approuvé, mais non
  connecté ; PulseAudio utilisateur est inactif. Ce comportement respecte le
  contrat et bloque proprement la sélection d’un sink non prouvé.
- Le correctif local `a2dp_sink` reste prêt dans le worktree candidat, mais la
  vérification matérielle ne peut reprendre qu’après mise sous tension du JBL
  et disponibilité de PulseAudio. Aucun appairage, connexion forcée ou son n’a
  été déclenché pendant ce diagnostic.

## Diagnostic et déploiement du correctif de session audio

- Le correctif local rend l’environnement PulseAudio explicite pour un service
  systemd : lorsque les variables de session sont absentes, `pactl` cible le
  socket utilisateur canonique. Les variables explicites existantes restent
  prioritaires ; l’unité systemd n’a pas été modifiée.
- Validation locale : 12 tests Bluetooth/PulseAudio ciblés et 257 tests de la
  suite complète passent. La compilation Python, la syntaxe JavaScript et le
  contrôle de diff passent également.
- Une nouvelle archive applicative, sans configuration, données, journaux,
  preuves, tests ni secrets, a été transférée avec empreinte locale/distante
  identique. La candidate a répondu correctement aux healthchecks et la route
  moderne a été observée pendant la tentative ; le rollback a ensuite restauré
  le code précédent après l’échec de la validation physique.
- Après déploiement, le JBL est visible par le contrôleur et reste `paired` et
  `trusted`, mais `connected=no` et `ServicesResolved=no`. BlueZ renvoie
  `br-connection-profile-unavailable` ; PulseAudio est joignable, ses modules
  Bluetooth sont chargés, mais aucune carte Bluetooth n’est publiée.
- Aucun son n’a été joué. `servo-sync.service` est resté inactif et aucune
  donnée/configuration n’a été ciblée. La tâche reste `PARTIEL` jusqu’à
  connexion A2DP effective, sélection du sink, puis validation physique.
- Une seconde tentative avec le JBL en mode appairage a confirmé le même refus
  `profile_unavailable` après une attente bornée de résolution des services.
  Le rollback a de nouveau restauré la candidate précédente ; aucun bond
  Bluetooth n’a été supprimé.

## Essai séparé Bose SoundLink Mini II

- Le scan a identifié `Bose Mini II SoundLink` ; son appairage et sa confiance
  ont réussi sans supprimer les bonds existants.
- Avec PulseAudio utilisateur lancé juste avant la connexion, BlueZ a accepté
  la connexion Bose et PulseAudio a publié temporairement une carte Bluetooth.
  Cela valide la chaîne radio BlueZ vers PulseAudio pour cette enceinte.
- La carte a ensuite disparu lorsque la session PulseAudio est redevenue
  inactive et le sink `auto_null` est revenu. La persistance de la session audio
  reste donc une correction distincte à traiter.
- La variable de production reste configurée sur le périphérique précédent ;
  la Bose n’a pas été substituée dans la configuration et aucun son n’a été
  joué. La tâche reste `PARTIEL`.
- Après confirmation explicite, une bascule temporaire vers la Bose a été
  préparée avec sauvegarde de la configuration précédente, maintien PulseAudio
  (`exit-idle-time=-1`), variables de session systemd et routage ALSA vers
  PulseAudio. La candidate a répondu aux healthchecks, mais la connexion Bose
  via l’IHM a expiré (`504`). Le rollback a restauré la candidate, la
  configuration précédente et l’absence des fichiers audio temporaires ;
  `servo-sync.service` est resté inactif.

## Capture HCI/D-Bus et correction de la connexion IHM

- Une capture classifiée a été réalisée pendant une tentative de connexion
  Bose. Les outils HCI et D-Bus étaient disponibles, PulseAudio était joignable
  et la commande bornée a terminé avec un code nul, mais BlueZ ne rapportait
  alors ni appairage, ni confiance, ni connexion, ni service résolu ; aucune
  carte ou sortie PulseAudio Bluetooth n’est apparue.
- La rupture observée est donc antérieure à la négociation A2DP sur cette
  tentative. Aucune trame HCI, adresse ou sortie brute n’a été conservée dans
  la preuve.
- Le défaut applicatif confirmé a été corrigé : la connexion de l’IHM et le
  reconnecteur utilisent désormais `bluetoothctl` en mode direct, avec agent
  `NoInputNoOutput` et délai borné, au lieu d’envoyer `connect` puis `quit`
  immédiatement dans une session interactive.
- Validation locale : 261 tests passent, compilation Python OK et archive de
  77 entrées sans configuration active, données, journaux, preuves, tests ou
  secrets.
- La candidate corrigée a été déployée sous `/opt/skull-candidate`, avec
  empreinte locale/distante identique, arrêt/redémarrage contrôlé et healthcheck
  HTTP 200. `servo-sync.service` est resté inactif et inchangé ; une sauvegarde
  root protégée de la candidate précédente est conservée.
- Le socle de session audio a ensuite été installé pour la candidate :
  variables systemd vers la session utilisateur `skull`, politique PulseAudio
  `exit-idle-time = -1` et défaut ALSA vers PulseAudio. Après redémarrage,
  PulseAudio est joignable et ses modules Bluetooth sont chargés ; aucune carte
  Bluetooth n’est attendue tant que la Bose n’est pas appairée/connectée.
- La validation matérielle finale reste à faire : au dernier contrôle la Bose
  n’était plus rapportée comme appairée par BlueZ. Aucun son n’a été joué. La
  tâche reste `PARTIEL` jusqu’à nouvel appairage, connexion IHM et apparition
  vérifiée du sink A2DP.

## Validation Bose après correction

- Après remise de la Bose en mode appairage, l’IHM a réalisé l’appairage et la
  confiance avec HTTP 200.
- La première connexion a révélé un second défaut : `bluetoothctl` pouvait
  rester bloqué malgré l’option interne de délai. Le correctif utilise désormais
  le superviseur Linux `timeout` et transforme son code 124 en expiration
  Bluetooth contrôlée.
- Après redéploiement, la connexion Bose via l’IHM répond HTTP 200. La carte
  PulseAudio est publiée avec un profil `a2dp_sink` actif.
- Le sink réellement exposé par PulseAudio natif est
  `bluez_sink.<adresse>.*`, et non `bluez_output.<adresse>.*`. Le détecteur
  accepte maintenant les deux nomenclatures. Le parseur d’état accepte aussi
  l’ordre réel `State` avant `Name` renvoyé par `pactl`.
- La sélection de sortie via l’IHM répond HTTP 200 ; PulseAudio est joignable,
  la carte Bluetooth et le sink sont présents, et le sink est sélectionné par
  défaut. Aucun volume, mute ou son n’a été déclenché.
- Validation locale finale : 264 tests passent, compilation Python OK ; la
  candidate reste active sur le port 5000, `servo-sync.service` est resté
  inactif et inchangé. La tâche reste `PARTIEL` jusqu’au test audio physique.
