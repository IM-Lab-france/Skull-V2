# SKULL-06.4 — playlist et état de lecture

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Périmètre

- Exécution locale dans le worktree isolé de production.
- Aucun accès distant ni action matérielle.
- Aucun commit ni push effectué.

## Résultat

La playlist et l’état courant ont été extraits dans `domain/playlist.py`.
Les opérations d’ajout, déplacement, suppression, saut, purge et remise en
tête restent compatibles avec la façade legacy. La sélection aléatoire est
injectable et l’unicité des identifiants est contrôlée.

Une persistance JSON facultative utilise un fichier temporaire et un
remplacement atomique. Les scénarios d’écriture impossible et de fichier
corrompu démontrent l’absence de perte ou de réparation destructive.

## Preuves

- Tests ciblés : 21 passés.
- Suite complète : 116 tests passés, 1 avertissement externe connu.
- Compilation Python : OK.
- `git diff --check` : OK ; seuls les avertissements de fins de ligne Git
  existants sont signalés.

## Limites

Les routes legacy conservent leurs dictionnaires et la persistance reste
désactivée dans le runtime candidat. Aucun comportement HTTP, réseau ou
matériel n’a été modifié volontairement.
