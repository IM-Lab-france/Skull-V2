# SKULL-02.2 — inventaire du patch de production

## Périmètre

Patch analysé : `C:\Skull-V2\evidence\SKULL-01.2\production.patch`.
Application réalisée uniquement dans :
`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`.

Le patch est expurgé : la nouvelle configuration du webhook lit une variable
d’environnement et aucune valeur de secret n’est présente. Les URI `data:` de
CSS et les URL de documentation locale présentes dans le diff ne sont pas des
identifiants d’accès.

## Fichiers modifiés

| Fichier | Classe | Résumé |
|---|---|---|
| `loop_player.py` | fonctionnel | Ajout d’un gain utilisateur et de `set_volume`, avec fondu, état `user_volume` et conservation du gain lors d’un arrêt. |
| `web_app.py` | fonctionnel / configuration | Ajout de `/loop/volume`, exposition de `volume_percent`, déclenchement conditionnel d’`Accueil` vers un webhook configuré par environnement, timeout et journalisation ; exclusion aléatoire normalisée sur `Accueil`. Plusieurs changements sont uniquement du reformatage Python. |
| `static/app.js` | fonctionnel UI | Ajout du curseur de volume de boucle, debounce, appel POST `/loop/volume`, synchronisation avec l’état serveur et gestion des erreurs ; reformatage de quelques expressions existantes. |
| `static/style.css` | UI | Ajout du style du curseur de volume et de sa variante responsive. |
| `static/playlist.css` | UI | Refonte visuelle du bouton de catalogue : gradient, dimensions, ombre et focus clavier ; aucune logique serveur. |
| `static/playlist.js` | UI / texte | Remplacement du libellé « Ajouter un morceau » par « Lancer un sort ». |
| `templates/index.html` | UI | Ajout du groupe de contrôle du volume de boucle et reformatage de deux boutons. |
| `templates/playlist_only.html` | UI / texte | Même changement de libellé et fin de fichier modifiée. |

## Exclusions

Aucun venv, log, fichier `.env`, configuration runtime, donnée audio ou secret
n’a été ajouté au worktree. Aucun fichier non suivi n’a été créé par
l’application du patch.

## Points de vigilance pour la suite

- Le webhook dépend maintenant de `SKULL_SMOKE_WEBHOOK_URL` ou de
  `PLAYLIST_ACCUEIL_WEBHOOK` côté production ; la présence et la validation de
  cette configuration devront être traitées dans `SKULL-02.4`/`SKULL-08`.
- Le nouveau endpoint et le comportement de volume nécessitent des tests de
  caractérisation avant tout déploiement.
- Les fins de fichier sans saut de ligne et les différences CRLF/LF restent du
  bruit de présentation à normaliser séparément ; elles ne doivent pas être
  mélangées à une modification fonctionnelle.

