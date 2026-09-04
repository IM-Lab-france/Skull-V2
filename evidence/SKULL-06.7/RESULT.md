# SKULL-06.7 — façade HTTP legacy

Statut : `VALIDÉ`

Date d’exécution : 3 septembre 2026, Europe/Paris

## Résultat

Les endpoints historiques sont maintenant enregistrés par le blueprint
`legacy` créé dans `api/legacy.py`. Les routes conservent leurs chemins,
méthodes, paramètres, statuts et formes JSON ; aucune modification n’est
requise côté boutons, sonnette ou clients existants.

Les appels de contrôle de lecture sont traduits vers
`LegacyPlaybackService`, qui reçoit explicitement le lecteur et le contrôleur
de boucle. Le service conserve l’ordre de chargement, suppression de boucle,
lecture et libération sur erreur.

## Vérifications

- Tests ciblés façade et contrats : 28 passés.
- Suite complète : 208 tests passés, 1 avertissement externe connu.
- Compilation Python : OK.
- `git diff --check` : OK ; seuls les avertissements de fins de ligne Git
  existants sont signalés.
- Rechargement répété du module : aucun doublon de règle.
- Aucun secret, webhook complet, adresse réseau, MAC ou contenu de production
  n’est présent dans cette preuve.

## Limites

- Les handlers restent dans `web_app.py` pour limiter le risque de régression ;
  leur enregistrement est cependant isolé par blueprint.
- Aucun Raspberry, service distant, bouton, sonnette ou matériel n’a été
  sollicité.
