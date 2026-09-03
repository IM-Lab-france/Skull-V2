# Runbook — rotation du secret fumée (`SKULL-08.5`)

Ce document décrit une exécution future. Il ne contient aucune valeur de
secret, URL complète, adresse réseau ou commande d’envoi vers la domotique.

## Garde d’approbation

Ne pas poursuivre la bascule tant que les trois conditions suivantes ne sont
pas confirmées séparément :

1. le consommateur domotique accepte temporairement l’ancien et le nouveau
   secret ;
2. le nouveau secret a été généré par le gestionnaire approuvé, hors chat,
   dépôt Git, ligne de commande et historique shell ;
3. le propriétaire confirme la fenêtre de test et le rollback.

Sans ces confirmations, l’état reste `BLOQUÉ` et aucune écriture n’est faite.

## Cibles

- Producteur : Skull, déclenchement nommé `Accueil`.
- Consommateur : service domotique derrière la référence webhook existante.
- Configuration Skull : référence `smoke.endpoint_ref` dans
  `/etc/skull/config.toml`.
- Secret : fournisseur `env:` ou fichier distinct `/etc/skull/secrets.env`,
  lisible uniquement par le compte de service.

## Séquence contrôlée

1. Sauvegarder uniquement la configuration et les permissions, sans recopier
   la valeur du secret dans Git, les logs ou le chat.
2. Préparer le consommateur domotique pour la double acceptation.
3. Vérifier son état depuis son interface approuvée, sans afficher les
   secrets.
4. Installer la nouvelle référence côté Skull avec le propriétaire et le
   mode minimaux.
5. Valider la configuration sans initialiser le matériel, puis redémarrer le
   service dans une fenêtre approuvée.
6. Déclencher une seule session `Accueil` de test et vérifier l’événement côté
   domotique ; ne pas confondre réponse HTTP et effet physique fumée.
7. Retirer l’ancienne acceptation côté consommateur et vérifier qu’elle est
   refusée, puis vérifier que la nouvelle reste acceptée.
8. Rechercher l’ancien identifiant dans les emplacements approuvés sans
   imprimer sa valeur.

## Rollback

En cas d’échec, arrêter la bascule, restaurer la référence précédente depuis
la sauvegarde contrôlée, rétablir l’ancienne acceptation côté consommateur,
redémarrer le service et refaire un test borné. Ne jamais supprimer les
appairages Bluetooth ni les données de lecture comme rollback du webhook.

## État actuel

La préparation de référence et le plan logiciel sont validés localement. La
génération, le déploiement, le test réel et le retrait de l’ancien secret sont
encore en attente d’autorisation et d’accès aux deux systèmes.
