# Runbook — déploiement de configuration (`SKULL-08.7`)

Ce runbook prépare un déploiement futur. Sa lecture et la validation locale du
candidat ne modifient aucun système.

## Garde d’approbation

Une confirmation séparée est obligatoire avant toute écriture sous
`/etc/skull`, changement de propriétaire/mode ou redémarrage de service. La
confirmation doit couvrir la cible, la fenêtre, l’impact attendu et le
rollback.

## Préparation locale

1. Valider le candidat avec `python -m config.validate` ; cette commande ne
   charge aucun client matériel et n’ouvre aucun socket.
2. Vérifier que le candidat contient uniquement des références de secrets et
   aucun contenu secret.
3. Comparer la configuration résolue aux contrats legacy et conserver les
   routes legacy pendant la coexistence.
4. Préparer les chemins cibles : code immuable `/opt/skull/current`, TOML
   `/etc/skull/config.toml`, secrets distincts, données `/var/lib/skull` et
   logs `/var/log/skull`.

## Séquence protégée sur la cible

1. Capturer une sauvegarde contrôlée des fichiers et de leurs permissions ; ne
   jamais copier la valeur d’un secret dans Git, les logs ou le chat.
2. Installer le candidat avec le propriétaire du service et les modes
   minimaux ; le fichier de secrets est séparé du TOML.
3. Exécuter le validateur sans initialisation matérielle.
4. Démarrer une candidate sur port parallèle local et comparer les états
   `live`, `ready`, les logs et les contrats.
5. Basculer le service uniquement après validation de la candidate.
6. Surveiller le démarrage, l’audio simulé et les erreurs contrôlées ; aucune
   validation physique n’est déduite d’un simple démarrage HTTP.

## Rollback

Arrêter la bascule, restaurer le TOML, le fichier de secrets et l’unité de
service précédents avec leurs permissions, puis redémarrer l’ancienne version.
Vérifier les données et les logs après restauration. Ne jamais supprimer les
sources legacy ni les données de lecture pour revenir en arrière.

## État actuel

Le schéma, la migration et le validateur sont validés localement. Aucun chemin
`/etc/skull`, service systemd, Raspberry Pi ou matériel réel n’a été écrit ou
redémarré ; le déploiement reste en attente d’une autorisation distincte.
