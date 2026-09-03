# Phase 12 — validation matérielle finale

## Conditions impératives

Cette phase nécessite une personne auprès du Skull, une zone dégagée, un moyen
d’arrêt électrique immédiat et une confirmation avant chaque famille d’effets.
Luna ne choisit jamais seule un angle, un volume ou une durée de fumée non déjà
validé. Les limites actuelles sont sauvegardées avant tout essai.

## SKULL-12.1 — préparer la séance

### Checklist

1. noter date, participants, release et configuration ;
2. photographier ou noter l’état mécanique initial ;
3. dégager les mécanismes et éloigner les personnes ;
4. identifier alimentation et coupure d’urgence ;
5. sauvegarder offsets, neutres, limites et playlists ;
6. vérifier température, alimentation et câblage visuellement ;
7. arrêter tout autre logiciel pouvant contrôler le matériel ;
8. convenir des mots `GO`, `STOP` et du volume maximal ;
9. ouvrir le procès-verbal `evidence/SKULL-12/acceptance.md`.

### Arrêt immédiat si

bruit mécanique anormal, servo en butée, échauffement, fumée non demandée,
odeur, perte de contrôle, processus dupliqué ou impossibilité de couper.

## SKULL-12.2 — valider sans effet matériel

### Étapes

1. vérifier release, service et unique processus ;
2. appeler live et ready ;
3. lire catalogue, état, playlist et configuration redigée ;
4. vérifier logs, rotation et espace disque ;
5. vérifier refus des routes non autorisées ;
6. confirmer qu’aucune étape n’a bougé, joué ou déclenché quoi que ce soit.

### Acceptation

- état nominal ou dégradé expliqué ;
- aucune sortie physique observée.

## SKULL-12.3 — tester l’audio seul

### Confirmation requise

Émission sonore à faible volume.

### Étapes

1. désactiver ou neutraliser la timeline et la fumée ;
2. vérifier l’identité exacte du sink ;
3. régler le volume au maximum convenu sans le dépasser ;
4. jouer un fichier court connu ;
5. tester pause, reprise et stop ;
6. éteindre/rallumer le JBL et répéter ;
7. confirmer auditivement le résultat avec l’utilisateur.

### Acceptation

- aucun mouvement ;
- son sur le seul périphérique prévu ;
- stop immédiat et reconnexion reproductible.

## SKULL-12.4 — tester chaque servo autour du neutre

### Confirmation requise pour chaque servo

Le nom, le canal, le neutre, l’amplitude réduite et la direction doivent être
lus depuis la configuration sauvegardée et approuvés. Ne pas inventer de valeur.

### Séquence par servo

1. neutraliser tous les autres canaux ;
2. commander le neutre ;
3. attendre confirmation visuelle ;
4. commander un petit déplacement approuvé dans un sens ;
5. revenir au neutre ;
6. commander le même déplacement approuvé dans l’autre sens ;
7. revenir au neutre et vérifier absence de vibration ;
8. noter valeur demandée, valeur clampée et résultat.

### Acceptation

- aucune butée ni collision ;
- sens et limites documentés ;
- arrêt électrique testé au moins une fois sans charge dangereuse.

## SKULL-12.5 — tester une timeline courte

### Étapes

1. choisir une fixture déjà validée en simulation ;
2. afficher durée, servos concernés et amplitudes maximales ;
3. obtenir confirmation ;
4. exécuter sans audio ni fumée au premier passage ;
5. comparer trace réelle et trace simulée ;
6. répéter avec audio seulement si le premier passage est validé ;
7. tester pause, reprise et stop au milieu.

### Acceptation

- état final neutre ;
- aucune dérive hors tolérance définie avant le test ;
- stop interrompt audio et commandes.

## SKULL-12.6 — tester boutons et sonnette

### Étapes

1. activer un mode de test sans fumée ;
2. appuyer une fois sur chaque bouton et noter requête/action ;
3. vérifier les cinq entrées firmware et les affectations serveur ;
4. maintenir/appuyer rapidement pour vérifier anti-rebond ;
5. tester la sonnette une fois sans effet, puis avec session courte confirmée ;
6. couper le réseau du Skull et vérifier timeouts côté émetteurs ;
7. rétablir et vérifier la reprise.

### Acceptation

- une action attendue par événement ;
- aucune boucle de retry agressive ;
- identité et ACL correctes.

## SKULL-12.7 — tester `Accueil` et la fumée

### Confirmation renforcée

Le dispositif de fumée est testé uniquement dans des conditions adaptées au
matériel, à la ventilation et à la présence humaine. Commencer par un faux
adaptateur ou une observation du webhook. La fumée réelle exige un `GO` séparé.

### Étapes

1. prouver avec le faux adaptateur que seule `Accueil` demande la fumée ;
2. appeler le webhook réel avec la charge non dangereuse prévue ;
3. vérifier authentification, délai et réponse ;
4. si autorisé, exécuter l’impulsion minimale déjà documentée ;
5. tester stop et indisponibilité domotique ;
6. vérifier absence de second déclenchement.

### Acceptation

- fumée jamais déclenchée pour une autre session ;
- déclenchement unique, borné et interruptible selon le matériel ;
- résultat observé par la personne présente.

## SKULL-12.8 — tester les pannes et le rollback

### Étapes

1. pendant état neutre, couper puis rétablir le réseau ;
2. redémarrer le service et vérifier un seul processus ;
3. redémarrer le Raspberry et vérifier ready, audio et clients ;
4. rendre une dépendance externe indisponible et vérifier le mode dégradé ;
5. basculer vers la release précédente avec la procédure de phase 10 ;
6. vérifier routes legacy, données, configuration et état neutre ;
7. rebasculer uniquement si le rollback est validé.

### Acceptation

- aucune sortie imprévue au démarrage ;
- reprise ou état dégradé borné ;
- rollback complet démontré.

## SKULL-12.9 — signer le procès-verbal

### Contenu obligatoire

- versions logiciel/configuration/firmware ;
- matériel et périphériques testés ;
- chaque test avec `VALIDÉ`, `PARTIEL` ou `BLOQUÉ` ;
- preuves et horodatages ;
- écarts, risques résiduels et contournements ;
- release de rollback ;
- décision de remise en service et nom du validateur humain.

La phase est terminée uniquement si les fonctions indispensables sont validées
et si aucun défaut de sécurité mécanique ou électrique n’est ouvert.
